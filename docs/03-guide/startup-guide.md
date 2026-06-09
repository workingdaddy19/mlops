# MLFoundry 서버 가동 가이드

## 1. 사전 조건

| 항목 | 요구사항 |
|------|----------|
| OS | Ubuntu Linux |
| Python | 3.11+ (현재 서버: 3.12.3) |
| PostgreSQL | 192.168.6.13:5432 (기 설치) |
| Docker | Docker + Docker Compose (JupyterLab/MLflow용) |

---

## 2. 초기 설정 (최초 1회)

### 2-1. Python 가상환경 생성

```bash
cd /home/kyobo/mlops-poc/mlfoundry
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2-2. 환경 변수 설정

```bash
cp .env.example .env
vi .env
```

**반드시 수정해야 할 항목:**

| 변수 | 설명 | 비고 |
|------|------|------|
| `DB_PASSWORD` | PostgreSQL 비밀번호 | 필수 수정 |
| `SECRET_KEY` | JWT 서명 키 | 운영시 변경 권장 |

> `.env` 파일은 `.gitignore`에 등록되어 있어 git에 절대 포함되지 않습니다.
> `.env` 파일 위치: `/home/kyobo/mlops-poc/mlfoundry/.env`

### 2-3. 데이터베이스 생성

```bash
# mlfoundry DB가 없는 경우에만 실행
PGPASSWORD=<비밀번호> psql -h 192.168.6.13 -p 5432 -U ai_ready -d postgres \
  -c "CREATE DATABASE mlfoundry OWNER ai_ready;"
```

> 테이블은 FastAPI 서버 최초 기동 시 자동 생성됩니다.
> 기본 사용자(admin/admin, user/user)도 자동 생성됩니다.

---

## 3. 서버 가동

### 3-1. Docker 서비스 (JupyterLab + MLflow)

```bash
cd /home/kyobo/mlops-poc/mlfoundry
docker-compose up -d
```

확인:
```bash
docker ps | grep mlfoundry
```

### 3-2. FastAPI 백엔드

```bash
cd /home/kyobo/mlops-poc/mlfoundry
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 6080 --reload
```

백그라운드 실행 (선택):
```bash
nohup uvicorn app.main:app --host 0.0.0.0 --port 6080 > logs/backend.log 2>&1 &
```

### 3-3. Streamlit UI

```bash
cd /home/kyobo/mlops-poc/mlfoundry
source .venv/bin/activate
streamlit run ui/streamlit_app.py --server.port 6501 --server.address 0.0.0.0
```

백그라운드 실행 (선택):
```bash
nohup streamlit run ui/streamlit_app.py --server.port 6501 --server.address 0.0.0.0 > logs/streamlit.log 2>&1 &
```

---

## 4. 접속 URL

| 서비스 | URL | 비고 |
|--------|-----|------|
| FastAPI API Docs | http://localhost:6080/docs | Swagger UI |
| Streamlit UI | http://localhost:6501 | 사용자 포털 |
| JupyterLab | http://localhost:6888 | Docker, 토큰: mlfoundry_token |
| MLflow | http://localhost:6000 | Docker |

---

## 5. 기본 계정

| 아이디 | 비밀번호 | 역할 |
|--------|----------|------|
| admin | admin | 관리자 |
| user | user | 일반 사용자 |

---

## 6. 서버 중지

```bash
# FastAPI / Streamlit 종료
kill $(lsof -t -i:6080) 2>/dev/null
kill $(lsof -t -i:6501) 2>/dev/null

# Docker 서비스 중지
docker-compose down
```

---

## 7. 디렉토리 구조

```
mlfoundry/
├── app/                     # FastAPI 백엔드
│   ├── main.py             # 앱 엔트리포인트
│   ├── core/               # 설정, DB, 보안
│   ├── models/             # SQLAlchemy 모델
│   ├── schemas/            # Pydantic 스키마
│   ├── repositories/       # DB 쿼리 계층
│   ├── services/           # 비즈니스 로직
│   └── api/                # API 라우트
│       └── routes/         # 개별 라우트 모듈
├── ui/                     # Streamlit UI
│   ├── streamlit_app.py    # 메인 앱
│   └── pages/              # 페이지 모듈
├── docker-compose.yml      # JupyterLab + MLflow
├── requirements.txt        # Python 의존성
├── .env                    # 환경 변수 (git 미포함!)
├── .env.example            # 환경 변수 템플릿
└── docs/                   # 문서
```

---

## 8. 주요 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | /api/auth/login | 로그인 |
| GET | /api/auth/me | 현재 사용자 조회 |
| GET/POST | /api/board | 게시판 목록/등록 |
| GET/PUT/DELETE | /api/board/{id} | 게시글 조회/수정/삭제 |
| POST | /api/query/execute | SQL 쿼리 실행 |
| GET | /api/query/schemas | 스키마 탐색 |
| GET | /api/query/history | 쿼리 실행 이력 |
| GET/POST | /api/datasets | 데이터셋 목록/등록 |
| GET | /api/jupyter/health | JupyterLab 상태 |
| GET | /api/jupyter/notebooks | 노트북 목록 |
| GET | /api/mlflow/health | MLflow 상태 |
| GET | /api/mlflow/experiments | MLflow 실험 목록 |
| GET/POST | /api/files | 파일 목록/업로드 |

---

## 9. 문제 해결

### DB 연결 실패
```
password authentication failed for user "ai_ready"
```
→ `.env` 파일의 `DB_PASSWORD` 값을 확인하세요.

### JupyterLab/MLflow 연결 안 됨
```
status: unavailable
```
→ `docker-compose up -d` 로 Docker 컨테이너를 시작하세요.

### 포트 충돌
```
Address already in use
```
→ 해당 포트를 사용하는 프로세스를 확인 후 종료:
```bash
lsof -i :6080
kill <PID>
```

---

## 10. 민감 정보 관리

| 파일 | 위치 | 용도 |
|------|------|------|
| `.env` | `/home/kyobo/mlops-poc/mlfoundry/.env` | DB 비밀번호, 시크릿 키 등 |

**절대 git에 커밋하지 마세요.** `.gitignore`에 등록되어 있으나 주의 필요.
수정 시: `vi /home/kyobo/mlops-poc/mlfoundry/.env`
