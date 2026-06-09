# INVEST 추론 API — 운영 가이드

**버전:** 1.0.0 | **작성일:** 2026-06-05 | **최종 배포:** 2026-06-05

---

## 1. 서비스 개요

### 1.1 목적

부동산담보대출 투자적격 심사 AI 모델 2종을 FastAPI로 서빙하는 독립 추론 서버.  
업무시스템 및 MLops 포탈에서 REST API 호출로 실시간 심사 결과를 받는다.

| 모델 | 역할 | MLflow 이름 |
|------|------|-------------|
| 분류 모델 | 투자적격 여부 (Y/N) + 확률 | `invest-crel-classification@champion` |
| 회귀 모델 | 적정 금리/수익률 (%) | `invest-crel-regression@champion` |

### 1.2 실제 배포 현황 (2026-06-05 기준)

| 항목 | 설계 초안 | 실제 배포 |
|------|----------|----------|
| Namespace | `invest-inference` (신규) | `mlops` (기존 공유) |
| ECR 이미지 | `invest-inference` | `invest-app` |
| ECR URI | - | `891376975666.dkr.ecr.ap-northeast-2.amazonaws.com/invest-app:latest` |
| Replicas | 2 | 2 |
| readinessProbe delay | 30s | **180s** (모델 로딩 시간 고려) |
| livenessProbe delay | 60s | **300s** |
| ServiceAccount | `invest-inference-sa` (IRSA) | `invest-inference-sa` (권한 없어 default SA 동작) |

---

## 2. 인프라 구성

```
┌─────────────────────────────────────────────────────┐
│  AWS EKS Cluster                                    │
│  ┌─────────────────┐     ┌─────────────────────┐   │
│  │  mlops namespace │     │  mlflow namespace   │   │
│  │                 │     │                     │   │
│  │ invest-inference│────▶│ mlflow (port 80)    │   │
│  │ Pod (x2)        │     │ http://mlflow.mlflow│   │
│  │ port: 8080      │     │ .svc.cluster.local  │   │
│  └────────┬────────┘     └─────────────────────┘   │
│           │ ClusterIP Service                        │
│           │ invest-inference:8080                    │
└───────────┼─────────────────────────────────────────┘
            │
   (kubectl port-forward 또는 Ingress)
            │
    업무시스템 / MLops 포탈 / 테스트 클라이언트
```

### K8s 리소스 목록

```bash
# 확인 명령
kubectl get deployment,svc,hpa -n mlops | grep invest
```

| 리소스 | 이름 | 상태 |
|--------|------|------|
| Deployment | `invest-inference` | 2/2 Running |
| Service | `invest-inference` | ClusterIP:8080 |
| HPA | `invest-inference-hpa` | min=2, max=10, CPU=60% |
| Secret | `mlflow-auth` | username/password |
| ServiceAccount | `invest-inference-sa` | (IRSA 미연결, S3 로그 비활성) |

---

## 3. API 명세

### Base URL

| 환경 | URL |
|------|-----|
| 클러스터 내부 | `http://invest-inference.mlops.svc.cluster.local:8080` |
| 로컬 테스트 (port-forward) | `http://localhost:8080` |
| Ingress (미구성) | 추후 설정 필요 |

### 엔드포인트 목록

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 서버/모델 상태 (K8s readinessProbe) |
| GET | `/model/info` | 현재 로드 모델 정보 |
| POST | `/model/reload` | champion 모델 핫 리로드 |
| POST | `/predict` | **추론 — 핵심 엔드포인트** |
| GET | `/ui` | 내장 테스트 UI (브라우저) |
| GET | `/docs` | FastAPI Swagger UI |

---

### `GET /health`

```bash
curl http://localhost:8080/health
```

```json
{
  "status": "ok",
  "model_loaded": true,
  "loaded_at": "2026-06-05 13:10:09"
}
```

---

### `GET /model/info`

```bash
curl http://localhost:8080/model/info
```

```json
{
  "mlflow_uri": "http://mlflow.mlflow.svc.cluster.local:80",
  "cls_model": "invest-crel-classification",
  "reg_model": "invest-crel-regression",
  "alias": "champion",
  "loaded_at": "2026-06-05 13:10:09"
}
```

---

### `POST /predict` ★

**Request 필드**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `gpt_ivt_jg_seq` | string | ✅ | 투자심사 일련번호 (추적 키) |
| `ltv_rte` | float | | LTV (%) |
| `dbt_rpy_coef_rte` | float | | DSCR |
| `ln_pd` | float | | 대출기간 (월) |
| `bs_itt` | float | | 기준금리 (%) |
| `gpt_ivt_etrm_rte` | float | | 공실률 (%) |
| `gpt_ivt_rmd_lsg_ycn` | float | | 잔여임대차기간 (년) |
| `gpt_ivt_dlb_rqt_amt` | float | | 심의요청금액 (원) |
| `gpt_ivt_ln_pfat_txt` | float | | Debt Yield (%) |
| `gpt_ivt_mkt_avg_cpt_rte` | float | | Cap Rate 시장평균 (%) |
| `gpt_ivt_kd_cd` | string | | 물건구분 |
| `gpt_ivt_ser_dv_cd` | string | | 투자섹터 |
| `gpt_ivt_tp_cd` | string | | 투자유형 |
| `gpt_ivt_mth_cd` | string | | 투자방법 |
| `gpt_ivt_ara_dv_cd` | string | | 지역구분 |
| *(기타 29개 컬럼)* | float/string | | 모두 Optional (없으면 0 또는 해시 처리) |

**Request 예시**

```json
{
  "gpt_ivt_jg_seq": "JG20260605001",
  "ltv_rte": 65.0,
  "dbt_rpy_coef_rte": 1.35,
  "ln_pd": 24.0,
  "bs_itt": 3.25,
  "gpt_ivt_etrm_rte": 5.0,
  "gpt_ivt_rmd_lsg_ycn": 3.5,
  "gpt_ivt_dlb_rqt_amt": 50000000000,
  "gpt_ivt_kd_cd": "오피스빌딩",
  "gpt_ivt_ser_dv_cd": "오피스",
  "gpt_ivt_tp_cd": "선순위",
  "gpt_ivt_mth_cd": "직접",
  "gpt_ivt_ara_dv_cd": "국내"
}
```

**Response 200**

```json
{
  "request_id":     "20260605131610047096",
  "gpt_ivt_jg_seq": "JG20260605001",
  "invest_yn":      "Y",
  "invest_prob":    0.7821,
  "fair_rate":      5.9848,
  "cls_model":      "invest-crel-classification@champion",
  "reg_model":      "invest-crel-regression@champion",
  "inferred_at":    "2026-06-05 13:16:11"
}
```

| 응답 필드 | 설명 |
|-----------|------|
| `invest_yn` | `Y` = 투자적격, `N` = 부적격 |
| `invest_prob` | 적격 확률 0.0~1.0 (보조 참고) |
| `fair_rate` | AI 추천 적정금리 (%) |

**오류 응답**

| HTTP | 원인 | 대응 |
|------|------|------|
| 422 | `gpt_ivt_jg_seq` 누락 | 필수 필드 확인 |
| 503 | 모델 미로드 | Pod 상태/로그 확인 |
| 500 | 전처리/추론 오류 | 로그 확인 |

---

## 4. 타시스템 연계 방법

### 4.1 업무시스템 → 추론 API 직접 호출

클러스터 내부에서 직접 호출 (Ingress 불필요):

```
http://invest-inference.mlops.svc.cluster.local:8080/predict
```

**Python 예시**

```python
import requests

response = requests.post(
    "http://invest-inference.mlops.svc.cluster.local:8080/predict",
    json={
        "gpt_ivt_jg_seq": "JG20260605001",
        "ltv_rte": 65.0,
        "dbt_rpy_coef_rte": 1.35,
        "bs_itt": 3.25,
        "gpt_ivt_kd_cd": "오피스빌딩"
    },
    timeout=30
)
result = response.json()
print(f"투자적격: {result['invest_yn']}, 금리: {result['fair_rate']}%")
```

**Java 예시**

```java
HttpClient client = HttpClient.newHttpClient();
String body = """
    {"gpt_ivt_jg_seq":"JG001","ltv_rte":65.0,"bs_itt":3.25}
    """;
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("http://invest-inference.mlops.svc.cluster.local:8080/predict"))
    .header("Content-Type", "application/json")
    .POST(HttpRequest.BodyPublishers.ofString(body))
    .build();
HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
```

### 4.2 MLops 포탈에서 호출

MLops 포탈 백엔드에 InferenceService 구현 완료 (`app/services/inference_service.py`).

**포탈 내 테스트 UI 접근:**

```
http://mlops-portal-url/aiml/inference
```

포탈 → `POST /api/inference/predict` → InferenceService(httpx) → 추론 Pod

**포탈 환경변수 설정 (`INFERENCE_BASE_URL`):**

```
INFERENCE_BASE_URL=http://invest-inference.mlops.svc.cluster.local:8080
```

### 4.3 외부 시스템 (Ingress 미구성 시 포트포워드로 테스트)

```bash
# 개발/테스트 시
kubectl port-forward svc/invest-inference 8080:8080 -n mlops

# Windows에서 원격 서버 SSH 터널
ssh -L 8080:localhost:8080 mlops_user@<서버IP> -N
# → 브라우저: http://localhost:8080/ui
```

---

## 5. 기동 및 재시작

### 5.1 정상 상태 확인

```bash
# Pod 상태 (2/2 Running이 정상)
kubectl get pods -n mlops | grep invest

# 헬스 체크
kubectl exec -n mlops deployment/invest-inference \
  -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/health').read().decode())"
```

### 5.2 배포/재배포

```bash
# 이미지 재빌드 + ECR 푸시 + K8s 재배포 (전체)
cd /home/mlops_user/invest-app
bash deploy.sh

# K8s 재배포만 (이미지 변경 없이)
bash deploy.sh --deploy

# 이미지 재빌드 + ECR 푸시만
bash deploy.sh --build

# 강제 재시작 (Pod 재생성)
kubectl rollout restart deployment/invest-inference -n mlops
kubectl rollout status deployment/invest-inference -n mlops
```

### 5.3 배포 소요 시간

| 단계 | 소요 시간 |
|------|----------|
| Docker 빌드 | ~130초 |
| ECR 푸시 | ~30초 |
| Pod 시작 (readinessProbe 대기) | **~3분** (모델 로딩 포함) |
| 전체 | **~6분** |

> Pod readinessProbe initialDelaySeconds=180 — MLflow 모델 로딩 시간 확보

---

## 6. 모델 관리

### 6.1 champion alias 확인

```bash
pip install mlflow -q  # 서버에 mlflow 없을 경우

python3 - << 'EOF'
import mlflow, os
mlflow.set_tracking_uri("http://mlflow.mlflow.svc.cluster.local:80")
os.environ["MLFLOW_TRACKING_USERNAME"] = "admin"
os.environ["MLFLOW_TRACKING_PASSWORD"] = "xxxx"
client = mlflow.tracking.MlflowClient()
for name in ["invest-crel-classification", "invest-crel-regression"]:
    versions = client.search_model_versions(f"name='{name}'")
    print(f"\n{name}:")
    for v in versions:
        aliases = client.get_model_version(name, v.version).aliases
        print(f"  v{v.version} | aliases={aliases}")
EOF
```

### 6.2 새 모델 버전으로 교체 (재배포 불필요)

```bash
# 방법 1: MLflow UI에서 직접 설정
# http://mlflow.mlops.click → Models → 해당 모델 → 버전 클릭 → Aliases → champion 입력

# 방법 2: Python으로 설정
python3 - << 'EOF'
import mlflow, os
mlflow.set_tracking_uri("http://mlflow.mlflow.svc.cluster.local:80")
os.environ["MLFLOW_TRACKING_USERNAME"] = "admin"
os.environ["MLFLOW_TRACKING_PASSWORD"] = "xxxx"
client = mlflow.tracking.MlflowClient()
# 버전 번호 확인 후 적용
client.set_registered_model_alias("invest-crel-classification", "champion", "3")
client.set_registered_model_alias("invest-crel-regression", "champion", "3")
print("champion alias 설정 완료")
EOF

# 방법 3: Pod 재시작 없이 핫 리로드
bash deploy.sh --reload
# 또는
kubectl exec -n mlops deployment/invest-inference \
  -- python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/model/reload', data=b'')"
```

---

## 7. 로그 확인

### 7.1 실시간 로그

```bash
# 전체 로그 (2개 Pod 동시)
kubectl logs -n mlops -l app=invest-inference --prefix=true -f

# 특정 Pod 로그
kubectl logs -n mlops <pod-name> -f

# 최근 100줄
kubectl logs -n mlops deployment/invest-inference --tail=100
```

### 7.2 S3 추론 로그

> 현재 IRSA 미설정으로 S3 로그 쓰기 비활성 (WARNING 로그만 출력, 추론에는 영향 없음)

IRSA 설정 후 아래 경로에서 확인:

```
s3://s3-an2-mlops/invest-model-result/LOG/YYYYMMDD/
  └── {request_id}_INFERENCE_START.json
  └── {request_id}_INFERENCE_SUCCESS.json
  └── {request_id}_INFERENCE_ERROR.json
```

---

## 8. 운영 절차

### 8.1 스케일링

```bash
# 수동 스케일 (일시적)
kubectl scale deployment invest-inference --replicas=4 -n mlops

# HPA 설정 변경 (영구적)
kubectl patch hpa invest-inference-hpa -n mlops \
  --type=json -p='[{"op":"replace","path":"/spec/maxReplicas","value":20}]'
```

### 8.2 Pod 이슈 대응

```bash
# CrashLoopBackOff 시
kubectl describe pod <pod-name> -n mlops          # 이벤트 확인
kubectl logs <pod-name> -n mlops --previous       # 이전 실행 로그

# champion alias 없음 오류 → MLflow UI에서 alias 설정 후 재시작
kubectl rollout restart deployment/invest-inference -n mlops

# MLflow 연결 오류 → MLflow Pod 상태 확인
kubectl get pods -n mlflow
kubectl logs -n mlflow deployment/mlflow
```

### 8.3 배포 롤백

```bash
# 이전 버전으로 롤백
kubectl rollout undo deployment/invest-inference -n mlops

# 특정 revision으로 롤백
kubectl rollout history deployment/invest-inference -n mlops
kubectl rollout undo deployment/invest-inference --to-revision=2 -n mlops
```

---

## 9. 트러블슈팅 (배포 시 경험)

| 증상 | 원인 | 해결 |
|------|------|------|
| `SyntaxError: invalid syntax` | 컨테이너 내 inference.py 파일 내용 오염 | 파일 재작성 후 이미지 재빌드 |
| `champion alias not found` | MLflow Registry에 `@champion` alias 미설정 | MLflow UI 또는 Python으로 alias 설정 |
| `Connection refused (MLflow)` | MLflow Pod 재시작 타이밍 겹침 | readinessProbe delay 180s로 증가 후 재시도 |
| `FailedCreate: serviceaccount not found` | `invest-inference-sa` SA가 해당 namespace에 없음 | SA 생성 또는 deployment에서 제거 |
| `Forbidden: namespaces` | mlops_user RBAC가 `invest-inference` namespace 권한 없음 | namespace를 `mlops`로 변경 |
| `CrashLoopBackOff (SIGTERM)` | readinessProbe timeout < 모델 로딩 시간 | initialDelaySeconds를 180s로 증가 |
| `invest_prob` 항상 0.0 | `mlflow.pyfunc.load_model`은 `predict_proba` 미지원 | `mlflow.xgboost.load_model`로 native 로드 |

> **모델 로드 방식 (중요)**: 분류 모델 확률(`invest_prob`)을 얻으려면 반드시
> `mlflow.xgboost.load_model`로 native XGBClassifier를 로드해야 한다.
> pyfunc 래퍼는 `predict`만 노출하므로 `predict_proba`가 동작하지 않는다.

---

## 10. 환경변수 전체 목록

| 변수명 | 현재값 | 출처 |
|--------|--------|------|
| `MLFLOW_TRACKING_URI` | `http://mlflow.mlflow.svc.cluster.local:80` | deployment.yaml |
| `MLFLOW_TRACKING_USERNAME` | `admin` | K8s Secret `mlflow-auth` |
| `MLFLOW_TRACKING_PASSWORD` | (Secret) | K8s Secret `mlflow-auth` |
| `MODEL_CLS_NAME` | `invest-crel-classification` | deployment.yaml |
| `MODEL_REG_NAME` | `invest-crel-regression` | deployment.yaml |
| `MODEL_ALIAS` | `champion` | deployment.yaml |
| `S3_BUCKET` | `s3-an2-mlops` | deployment.yaml |
| `AWS_REGION` | `ap-northeast-2` | deployment.yaml |

---

## 11. 소스 파일 위치

| 파일 | 위치 | 설명 |
|------|------|------|
| `inference.py` | `mlops_user@ip-10-1-0-86:~/invest-app/` | FastAPI 앱 (서버 상) |
| `deploy.sh` | `~/invest-app/` | 빌드/배포 자동화 |
| `k8s/*.yaml` | `~/invest-app/k8s/` | K8s 매니페스트 |
| Windows 원본 | `d:\ADT\workspace\mlapi\` | 개발 원본 |
| MLops 포탈 연동 | `d:\ADT\workspace\mlops\app\services\inference_service.py` | 포탈 InferenceService |
| MLops 포탈 UI | `d:\ADT\workspace\mlops\app\templates\pages\inference.html` | 포탈 테스트 페이지 |

---

## 12. 담당자 연락처

| 역할 | 담당 | 문의 내용 |
|------|------|----------|
| 추론 API 개발 | 개발팀 | 소스코드, API 스펙 |
| ML 모델/champion alias | ML 학습팀 | 모델 버전 관리, 재학습 |
| EKS 인프라/ECR | 인프라팀 | 배포 환경, 권한, 네트워크 |
| MLops 플랫폼 | MLops팀 | MLflow, 포탈 연동 |
