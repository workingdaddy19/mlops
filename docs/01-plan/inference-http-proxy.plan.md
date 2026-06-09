# [Plan] MLOps 포탈 추론 API — HTTP 프록시 전환 (전면 재개발)

## Executive Summary

| 항목 | 내용 |
|------|------|
| Feature | inference-http-proxy |
| 작성일 | 2026-06-05 |
| 최종 수정 | 2026-06-05 |
| 목표 완료일 | 2026-06-09 (2 영업일) |
| 대상 프로젝트 | `d:\ADT\workspace\mlops` (MLOps 포탈) — **호출자(client)만 변경** |
| 호출 대상 | **invest-app 프로젝트 서비스 (별도 Pod)** — `d:\ADT\workspace\mlapi` 산출물, EKS 배포 완료, **수정 없음** |
| 상태 | **Plan** |

> **명칭 정리**: "invest-app 프로젝트"는 추론을 전담하는 별도 애플리케이션이다. 서버/ECR 이미지명은 `invest-app`(`~/invest-app/`), K8s Deployment·Service 명은 `invest-inference`, Windows 개발 원본은 `d:\ADT\workspace\mlapi`. 본 문서에서 "invest-app 서비스" = "invest-inference Pod"는 **동일 대상**을 가리킨다.

### Value Delivered (4-perspective)

| 관점 | 내용 |
|------|------|
| **Problem** | MLOps 포탈이 추론을 **자체 처리**한다. `inference_service.py`가 MLflow XGBoost 모델을 직접 로드하고 인코더·전처리·`predict_proba`를 재구현 → 이미 배포된 invest-inference Pod 로직을 **중복**하고, 포탈에 mlflow/xgboost/joblib/pandas 무거운 의존성을 강제하며, FEATURE_COLS·전처리 로직이 두 곳에서 따로 관리되어 모델 변경 시 동기화 깨짐 위험 |
| **Solution** | 포탈의 **자체 추론(self-processing) 기능을 전면 제거**하고, **다른 Pod에 배포된 invest-app 프로젝트 서비스를 HTTP로 호출**하는 얇은 프록시로 전환. 브라우저가 입력한 **추론 API URL**로 MLOps 백엔드가 JSON 페이로드를 POST 중계하고 JSON 응답을 그대로 반환 |
| **Function UX Effect** | 추론 테스트 페이지를 **범용 API 테스터**로 재구성: ① 추론 URL 입력칸 ② JSON 요청 textarea ③ JSON 응답 뷰어. 어떤 추론 엔드포인트든 URL만 바꿔 검증 가능 |
| **Core Value** | 단일 책임(Pod=추론 / 포탈=호출)으로 중복 제거, 포탈에서 ML 의존성 5종 삭제로 경량화, ALB `/predict` 실제 호출로 기능 검증 완료(curl 통과 확인) |

---

## 1. 개요

### 1.1 목적

MLOps 포탈의 추론 기능을 **자체 추론 서버(self-processing) 방식 → 다른 Pod의 invest-app 서비스 HTTP 호출(프록시) 방식**으로 전면 재개발한다.

- 포탈은 더 이상 모델을 로드하거나 추론을 **자체 처리하지 않는다**.
- 추론은 **별도 Pod에 배포된 invest-app 프로젝트 서비스(=invest-inference Deployment)**가 전담하며, 포탈은 이 서비스를 **호출만** 한다.
- 포탈은 사용자가 입력한 **추론 API URL**로 **JSON POST**를 보내고 **JSON 응답**을 표시하는 역할만 한다.
- invest-app 프로젝트(`d:\ADT\workspace\mlapi`) 및 Pod는 **본 작업 범위에서 수정하지 않는다** (이미 배포·검증 완료).

### 1.2 배경 — 현재 구현의 문제 (As-Is)

| 위치 | 현재 동작 | 문제 |
|------|----------|------|
| `app/services/inference_service.py` | `mlflow.xgboost.load_model()`으로 분류/회귀 모델 직접 로드, `encoders/` 아티팩트 다운로드, `_preprocess()`로 전처리, `predict`/`predict_proba` 실행 | invest-inference Pod 로직 **완전 중복**. 포탈이 곧 추론 서버 |
| 의존성 | mlflow, mlflow.xgboost, joblib, pandas, numpy, sklearn | 포탈 컨테이너에 불필요한 무거운 ML 스택 강제 |
| `FEATURE_COLS`/`NUMERIC_COLS`/`CAT_COLS` | Pod와 포탈에 각각 하드코딩 | 모델 피처 변경 시 두 곳 동기화 필요 → 누락 위험 |
| `app/templates/pages/inference.html` | INVEST 전용 15개 입력 필드 하드코딩 | invest 스키마에 강결합, 다른 모델/엔드포인트 테스트 불가 |

### 1.3 목표 상태 (To-Be)

```
[브라우저] 추론 테스트 페이지
   ├─ 추론 API URL 입력 (예: http://<ALB>/predict, http://invest-inference.mlops.svc.cluster.local:8080/predict)
   ├─ 요청 JSON (textarea)
   └─ POST /api/inference/proxy  { "target_url": "...", "payload": {...} }
        │
[MLOps 백엔드] InferenceProxyService (httpx)
        │  POST {target_url}  body={payload}
        ▼
[다른 Pod: invest-app 서비스 = invest-inference] /predict   → JSON 응답
        │   (수정 없음 / 추론 전담)
        ▼
   JSON 응답 뷰어에 그대로 표시
```

### 1.4 설계 결정 (사용자 확인 완료)

| 결정 항목 | 선택 | 사유 |
|-----------|------|------|
| 호출 구조 | **백엔드 프록시** | CORS 회피, 클러스터 내부 DNS·외부 ALB 모두 호출 가능, 인증/타임아웃 일관 처리 |
| 기존 모델 로딩 코드 | **완전 제거** | 중복 제거, 포탈 경량화 (ML 의존성 5종 삭제) |
| 입력 UI | **범용 테스터** | URL 입력 + JSON 요청 textarea + JSON 응답 뷰어 (+ 샘플 채우기 버튼) |

---

## 2. 기술 스택

| 구분 | 기술 | 비고 |
|------|------|------|
| 백엔드 | FastAPI (기존 포탈) | 기존 라우터 구조 재사용 |
| HTTP 클라이언트 | **httpx (AsyncClient)** | 비동기 POST 중계, 타임아웃 설정 |
| 데이터 검증 | Pydantic v2 | `ProxyRequest` 스키마 |
| 프론트 | Jinja2 + Vanilla JS | 기존 `inference.html` 재작성 |
| 제거 대상 | mlflow, mlflow.xgboost, joblib, pandas, numpy(추론 한정), sklearn | 포탈에서 추론용 사용처 삭제 |

> httpx는 포탈에 이미 존재 여부 확인 필요. 없으면 requirements에 추가(경량). 제거되는 ML 스택 대비 순감소.

---

## 3. 변경 파일 목록

### 3.1 백엔드

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/services/inference_service.py` | **전면 재작성** | 모델 로딩/전처리/예측 전부 삭제 → `InferenceProxyService` (httpx로 임의 URL에 JSON POST 중계). `health`는 선택적으로 `{target_url}` 기반 GET 또는 제거 |
| `app/api/routes/inference.py` | **재작성** | `/api/inference/proxy` (POST) 단일 핵심 엔드포인트. 기존 `/predict`, `/model/info`, `/health`는 프록시 기반으로 단순화 또는 제거 |
| `app/schemas/` (신규 or 인라인) | 신규 | `ProxyRequest { target_url: str, payload: dict, timeout?: int }`, `ProxyResponse { status_code, body, elapsed_ms }` |
| `app/core/config.py` | 수정 | `mlflow_cls_model`/`mlflow_reg_model`/`mlflow_model_stage` 중 추론 전용 설정 정리. `INFERENCE_DEFAULT_URL`(기본 추론 URL, 폼 placeholder용) 추가 |
| `requirements.txt` | 수정 | httpx 보장, 추론용 mlflow/xgboost/joblib 등 미사용 시 정리 |

### 3.2 프론트엔드

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/templates/pages/inference.html` | **전면 재작성** | INVEST 전용 폼 삭제 → ① 추론 URL 입력 ② 요청 JSON textarea ③ JSON 응답 뷰어 ④ 샘플 JSON 채우기 버튼 ⑤ 상태/에러 표시 |
| `app/templates/base.html` | 유지 | 사이드바 Inference Test 메뉴 그대로 (라우트 변경 없음) |
| `app/api/routes/web.py` | 유지/수정 | `/aiml/inference` 페이지 라우트 유지, `inference_url` 컨텍스트 → 기본 URL 전달 |

### 3.3 mlapi 프로젝트 (invest-inference) — 변경 없음

invest-inference Pod 자체는 **수정 대상 아님**. 이미 EKS 배포·검증 완료. 본 작업은 포탈(호출자)만 변경.

---

## 4. API 명세 (To-Be)

### 4.1 POST `/api/inference/proxy` (핵심, 신규)

**Request**
```json
{
  "target_url": "http://k8s-sharedalb-0882a5287f-595901001.ap-northeast-2.elb.amazonaws.com/predict",
  "payload": {
    "gpt_ivt_jg_seq": "JG_TEST_001",
    "ltv_rte": 65.0,
    "dbt_rpy_coef_rte": 1.35,
    "ln_pd": 24.0,
    "bs_itt": 3.25,
    "gpt_ivt_kd_cd": "오피스빌딩",
    "gpt_ivt_ser_dv_cd": "오피스",
    "gpt_ivt_tp_cd": "선순위"
  },
  "timeout": 30
}
```

**Response 200** (대상 응답을 그대로 래핑)
```json
{
  "status_code": 200,
  "elapsed_ms": 1842,
  "body": {
    "request_id": "20260605141910872372",
    "gpt_ivt_jg_seq": "JG_TEST_001",
    "invest_yn": "N",
    "invest_prob": 0.1882,
    "fair_rate": 5.9848,
    "cls_model": "invest-crel-classification@champion",
    "reg_model": "invest-crel-regression@champion",
    "inferred_at": "2026-06-05 14:19:12"
  }
}
```

**오류 처리**

| HTTP | 원인 | 응답 |
|------|------|------|
| 400 | `target_url` 누락/형식 오류, payload JSON 파싱 실패 | `{ "detail": "..." }` |
| 502 | 대상 추론 서버 연결 실패 | `{ "detail": "추론 서버 연결 오류: ..." }` |
| 504 | 대상 서버 타임아웃 | `{ "detail": "추론 서버 응답 시간 초과" }` |
| (passthrough) | 대상이 4xx/5xx 반환 | `status_code`에 대상 코드 그대로, `body`에 대상 응답 |

> 대상 서버가 비-2xx를 반환해도 프록시 자체는 200으로 감싸 `status_code`/`body`를 전달 → 테스터가 원본 응답을 그대로 확인 가능.

### 4.2 인증

기존과 동일하게 `Depends(get_current_user)` 적용 (포탈 로그인 사용자만 호출).

### 4.3 보안 (SSRF 고려)

임의 URL POST 중계는 SSRF 위험이 있으므로:
- 허용 호스트 화이트리스트(설정값) 또는 사내/클러스터 도메인 prefix 검증 권장 (Design 단계에서 확정)
- 최소한 `http/https` 스킴만 허용, 내부 메타데이터 IP(169.254.169.254) 차단

---

## 5. 구현 상세

### 5.1 InferenceProxyService (httpx 기반)

```
async def proxy(target_url, payload, timeout) -> dict:
    1. URL 스킴/호스트 검증 (보안)
    2. httpx.AsyncClient(timeout) 로 POST target_url, json=payload
    3. 응답 status_code, elapsed, body(json 우선, 실패 시 text) 수집
    4. { status_code, elapsed_ms, body } 반환
    예외: ConnectError→502, TimeoutException→504
```

### 5.2 제거 항목 (자체 추론 기능 완전 삭제)

- `_setup_mlflow`, `_load_encoders`, `_get_models`, `_preprocess`
- 전역 캐시 `_clf/_reg/_le_dict/_le_target/_medians`
- `NUMERIC_COLS/CAT_COLS/FEATURE_COLS` 상수
- 관련 import: mlflow, mlflow.xgboost, joblib, pandas, numpy, MlflowClient

### 5.3 프론트 재구성 (범용 테스터)

| 영역 | 구성 |
|------|------|
| 추론 URL | text input (기본값: `INFERENCE_DEFAULT_URL` placeholder) |
| 요청 JSON | textarea (기본 샘플 JSON 프리필 + "샘플 채우기" 버튼) |
| 실행 | "추론 실행" → `POST /api/inference/proxy` |
| 응답 | `<pre>` JSON pretty-print, status_code/elapsed_ms 배지 |
| 오류 | 에러 카드에 detail 표시 |

---

## 6. 테스트 계획

### 6.1 검증 기준 (실제 배포 엔드포인트)

이미 통과 확인된 호출 (Plan 근거):
```bash
ALB=k8s-sharedalb-0882a5287f-595901001.ap-northeast-2.elb.amazonaws.com
curl -s -X POST -H "Host: api.mlops.click" http://${ALB}/predict \
  -H "Content-Type: application/json" \
  -d '{"gpt_ivt_jg_seq":"JG_TEST_001","ltv_rte":65.0,...}'
# → {"invest_yn":"N","invest_prob":0.1882,"fair_rate":5.9848,...}
```

> 참고: 위 curl은 `Host: api.mlops.click` 헤더로 ALB 라우팅됨. 프록시가 Host 헤더 지정 가능해야 함 (선택 입력 또는 target_url을 `http://api.mlops.click/predict`로 DNS 해석되게 사용). Design에서 Host 헤더 처리 방식 확정.

### 6.2 단위 테스트 (`tests/test_inference_proxy.py`)

| 케이스 | 검증 |
|--------|------|
| 정상 프록시 | httpx mock 200 → `{status_code:200, body:{...}}` |
| 대상 4xx passthrough | mock 422 → status_code=422 전달 |
| 연결 실패 | ConnectError → 502 |
| 타임아웃 | TimeoutException → 504 |
| URL 검증 | 잘못된 스킴/내부 IP → 400 |
| 인증 누락 | 비로그인 → 401 |

### 6.3 통합 테스트 (수동)

- 포탈 `/aiml/inference` 접속 → URL+JSON 입력 → 실제 invest-inference 응답 표시 확인

---

## 7. 작업 순서 (Do 단계 체크리스트)

- [ ] httpx 의존성 확인/추가, requirements에서 추론용 ML 스택 사용처 점검
- [ ] `app/schemas` 에 `ProxyRequest`/`ProxyResponse` 정의
- [ ] `inference_service.py` → `InferenceProxyService`로 전면 재작성 (모델 로딩 코드 삭제)
- [ ] `routes/inference.py` → `/proxy` 엔드포인트 재작성, 불필요 엔드포인트 정리
- [ ] `config.py` → `INFERENCE_DEFAULT_URL` 추가, 미사용 mlflow 추론 설정 정리
- [ ] `inference.html` 범용 테스터로 재작성
- [ ] `web.py` 컨텍스트(기본 URL) 점검
- [ ] 단위 테스트 작성 및 통과
- [ ] 포탈 구동 → 실제 ALB 엔드포인트로 통합 검증

---

## 8. 완료 기준

| 기준 | 검증 방법 | 상태 |
|------|----------|------|
| 포탈에서 모델 직접 로딩 코드 0건 | `grep mlflow.xgboost.load_model app/` 결과 없음 | ⏳ |
| `/api/inference/proxy` 정상 동작 | 단위 테스트 PASS | ⏳ |
| 실제 invest-inference 호출 성공 | 포탈 UI에서 JSON 응답 표시 | ⏳ |
| ML 의존성 제거 | requirements/임포트에서 추론용 mlflow·xgboost·joblib 사용처 제거 | ⏳ |
| 범용 테스터 UI | URL 입력 + JSON 요청 + JSON 응답 동작 | ⏳ |

---

## 9. 리스크 및 고려사항

| 리스크 | 영향 | 대응 |
|--------|------|------|
| SSRF (임의 URL POST) | 보안 | 스킴/호스트 검증, 내부 메타데이터 IP 차단, (선택) 화이트리스트 |
| ALB Host 헤더 라우팅 | 호출 실패 | 프록시에서 Host 헤더 지정 옵션 또는 정식 도메인 URL 사용 |
| httpx 미존재 | 빌드 | requirements 추가 (경량, ML 스택 제거로 순감소) |
| 기존 `/predict` 호출처 잔존 | 회귀 | base.html·web.py·기타 참조 grep 확인 후 정리 |

---

## 10. 참고 파일

| 파일 | 설명 |
|------|------|
| `app/services/inference_service.py` | 재작성 대상 (현재 자체 추론) |
| `app/api/routes/inference.py` | 재작성 대상 |
| `app/templates/pages/inference.html` | 재작성 대상 |
| `docs/01-plan/INVEST_API_설계문서.md` | invest-inference 설계 원문 |
| `docs/03-guide/invest-inference-operations.md` | 운영 가이드 (실제 배포 현황, ALB/엔드포인트) |
| `d:\ADT\workspace\mlapi\inference.py` | invest-inference Pod 소스 (호출 대상, 수정 없음) |

---

## 11. 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-06-05 | v1.0 | 최초 계획서 — 포탈 추론을 자체 서버 → HTTP 프록시로 전면 전환 |
| 2026-06-05 | v1.1 | 호출 대상 명칭 정리(invest-app 프로젝트 서비스 = invest-inference, 별도 Pod) 및 "자체 처리 X / 타 Pod 서비스 호출 O" 의도 명확화 (§Executive Summary, §1.1, To-Be 다이어그램) |
