# 배포 가이드 — AI 데이터 분석 포털

> 최종 업데이트: 2026-05-27  
> 배포 방식: **압축 파일(zip) 전송 → 서버에서 Docker 빌드 → kubectl apply**

---

## 1. 배포 대상 파일 구조

```
mlfoundry_260429/          ← 배포 패키지 루트
├── app/                   ✅ 배포 필수
│   ├── api/
│   │   ├── deps.py
│   │   ├── router.py
│   │   └── routes/
│   │       ├── admin.py         ← 신규 (사용자/설정 관리)
│   │       ├── auth.py
│   │       ├── board.py
│   │       ├── datasets.py
│   │       ├── jupyter.py
│   │       ├── mlflow_proxy.py
│   │       ├── query.py
│   │       ├── s3_storage.py
│   │       ├── service_token.py
│   │       └── web.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── security.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── board.py
│   │   ├── dataset.py
│   │   ├── query_history.py
│   │   ├── service_token.py
│   │   ├── system_settings.py  ← 신규 (설정 DB 모델)
│   │   └── user.py
│   ├── repositories/
│   │   ├── board_repo.py
│   │   ├── dataset_repo.py
│   │   ├── query_history_repo.py
│   │   ├── settings_repo.py    ← 신규
│   │   └── user_repo.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── board.py
│   │   ├── common.py
│   │   ├── dataset.py
│   │   └── query.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── board_service.py
│   │   ├── dataset_service.py
│   │   ├── jupyter_service.py
│   │   ├── mlflow_service.py
│   │   ├── query_service.py
│   │   ├── settings_seed.py    ← 신규
│   │   ├── settings_service.py ← 신규
│   │   └── file_service.py (있는 경우)
│   ├── static/
│   │   ├── css/main.css        ← 변경
│   │   └── js/app.js           ← 변경
│   ├── templates/
│   │   ├── base.html           ← 변경 (accordion sidebar)
│   │   ├── login.html
│   │   └── pages/
│   │       ├── admin_settings.html  ← 신규
│   │       ├── admin_users.html     ← 신규
│   │       ├── board.html
│   │       ├── dashboard.html  ← 변경
│   │       ├── datasets.html
│   │       ├── files.html
│   │       ├── jupyter.html
│   │       ├── mlflow.html     ← 변경
│   │       └── query.html
│   └── main.py                 ← 변경
├── k8s/                   ✅ 배포 필수
│   ├── backend-deployment.yaml
│   ├── backend-ingress.yaml
│   ├── backend-secret.yaml     ← 배포 전 값 확인 필수
│   └── backend-service.yaml
├── scripts/               ✅ 운영 도구
│   └── add_users.py
├── Dockerfile             ✅ 배포 필수
├── requirements.txt       ✅ 배포 필수
└── .env.example           ✅ 참고용

```

---

## 2. 배포 제외 파일 (압축 시 제외)

```
.venv/              ← Python 가상환경 (서버에서 pip install)
__pycache__/        ← 런타임 캐시
*.pyc / *.pyo
.env                ← 로컬 전용 환경변수 (k8s Secret으로 관리)
docs/               ← 개발 문서
libs/
demo/
docker/
docker-compose*.yml
.git/
.claude/
.bkit/
.streamlit/
*.log
alembic.ini
dbcreate.md
```

---

## 3. 배포 절차

### 3-1. 압축 파일 생성 (Windows 로컬)

PowerShell에서 실행:
```powershell
# 프로젝트 루트로 이동
cd "D:\ADT\workspace\mlfoundry_260429"

# 배포 패키지 생성 (제외 목록 적용)
$exclude = @('.venv','__pycache__','.git','.claude','.bkit','.streamlit','docs','libs','demo','docker','*.log','*.pyc','*.pyo','.env','alembic.ini','dbcreate.md')
$date = Get-Date -Format "yyyyMMdd_HHmm"
$zipName = "mlfoundry_$date.zip"

# 포함할 항목만 압축
Compress-Archive -Path app, k8s, scripts, Dockerfile, requirements.txt, .env.example, .dockerignore `
  -DestinationPath "D:\ADT\deploy\$zipName" -Force

Write-Host "배포 파일 생성: D:\ADT\deploy\$zipName"
```

### 3-2. EC2 서버에 전송

```bash
# SCP로 전송 (EC2 public IP 또는 bastion)
scp -i your-key.pem D:/ADT/deploy/mlfoundry_20260527_1200.zip ec2-user@<EC2_IP>:/tmp/
```

### 3-3. EC2 서버에서 빌드 & 배포

```bash
# EC2 접속 후
cd /tmp
unzip mlfoundry_20260527_1200.zip -d mlfoundry
cd mlfoundry

# Docker 이미지 빌드 (ECR 또는 로컬 레지스트리)
# 예: ECR 사용 시
AWS_ACCOUNT=<account-id>
AWS_REGION=ap-northeast-2
ECR_REPO=$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/mlops-portal

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_REPO

docker build -t $ECR_REPO:latest .
docker push $ECR_REPO:latest

# k8s 배포
kubectl apply -f k8s/backend-secret.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/backend-ingress.yaml

# 롤링 재시작 (이미 배포된 경우 이미지 업데이트)
kubectl rollout restart deployment/mlops -n mlops

# 상태 확인
kubectl rollout status deployment/mlops -n mlops
kubectl get pods -n mlops
```

---

## 4. backend-secret.yaml 체크리스트

배포 전 반드시 확인:

| 항목 | 키 | 비고 |
|------|-----|------|
| DB 비밀번호 | `DB_PASSWORD` | RDS 비밀번호 |
| JWT 시크릿 | `SECRET_KEY` | 운영용 랜덤 값 |
| JupyterHub 관리자 토큰 | `JUPYTERHUB_ADMIN_TOKEN` | `88db47bb87f140b6b69cbbabf6966b6c` |
| Jupyter 환경 목록 | `JUPYTER_ENVS` | JSON 배열 |
| JupyterHub URL | `JUPYTER_BASE_URL` | `http://jupyterhub.mlops.click` |
| MLFlow URL | `MLFLOW_BASE_URL` | `http://mlflow.mlops.click` |
| Athena 데이터베이스 | `ATHENA_DATABASE` | `mlops` |
| Athena S3 출력 | `ATHENA_S3_OUTPUT` | S3 경로 |
| S3 버킷 | `S3_BUCKET_NAME` | `s3-an2-mlflow` |

> ⚠️ `.env` 파일을 절대 압축 패키지에 포함하지 마세요.

---

## 5. 신규 사용자 추가 (재배포 불필요)

배포 후 포털 사용자 추가:
```bash
# kubectl exec으로 파드에서 직접 실행
kubectl exec -n mlops -it \
  $(kubectl get pod -n mlops -l app=mlops -o jsonpath='{.items[0].metadata.name}') \
  -- python scripts/add_users.py <사용자ID> <비밀번호>

# 예시
kubectl exec -n mlops -it <POD> -- python scripts/add_users.py 09930269 09930269
kubectl exec -n mlops -it <POD> -- python scripts/add_users.py 09929689 09929689
```

또는 배포 후 포털 관리자(admin 계정)로 로그인 → **Management > Users > 사용자 추가** 메뉴 사용.

---

## 6. 설정 변경 (재배포 불필요)

서비스 URL 등 비민감 설정은 포털 UI에서 직접 변경 가능:

1. admin 계정으로 로그인
2. **Management > Settings** 이동
3. 값 수정 후 **저장** 클릭 → 즉시 반영 (캐시 무효화, 재배포 불필요)

변경 가능 설정: `MLFLOW_BASE_URL`, `JUPYTER_BASE_URL`, `JUPYTER_ENVS`, `ATHENA_DATABASE`, `ATHENA_S3_OUTPUT`, `S3_BUCKET_NAME`

---

## 7. 로컬 개발 환경

```powershell
# 1. .env 파일 생성
Copy-Item .env.example .env
# .env 편집: DB_HOST, JUPYTERHUB_ADMIN_TOKEN 등 설정

# 2. 패키지 설치
python -m pip install -r requirements.txt

# 3. 서버 실행
python -m uvicorn app.main:app --host 0.0.0.0 --port 6080 --reload

# 4. 접속
# http://localhost:6080  (admin / admin)
```
