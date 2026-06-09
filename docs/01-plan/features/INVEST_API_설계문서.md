# INVEST 투자적격 심사 추론 API 서버 설계문서
**버전:** 1.1.0 | **작성일:** 2026-06-04 | **최종수정:** 2026-06-05 | **상태:** 배포 완료

> **배포 완료** — 실제 운영 정보는 [운영 가이드](../../03-guide/invest-inference-operations.md) 참조

---

## 1. 개요

### 1.1 목적
부동산담보대출 투자적격 심사 AI 모델(투자적격판단 + 적정금리평가)을 실시간 REST API로 서빙하는 독립 애플리케이션.  
JupyterHub(`invest_crel_model.ipynb`)에서 학습·등록된 MLFlow 모델을 로드하여 업무시스템의 실시간 추론 요청에 응답한다.

### 1.2 배포 위치
- **플랫폼:** AWS EKS (기존 mlops 클러스터와 동일 또는 별도 namespace)
- **네임스페이스:** `invest-inference` (신규)
- **mlops workspace(`D:\ADT\workspace\mlops`)와 독립된 별도 Pod**

### 1.3 기술 스택 (mlops 스택 기준 유사 구성)

| 구분 | 기술 | 비고 |
|------|------|------|
| API Framework | FastAPI | mlops 스택과 동일 |
| WSGI | Uvicorn | |
| 모델 로드 | MLFlow pyfunc | Registry @champion alias |
| 데이터 검증 | Pydantic v2 | 요청/응답 스키마 |
| 컨테이너 | Docker (Python 3.11-slim) | |
| 오케스트레이션 | Kubernetes (EKS) | |
| 인증 | AWS IAM Role (IRSA) | .env 미사용, K8s Secret 주입 |
| 로깅 | S3 + CloudWatch | |
| 모니터링 | Prometheus + Grafana | mlops 동일 스택 |

---

## 2. 디렉토리 구조

```
invest-inference/
├── app/
│   ├── main.py              # FastAPI 앱 진입점 (inference.py 기반)
│   ├── model_store.py       # MLFlow 모델 로드/캐싱/리로드
│   ├── preprocess.py        # 전처리 로직 (노트북과 동일)
│   ├── schema.py            # Pydantic 요청/응답 모델
│   └── utils/
│       ├── logger.py        # S3 로그 유틸
│       └── health.py        # 헬스체크 유틸
├── Dockerfile
├── requirements.txt
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── hpa.yaml             # HorizontalPodAutoscaler
│   └── secret.yaml          # MLFlow 인증정보 (K8s Secret)
└── tests/
    ├── test_predict.py
    └── test_preprocess.py
```

---

## 3. API 명세

### Base URL
```
http://invest-inference.invest-inference.svc.cluster.local:8080   # 클러스터 내부
https://api.invest.internal/inference                              # Ingress 외부
```

---

### 3.1 `GET /health`
서버 및 모델 로드 상태 확인

**Response 200**
```json
{
  "status": "ok",
  "model_loaded": true,
  "loaded_at": "2026-06-04 10:00:00"
}
```

---

### 3.2 `GET /model/info`
현재 로드된 모델 버전 정보 조회

**Response 200**
```json
{
  "mlflow_uri": "http://mlflow.mlflow.svc.cluster.local:80",
  "cls_model": "invest-crel-classification",
  "reg_model": "invest-crel-regression",
  "alias": "champion",
  "loaded_at": "2026-06-04 10:00:00"
}
```

---

### 3.3 `POST /model/reload`
MLFlow Registry champion alias 변경 후 재배포 없이 새 버전 핫 리로드

**Response 200**
```json
{
  "status": "reloaded",
  "loaded_at": "2026-06-04 11:00:00"
}
```
> ⚠️ Internal endpoint — Ingress에서 외부 노출 제외 권장

---

### 3.4 `POST /predict` ⭐ 핵심 엔드포인트

**Request Body** (`application/json`)

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `gpt_ivt_jg_seq` | string | ✅ | GPT투자심사일련번호 (요청 추적 키) |
| `ltv_rte` | float | | LTV (%) |
| `dbt_rpy_coef_rte` | float | | DSCR |
| `ln_pd` | float | | 대출기간 (월) |
| `bs_itt` | float | | 기준금리 (%) |
| `gpt_ivt_etrm_rte` | float | | 공실률 (%) |
| `gpt_ivt_rmd_lsg_ycn` | float | | 잔여임대차기간 (년) |
| `gpt_ivt_ln_pfat_txt` | float | | Debt Yield (%) |
| `gpt_ivt_mkt_avg_cpt_rte` | float | | 시장 Cap Rate (%) |
| `gpt_ivt_dlb_rqt_amt` | float | | 심의요청금액 (원) |
| `gpt_ivt_kd_cd` | string | | 물건구분 |
| `gpt_ivt_ser_dv_cd` | string | | 투자섹터 |
| `gpt_ivt_tp_cd` | string | | 투자유형 |
| *(기타 44개 컬럼 전체 Optional)* | | | |

**Request 예시**
```json
{
  "gpt_ivt_jg_seq": "JG20260604001",
  "gpt_fl_nm": "서울 강남구 오피스빌딩 선순위 대출",
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
  "request_id": "20260604100000123456",
  "gpt_ivt_jg_seq": "JG20260604001",
  "invest_yn": "Y",
  "invest_prob": 0.7821,
  "fair_rate": 5.4312,
  "cls_model": "invest-crel-classification@champion",
  "reg_model": "invest-crel-regression@champion",
  "inferred_at": "2026-06-04 10:00:00"
}
```

| 응답 필드 | 설명 |
|-----------|------|
| `invest_yn` | 투자 적격 여부 (Y=적격, N=부적격) |
| `invest_prob` | 적격 확률 (0~1, 보조지표로 활용) |
| `fair_rate` | 적정 수익률/금리 (%) |

**Error Response**
```json
{ "detail": "모델 미로드 상태" }   // 503
{ "detail": "전처리 오류: ..." }   // 500
```

---

## 4. 모델 로드 전략

```
앱 시작 (startup)
    ↓
MLFlow Registry 조회
    → models:/invest-crel-classification@champion
    → models:/invest-crel-regression@champion
    ↓
메모리 캐싱 (ModelStore 싱글턴)
    ↓
요청마다 캐싱된 모델로 즉시 추론
```

**champion alias 관리 흐름**
```
MLFlow UI 또는 MlflowClient
    → invest-crel-classification v3 에 @champion alias 부여
    ↓
POST /model/reload 호출 (또는 Pod 재시작)
    ↓
새 champion 버전 자동 로드
```

> 모델 교체 시 **Pod 재배포 불필요** — `/model/reload`만으로 교체 가능

---

## 5. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libgomp1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
```

---

## 6. requirements.txt

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
pydantic>=2.0.0
mlflow>=2.8.0
xgboost>=1.7.0
scikit-learn>=1.2.0
pandas>=1.5.0
numpy>=1.23.0
boto3>=1.26.0
joblib>=1.2.0
python-dotenv>=1.0.0
pytz>=2024.1
```

---

## 7. Kubernetes 배포 명세

### 7.1 deployment.yaml 핵심 스펙

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: invest-inference
  namespace: invest-inference
spec:
  replicas: 2
  selector:
    matchLabels:
      app: invest-inference
  template:
    spec:
      serviceAccountName: invest-inference-sa   # IRSA (S3/MLFlow 접근)
      containers:
      - name: invest-inference
        image: <ECR_URI>/invest-inference:latest
        ports:
        - containerPort: 8080
        env:
        - name: MLFLOW_TRACKING_URI
          value: "http://mlflow.mlflow.svc.cluster.local:80"
        - name: MLFLOW_TRACKING_USERNAME
          valueFrom:
            secretKeyRef:
              name: mlflow-auth
              key: username
        - name: MLFLOW_TRACKING_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mlflow-auth
              key: password
        - name: MODEL_CLS_NAME
          value: "invest-crel-classification"
        - name: MODEL_REG_NAME
          value: "invest-crel-regression"
        - name: MODEL_ALIAS
          value: "champion"
        - name: S3_BUCKET
          value: "s3-an2-mlops"
        - name: AWS_REGION
          value: "ap-northeast-2"
        resources:
          requests:
            cpu: "500m"
            memory: "1Gi"
          limits:
            cpu: "2"
            memory: "4Gi"
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 30
```

### 7.2 HPA (자동 스케일링)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: invest-inference-hpa
  namespace: invest-inference
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: invest-inference
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
```

### 7.3 K8s Secret (MLFlow 인증)

```bash
# 생성 명령 (CI/CD 파이프라인에서 수행)
kubectl create secret generic mlflow-auth \
  --from-literal=username=admin \
  --from-literal=password=<실제패스워드> \
  -n invest-inference
```

---

## 8. CI/CD 파이프라인 (Bitbucket 기준)

```
코드 Push (Bitbucket)
    ↓
Bitbucket Pipelines 트리거
    ↓
Docker 빌드
    ↓
ECR Push (<account>.dkr.ecr.ap-northeast-2.amazonaws.com/invest-inference)
    ↓
kubectl rollout restart deployment/invest-inference -n invest-inference
```

---

## 9. 업무시스템 연동 시나리오

```
업무시스템 (심사 화면)
    │  POST /predict
    │  {gpt_ivt_jg_seq, ltv_rte, dscr, ...}
    ↓
invest-inference Pod
    │  MLFlow Registry 모델 추론
    ↓
응답: {invest_yn: "Y", invest_prob: 0.78, fair_rate: 5.43}
    ↓
업무시스템 화면 표시
    - 투자적격 여부: ✅ 적격 (확률 78%)
    - AI 추천 금리: 5.43%
```

---

## 10. 개발 구현 가이드 (Claude Code용)

### 구현 우선순위

1. `app/schema.py` — Pydantic 요청/응답 모델 (44개 컬럼 전체)
2. `app/preprocess.py` — 전처리 함수 (`invest_crel_model.ipynb` 1-4셀과 동일 로직)
3. `app/model_store.py` — ModelStore 클래스 (싱글턴, load/reload)
4. `app/main.py` — FastAPI 앱 + 엔드포인트 연결
5. `Dockerfile` + `requirements.txt`
6. `k8s/` 매니페스트
7. `tests/` 단위 테스트

### 핵심 주의사항

- **전처리 일관성**: `preprocess.py`의 컬럼 순서, LabelEncoder 처리가 `invest_crel_model.ipynb` 학습과 **완전히 동일**해야 함
- **LabelEncoder 공유**: 노트북에서 학습 시 `le_dict.pkl`, `le_target.pkl`을 MLFlow Artifact에 등록해야 API에서 로드 가능
- **결측값 전략**: 단건 추론은 학습셋 중앙값을 상수로 박아두거나 Artifact로 저장하여 주입
- **모델 alias**: MLFlow Registry에서 배포할 버전에 `@champion` alias 부여 후 `/model/reload` 호출
- **인증정보**: `.env` 파일 사용 금지 → K8s Secret + 환경변수 주입만 사용

### 노트북 → API 연결 항목 체크리스트

- [ ] `NUMERIC_COLS`, `CAT_COLS`, `FEATURE_COLS` 리스트 동일 여부 확인
- [ ] LabelEncoder pickle을 MLFlow Artifact `encoders/` 경로에 등록
- [ ] 학습셋 중앙값을 `encoders/numeric_medians.json`으로 저장하여 결측 대체에 활용
- [ ] MLFlow champion alias 설정 확인 (`invest-crel-classification`, `invest-crel-regression`)
- [ ] `/health` 엔드포인트로 K8s readinessProbe 연동 확인
