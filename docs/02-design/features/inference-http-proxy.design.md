# [Design] MLOps 포탈 추론 API — HTTP 프록시 전환

> Plan: [inference-http-proxy.plan.md](../../01-plan/inference-http-proxy.plan.md)
> 작성일: 2026-06-05 | 상태: Design

---

## 1. 설계 개요

포탈의 **자체 추론(모델 직접 로드)** 기능을 제거하고, 사용자가 입력한 추론 API URL로 JSON을 **POST 중계**하는 얇은 백엔드 프록시 + 범용 테스터 UI로 전환한다.

### 1.1 조사 기반 사실 (As-Is 확정)

| 사실 | 근거 | 설계 반영 |
|------|------|----------|
| `mlflow/xgboost/pandas/joblib`는 **`inference_service.py`에서만** 사용 | `grep -rln` 전체 app/ 결과 1개 파일 | requirements.txt에서 4종 **완전 제거 가능** |
| `httpx==0.28.1` **이미 존재** | requirements.txt:7 | 추가 의존성 없음 |
| `inference_base_url`이 **config.py에 미정의**인데 web.py가 참조 | config grep 결과 없음 + web.py:74 사용 | `inference_base_url` 설정 **신규 추가**(현재 잠재 버그 동시 해결) |
| `mlflow_cls_model/reg_model/model_stage/tracking_*` 추론 전용 설정 | config.py:40-48 | 추론용으로만 쓰였다면 정리 대상 (단, mlflow_proxy 등 타 용도 확인 후) |

---

## 2. 아키텍처

### 2.1 컴포넌트 다이어그램

```
┌────────────────────────────────────────────────────────────┐
│ 브라우저  /aiml/inference  (inference.html, 범용 테스터)        │
│   [추론 URL] [요청 JSON textarea] [실행] → [JSON 응답 뷰어]      │
└───────────────┬────────────────────────────────────────────┘
                │ POST /api/inference/proxy  (apiFetch, 인증 쿠키)
                │ { target_url, payload, host_header?, timeout? }
                ▼
┌────────────────────────────────────────────────────────────┐
│ routes/inference.py  →  Depends(get_current_user)            │
│   ProxyRequest 검증 → InferenceProxyService.proxy()           │
└───────────────┬────────────────────────────────────────────┘
                │ httpx.AsyncClient.post(target_url, json=payload)
                ▼
┌────────────────────────────────────────────────────────────┐
│ invest-inference Pod / ALB  (수정 없음)                        │
│   POST /predict → JSON                                        │
└────────────────────────────────────────────────────────────┘
```

### 2.2 책임 분리

| 컴포넌트 | 책임 | 비책임(하지 않음) |
|----------|------|------------------|
| 포탈 프론트 | URL·JSON 입력 수집, 응답 표시 | 추론 로직 없음 |
| 포탈 백엔드 | 인증, URL 검증(SSRF), HTTP 중계, 오류 매핑 | 모델 로드·전처리·예측 **없음** |
| invest-inference | 모델 로드/전처리/추론 전담 | (변경 없음) |

---

## 3. 데이터 모델 (Pydantic v2 스키마)

신규 파일: `app/schemas/inference.py`

```python
from pydantic import BaseModel, Field, field_validator
from typing import Any

class ProxyRequest(BaseModel):
    target_url: str = Field(..., description="추론 API 엔드포인트 URL")
    payload: dict[str, Any] = Field(default_factory=dict, description="추론 요청 JSON")
    host_header: str | None = Field(default=None, description="ALB 라우팅용 Host 헤더 (선택)")
    timeout: int = Field(default=30, ge=1, le=120, description="초 단위 타임아웃")

    @field_validator("target_url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        # 스킴/호스트/SSRF 검증은 서비스 계층 _assert_safe_url에서 수행 (재사용 위해)
        if not v.strip():
            raise ValueError("target_url is required")
        return v.strip()

class ProxyResponse(BaseModel):
    status_code: int
    elapsed_ms: int
    body: Any            # 대상이 JSON이면 dict/list, 아니면 str
    ok: bool             # 2xx 여부
```

> `payload`를 textarea 원문(str)으로 받지 않고 프론트에서 `JSON.parse` 후 객체로 전송한다. 파싱 실패는 프론트에서 1차 차단, 백엔드는 dict로 검증.

---

## 4. API 계약

### 4.1 `POST /api/inference/proxy`

| 항목 | 값 |
|------|-----|
| 인증 | `Depends(get_current_user)` (필수) |
| Content-Type | application/json |
| Request | `ProxyRequest` |
| Response 200 | `ProxyResponse` |

> **✅ DNS 현황**: `api.mlops.click` 도메인 **등록 완료** (인프라팀). 외부 인터넷에서도
> `http://api.mlops.click/predict`로 **직접 호출 가능**하며 `host_header`는 **불필요**(빈 값)하다.
> `host_header` 필드는 도메인 미등록 환경/ALB Host 라우팅 우회용으로 남겨둔다(선택).

**요청 예시 (현재 기본 방식 — 도메인 직접 호출)**
```json
{
  "target_url": "http://api.mlops.click/predict",
  "timeout": 30,
  "payload": {
    "gpt_ivt_jg_seq": "JG_TEST_001",
    "ltv_rte": 65.0, "dbt_rpy_coef_rte": 1.35, "ln_pd": 24.0, "bs_itt": 3.25,
    "gpt_ivt_kd_cd": "오피스빌딩", "gpt_ivt_ser_dv_cd": "오피스", "gpt_ivt_tp_cd": "선순위"
  }
}
```

> 이는 검증된 curl과 동일하다:
> ```bash
> ALB=k8s-sharedalb-0882a5287f-595901001.ap-northeast-2.elb.amazonaws.com
> curl -s -X POST -H "Host: api.mlops.click" http://${ALB}/predict \
>   -H "Content-Type: application/json" -d '{...payload...}'
> ```
> **호출 경로 대안**
> | 방식 | target_url | host_header | 비고 |
> |------|-----------|-------------|------|
> | 도메인 직접 (현재 기본) | `http://api.mlops.click/predict` | 불필요 | 도메인 등록 완료, 외부에서도 호출 |
> | 클러스터 내부 (포탈이 EKS 내부일 때) | `http://invest-inference.mlops.svc.cluster.local:8080/predict` | 불필요 | svc DNS 직접 해석 |
> | ALB + Host (도메인 미등록 환경 fallback) | `http://<ALB>/predict` | `api.mlops.click` | 우회용 |

**응답 예시 (대상 200)**
```json
{
  "status_code": 200,
  "elapsed_ms": 1842,
  "ok": true,
  "body": {
    "request_id": "20260605141910872372",
    "invest_yn": "N", "invest_prob": 0.1882, "fair_rate": 5.9848,
    "cls_model": "invest-crel-classification@champion",
    "reg_model": "invest-crel-regression@champion",
    "inferred_at": "2026-06-05 14:19:12"
  }
}
```

### 4.2 오류 매핑

| 상황 | 포탈 응답 HTTP | 비고 |
|------|----------------|------|
| target_url 누락/형식 오류 | 400 | Pydantic/검증 |
| SSRF 차단(내부 IP·비허용 스킴) | 400 | `_assert_safe_url` |
| 대상 연결 실패 (`httpx.ConnectError`) | 502 | `detail: 추론 서버 연결 오류` |
| 대상 타임아웃 (`httpx.TimeoutException`) | 504 | `detail: 추론 서버 응답 시간 초과` |
| 대상이 4xx/5xx 반환 | **200** (passthrough) | `ok:false`, `status_code`에 원본 코드, `body`에 원본 응답 |
| 비로그인 | 401 | 기존 인증 미들웨어 |

> **설계 결정**: 대상의 비-2xx는 포탈에서 예외로 던지지 않고 200으로 감싸 전달한다. 테스터 도구 특성상 사용자가 원본 status/body를 그대로 봐야 디버깅이 가능하기 때문. 단 *프록시 자체* 실패(연결/타임아웃/검증)는 명확히 4xx/5xx로 구분.

---

## 5. 시퀀스

```
사용자 → [실행] 클릭
  프론트: JSON.parse(textarea)  ──(실패)──▶ 에러카드 "JSON 형식 오류" (백엔드 호출 안 함)
        │ 성공
        ▼
  POST /api/inference/proxy {target_url, payload, host_header, timeout}
        ▼
  라우트: get_current_user 검증
        ▼
  서비스: _assert_safe_url(target_url)  ──(실패)──▶ 400
        │ 통과
        ▼
  httpx.AsyncClient(timeout).post(target_url, json=payload, headers={Host?})
        │            │              │
     ConnectError  Timeout       정상 응답
        │            │              │
       502          504    status/body/elapsed 수집 → ProxyResponse(ok=2xx여부)
        ▼
  프론트: status_code 배지 + elapsed_ms + body pretty-print
```

---

## 6. 보안 설계 (SSRF 방어)

`_assert_safe_url(url: str)` — 서비스 계층, 호출 전 검증:

| 규칙 | 내용 |
|------|------|
| 스킴 화이트리스트 | `http`, `https`만 허용 |
| 메타데이터 차단 | 호스트가 `169.254.169.254`(AWS IMDS), `localhost`/`127.0.0.0/8`(설정으로 허용 가능) 차단 |
| 사설망 정책 | 기본 허용(클러스터 내부 svc DNS 호출 필요) — 단, IMDS만 명시 차단 |
| (선택) 허용 호스트 prefix | `config.inference_allowed_hosts` 설정 시 해당 도메인만 허용 (운영 강화용, 기본 빈 값=전체 허용) |

> 본 도구는 사내 로그인 사용자 전용 + 클러스터 내부 호출 필요성 때문에 전면 화이트리스트는 기본 비활성. IMDS 차단과 스킴 제한을 최소 안전장치로 둔다. 운영 강화 시 `inference_allowed_hosts`로 좁힌다.

---

## 7. 파일별 변경 설계

### 7.1 `app/services/inference_service.py` — 전면 재작성

**삭제**: `NUMERIC_COLS/CAT_COLS/FEATURE_COLS`, 전역 `_clf/_reg/_le_dict/_le_target/_medians`, `_setup_mlflow/_load_encoders/_get_models/_preprocess`, `InferenceService` 클래스 전체, mlflow/xgboost/pandas/joblib/numpy import.

**신규**:
```python
import time, ipaddress
from urllib.parse import urlparse
import httpx
from app.core.config import get_settings

class InferenceProxyService:
    @staticmethod
    def _assert_safe_url(url: str) -> None:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            raise ValueError("http/https URL만 허용됩니다.")
        if not p.hostname:
            raise ValueError("유효한 호스트가 없습니다.")
        if p.hostname == "169.254.169.254":
            raise ValueError("허용되지 않은 호스트입니다.")
        allowed = get_settings().inference_allowed_hosts  # list[str], 빈 값=전체 허용
        if allowed and not any(p.hostname == h or p.hostname.endswith("." + h) for h in allowed):
            raise ValueError("허용되지 않은 호스트입니다.")

    async def proxy(self, target_url: str, payload: dict,
                    host_header: str | None = None, timeout: int = 30) -> dict:
        self._assert_safe_url(target_url)
        headers = {"Content-Type": "application/json"}
        if host_header:
            headers["Host"] = host_header
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(target_url, json=payload, headers=headers)
        elapsed = int((time.perf_counter() - start) * 1000)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {"status_code": resp.status_code, "elapsed_ms": elapsed,
                "ok": resp.is_success, "body": body}
```

### 7.2 `app/api/routes/inference.py` — 재작성

```python
from fastapi import APIRouter, Depends, HTTPException
import httpx
from app.api.deps import get_current_user
from app.schemas.auth import UserRead
from app.schemas.inference import ProxyRequest, ProxyResponse
from app.services.inference_service import InferenceProxyService

router = APIRouter(prefix="/inference", tags=["inference"])

@router.post("/proxy", response_model=ProxyResponse)
async def proxy(req: ProxyRequest, _: UserRead = Depends(get_current_user)):
    svc = InferenceProxyService()
    try:
        return await svc.proxy(req.target_url, req.payload, req.host_header, req.timeout)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"추론 서버 연결 오류: {e}") from e
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504, detail="추론 서버 응답 시간 초과") from e
```

**제거**: 기존 `/health`, `/model/info`, `/predict` 엔드포인트 (자체 추론 기반). 프론트 의존성 정리 후 삭제.

### 7.3 `app/core/config.py` — 설정 정리

```python
# 신규
inference_base_url: str = Field(
    # api.mlops.click 도메인 등록 완료 → 직접 호출 (Host 헤더 불필요)
    default="http://api.mlops.click/predict",
    alias="INFERENCE_BASE_URL")          # 폼 기본 URL (web.py:74 참조 버그 동시 해결)
inference_default_host: str = Field(
    default="", alias="INFERENCE_DEFAULT_HOST")  # 폼 Host 헤더 기본값(빈 값, 우회 시만 사용)
inference_allowed_hosts: list[str] = Field(
    default_factory=list, alias="INFERENCE_ALLOWED_HOSTS")  # 빈 값=전체 허용

# 제거 검토 (타 라우트 미사용 확인됨 — inference_service 전용)
# mlflow_tracking_uri / mlflow_tracking_username / mlflow_tracking_password
# mlflow_cls_model / mlflow_reg_model / mlflow_model_stage
```
> `mlflow_base_url/username/password`(config.py:35-37)는 `mlflow_proxy` 라우트에서 쓰일 수 있으므로 **유지**. `mlflow_tracking_*` 및 모델명/stage는 추론 전용이었으면 제거. Do 단계에서 `grep mlflow_tracking_/mlflow_cls_model` 재확인 후 삭제.

### 7.4 `app/templates/pages/inference.html` — 전면 재작성 (범용 테스터)

| 영역 | 요소 |
|------|------|
| 추론 URL | `<input id="f-url">` 기본값 `{{ inference_url }}` |
| Host 헤더 | `<input id="f-host" value="{{ inference_host }}">` (DNS 미등록 상태에선 필수, 기본값 채워둠) |
| 요청 JSON | `<textarea id="f-json">` 샘플 프리필 + "샘플 채우기" 버튼 |
| 실행 | `<button onclick="runProxy()">추론 실행</button>` |
| 응답 | status 배지 + `elapsed_ms` + `<pre id="res-json">` pretty-print |
| 오류 | 에러 카드 (JSON 파싱 오류 / 프록시 오류 구분) |

```javascript
async function runProxy() {
  let payload;
  try { payload = JSON.parse(document.getElementById('f-json').value); }
  catch(e) { showError('요청 JSON 형식 오류: ' + e.message); return; }
  const body = {
    target_url: document.getElementById('f-url').value.trim(),
    host_header: document.getElementById('f-host').value.trim() || null,
    payload, timeout: 30
  };
  const res = await apiFetch('/api/inference/proxy', {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)
  });
  const d = await res.json();
  if (!res.ok) { showError(d.detail || JSON.stringify(d)); return; }
  showResult(d);  // status_code 배지 + elapsed_ms + JSON.stringify(d.body, null, 2)
}
```

### 7.5 `app/api/routes/web.py` — 수정 (컨텍스트 추가)

```python
@router.get("/aiml/inference", ...)
async def inference_page(request: Request):
    s = get_settings()
    return templates.TemplateResponse("pages/inference.html", {
        "request": request, "active_page": "inference",
        "inference_url": s.inference_base_url,      # config 추가로 기존 버그 해결
        "inference_host": s.inference_default_host, # Host 헤더 기본값 (api.mlops.click)
    })
```

### 7.6 `requirements.txt` — ML 의존성 제거

```diff
- mlflow>=2.10.0
- pandas>=2.0.0
- xgboost>=2.0.0
- joblib>=1.3.0
```
> 전 코드베이스에서 inference_service.py 전용 확인됨. `mlflow_proxy` 라우트는 HTTP 프록시(httpx)이지 mlflow SDK 미사용인지 Do 단계 재확인 후 제거.

---

## 8. 테스트 설계

신규: `tests/test_inference_proxy.py` (httpx mock — `respx` 또는 `monkeypatch`)

| # | 케이스 | 기대 |
|---|--------|------|
| 1 | 정상 프록시 (mock 200) | `status_code=200, ok=true, body=dict` |
| 2 | 대상 422 passthrough | 포탈 200, `ok=false, status_code=422` |
| 3 | 대상 500 passthrough | 포탈 200, `ok=false, status_code=500` |
| 4 | ConnectError | 포탈 502 |
| 5 | TimeoutException | 포탈 504 |
| 6 | 비-http 스킴 (`file://`) | 400 |
| 7 | IMDS 호스트 (169.254.169.254) | 400 |
| 8 | 허용 호스트 제한 위반 | 400 (allowed_hosts 설정 시) |
| 9 | 비로그인 호출 | 401 |
| 10 | 비-JSON 응답(text) | `body`가 문자열로 전달 |
| 11 | host_header 전달 | mock 요청에 `Host: api.mlops.click` 헤더 포함 확인 (ALB 라우팅 검증) |

**통합(수동)**: 포탈 `/aiml/inference` → `target_url=http://api.mlops.click/predict`, `host_header=api.mlops.click`, 샘플 JSON → invest 응답 표시 확인.

---

## 9. 구현 순서

1. `app/schemas/inference.py` 생성 (ProxyRequest/ProxyResponse)
2. `app/core/config.py` 설정 추가/정리
3. `app/services/inference_service.py` 전면 재작성 (InferenceProxyService)
4. `app/api/routes/inference.py` 재작성 (/proxy)
5. `app/templates/pages/inference.html` 범용 테스터로 재작성
6. `requirements.txt` ML 의존성 제거
7. `tests/test_inference_proxy.py` 작성
8. 단위 테스트 + 포탈 구동 통합 검증

---

## 10. 완료 기준 매핑 (Plan §8 대응)

| Plan 완료 기준 | Design 충족 항목 |
|----------------|------------------|
| 모델 직접 로딩 코드 0건 | §7.1 전면 삭제 |
| `/api/inference/proxy` 동작 | §4, §7.2 |
| 실제 invest-inference 호출 성공 | §8 통합 + host_header 설계 |
| ML 의존성 제거 | §7.6 (전용 사용 확인) |
| 범용 테스터 UI | §7.4 |

---

## 11. 미해결/Do 단계 확인 항목

- [ ] `mlflow_proxy` 라우트가 mlflow SDK를 import하는지 확인 후 requirements 제거 범위 확정
- [ ] `config.mlflow_tracking_*` 타 사용처 grep 확인 후 제거
- [ ] `apiFetch` 헬퍼의 401 처리/리다이렉트 동작 확인 (base.html)
- [ ] 기존 `/api/inference/health|model/info|predict` 호출처 잔존 여부 grep
