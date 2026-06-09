# EKS Deployment - Gap Analysis (Check Phase)

> Version: 1.0.0 | Date: 2026-05-20 | Phase: Check

## 1. 분석 요약

| 항목 | 내용 |
|------|------|
| 설계 문서 | `docs/02-design/features/eks-deployment.design.md` |
| 구현 파일 | `Dockerfile`, `build_and_push.sh`, `k8s/*.yaml` |
| 검사 항목 | 12개 |
| 일치 항목 | 8개 |
| 갭 항목 | 4개 |
| **Match Rate** | **67%** (90% 목표 미달) |

---

## 2. 일치 항목 (Matched) ✅

| # | 설계 명세 | 구현 상태 | 파일 |
|---|----------|----------|------|
| 1 | Dockerfile: python:3.12-slim 베이스 이미지 | ✅ 일치 | `Dockerfile:1` |
| 2 | Dockerfile: 포트 6080 노출 | ✅ 일치 | `Dockerfile:18` |
| 3 | Dockerfile: uvicorn 엔트리포인트 | ✅ 일치 | `Dockerfile:21` |
| 4 | ECR 스크립트: 로그인/빌드/태그/푸시 | ✅ 일치 | `build_and_push.sh` |
| 5 | Secret: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD | ✅ 일치 | `k8s/backend-secret.yaml` |
| 6 | Deployment: replicas=1, namespace=mlops | ✅ 일치 | `k8s/backend-deployment.yaml` |
| 7 | Deployment: envFrom secretRef | ✅ 일치 | `k8s/backend-deployment.yaml:27-29` |
| 8 | Service: ClusterIP, port=6080, namespace=mlops | ✅ 일치 | `k8s/backend-service.yaml` |

---

## 3. 갭 항목 (Gaps) ❌

### GAP-1: Secret에 필수 환경변수 누락 [Critical]

**설명**: `app/core/config.py`가 요구하는 환경변수 중 4개가 `k8s/backend-secret.yaml`에 없음.  
K8s에서 기본값(localhost)을 사용하면 서비스 간 연결이 실패함.

| 누락 환경변수 | 기본값 | K8s에서의 문제 |
|-------------|--------|--------------|
| `SECRET_KEY` | `mlfoundry-change-this-secret-key` | 프로덕션 보안 취약 |
| `MLFLOW_BASE_URL` | `http://localhost:6000` | MLflow 연결 불가 |
| `JUPYTER_BASE_URL` | `http://localhost:6888` | JupyterLab 연결 불가 |
| `JUPYTER_TOKEN` | `mlfoundry_token` | JupyterLab 인증 실패 |

**수정 위치**: `k8s/backend-secret.yaml`

---

### GAP-2: Liveness/Readiness Probe 경로 비최적 [Medium]

**설명**: Probe가 `/docs` (Swagger UI)를 사용하지만, `app/main.py:41`에 전용 `/health` 엔드포인트가 존재함.  
`/docs`는 Swagger 페이지 전체를 렌더링하므로 헬스체크에 불필요한 부하 발생.

**수정 위치**: `k8s/backend-deployment.yaml` - probe path를 `/health`로 변경

---

### GAP-3: .dockerignore 없음 [High]

**설명**: `.dockerignore`가 없으면 `.venv`(수백 MB), `__pycache__`, `.env` 등이 Docker 이미지에 포함됨.  
- 이미지 크기 불필요하게 증가 (300MB+)
- `.env` 파일에 민감 정보 포함 가능성
- Windows에서 생성된 `.venv`가 Linux 컨테이너에 포함되면 Python 경로 충돌

**수정 위치**: 프로젝트 루트에 `.dockerignore` 파일 생성

---

### GAP-4: ECR 이미지 풀 인증 미명시 [Medium]

**설명**: `backend-deployment.yaml`에 ECR 이미지 풀 인증 방식이 명시되지 않음.  
IRSA(IAM Roles for Service Accounts) 또는 `imagePullSecrets`가 설정되지 않으면 `ErrImagePull` 오류 발생.

**수정 위치**: `k8s/backend-deployment.yaml` - imagePullSecrets 추가 또는 IRSA 설정 문서화

---

## 4. 수정 방법

### Fix-1: backend-secret.yaml에 누락 환경변수 추가

```yaml
# k8s/backend-secret.yaml 전체 교체
stringData:
  # DB 접속 정보
  DB_HOST: "your-rds-endpoint.amazonaws.com"
  DB_PORT: "5432"
  DB_NAME: "mlfoundry"
  DB_USER: "ai_ready"
  DB_PASSWORD: "your-db-password"
  # 앱 보안키 (프로덕션용 랜덤값 사용)
  SECRET_KEY: "your-random-secret-key-here"
  # MLflow 서버 주소 (mlops 네임스페이스 내 서비스명 또는 외부 URL)
  MLFLOW_BASE_URL: "http://mlflow-service:5000"
  # JupyterLab 서버 주소
  JUPYTER_BASE_URL: "http://jupyter-service:8888"
  JUPYTER_TOKEN: "mlfoundry_token"
```

### Fix-2: Probe 경로를 /health로 변경

```yaml
livenessProbe:
  httpGet:
    path: /health   # /docs → /health
    port: 6080
readinessProbe:
  httpGet:
    path: /health   # /docs → /health
    port: 6080
```

### Fix-3: .dockerignore 생성

```
.venv
__pycache__
*.pyc
*.pyo
.env
.env.*
*.log
.git
.gitignore
docs/
k8s/
demo/
```

### Fix-4: ECR imagePullSecrets (IRSA 미사용 시)

```yaml
spec:
  serviceAccountName: default
  # IRSA 미사용 시 아래 추가:
  # imagePullSecrets:
  #   - name: ecr-registry-secret
```

---

## 5. 결론 및 다음 단계

| 우선순위 | 갭 | 액션 |
|---------|-----|------|
| 🔴 Critical | GAP-1: Secret 누락 변수 | 즉시 수정 필요 (앱 동작 불가) |
| 🟠 High | GAP-3: .dockerignore | 이미지 빌드 전 수정 필요 |
| 🟡 Medium | GAP-2: Probe 경로 | 운영 안정성을 위해 수정 권장 |
| 🟡 Medium | GAP-4: ECR 인증 | IRSA 설정 여부 확인 필요 |

수정 후 재분석(`/pdca iterate`)을 통해 Match Rate 90% 이상 달성 권장.
