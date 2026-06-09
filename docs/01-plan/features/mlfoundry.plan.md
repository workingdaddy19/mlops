# mlfoundry 프로젝트 개발 계획서 (v2)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | mlfoundry - 로컬 ML 데이터 플랫폼 포털 |
| **작성일** | 2026-04-04 (2026-04-24 v2 전면 개편) |
| **프로젝트명** | mlfoundry |
| **대상 환경** | 로컬 서버 (Ubuntu Linux) |

### v2 변경 이력 (2026-04-24)

| 변경 항목 | Before (v1) | After (v2) |
|-----------|-------------|------------|
| 개발 언어 | Java 1.8 + Spring Boot 2.7 | **Python + FastAPI** |
| UI | Thymeleaf + Bootstrap | **FastAPI + Jinja2 (HTML/JS)** |
| ORM | MyBatis | **SQLAlchemy** |
| DB | MySQL (Docker / RDS) | **PostgreSQL (192.168.6.13:5432)** |
| AWS | SageMaker, Redshift, QuickSight, S3 | **전체 삭제** |
| LLM | Ollama | **삭제** |
| Jupyter | conda-pack / SageMaker | **Docker 컨테이너** |
| MLflow | 없음 | **Docker 컨테이너 (신규)** |
| SSO/DRM | Initech SSO, MarkAny DRM | **삭제** |

> ai-ready-poc 프로젝트와 동일 기술 스택 채택. 추후 통합 용이.

---

## 1. 기술 스택

### 백엔드 (API + UI Serving)

| 구분 | 기술 | 비고 |
|------|------|------|
| Language | Python 3.11+ | |
| Framework | FastAPI | API 및 HTML 템플릿 서빙 |
| Template Engine | Jinja2 | |
| ORM | SQLAlchemy 2.x | ai-ready-poc와 동일 |
| DB Driver | psycopg 3.x | ai-ready-poc와 동일 |
| Auth | JWT (localStorage 저장) | |
| 서버 | uvicorn | |

### 프론트엔드

| 구분 | 기술 | 비고 |
|------|------|------|
| UI | HTML5, Vanilla JS | 상단 탭 + 좌측 서브메뉴 레이아웃 |
| Styling | Custom CSS (main.css) | ai-ready-poc 스크린샷 스타일 준수 |

### 인프라

| 서비스 | 호스트 | 포트 |
|--------|--------|------|
| FastAPI 포털 (UI+API) | localhost | **6080** |
| PostgreSQL | 192.168.6.13 | **5432** |
| JupyterLab (Docker) | localhost | **6888** |
| MLflow (Docker) | localhost | **6000** |

---

## 2. 주요 기능

| # | 기능 | 설명 |
|---|------|------|
| 1 | **로그인** | JWT 기반 인증 (admin/admin, user/user) |
| 2 | **게시판** | 공지/자료실 CRUD + 파일 첨부 |
| 3 | **Data Query** | PostgreSQL SQL 실행 + 스키마 탐색 |
| 4 | **JupyterLab** | Docker 노트북 목록/열기 |
| 5 | **MLflow** | ML 실험/모델 추적 (iframe 임베딩) |
| 6 | **데이터셋 카탈로그** | 데이터셋/Feature 메타 관리 |
| 7 | **파일 관리** | 로컬 파일시스템 업로드/다운로드 |

---

## 3. 프로젝트 구조

```
mlfoundry/
├── app/
│   ├── main.py                  # FastAPI 앱 팩토리
│   ├── core/
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── security.py          # JWT 인증
│   │   └── database.py          # SQLAlchemy 엔진/세션
│   ├── api/
│   │   ├── routes/
│   │   │   ├── web.py           # HTML 페이지 라우트 (Jinja2)
│   │   │   ├── auth.py          # 로그인/로그아웃 API
│   │   │   ├── board.py         # 게시판 CRUD API
│   │   │   ├── query.py         # SQL 쿼리 실행 API
│   │   │   ├── datasets.py      # 데이터셋 카탈로그 API
│   │   │   ├── jupyter.py       # JupyterLab 연동 API
│   │   │   ├── mlflow_proxy.py  # MLflow API 프록시
│   │   │   └── files.py         # 파일 관리 API
│   │   └── router.py            # 라우터 통합
│   ├── models/                   # SQLAlchemy 모델
│   ├── schemas/                  # Pydantic 스키마
│   ├── services/                 # 비즈니스 로직
│   ├── repositories/            # DB 쿼리 계층
│   ├── templates/               # Jinja2 HTML 템플릿
│   │   ├── base.html            # 상단바 + 사이드바 공통 레이아웃
│   │   ├── login.html           # 로그인 페이지
│   │   └── pages/               # 각 기능별 페이지
│   └── static/                  # 정적 파일
│       ├── css/                 # main.css
│       └── js/                  # app.js (API 호출, 인증)
├── migrations/                   # Alembic DB 마이그레이션
├── docker-compose.yml            # JupyterLab + MLflow
├── requirements.txt
├── .env                          # 환경변수
└── docs/
```

---

## 4. Docker Compose

```yaml
version: '3.8'

services:
  jupyter:
    image: jupyter/scipy-notebook:latest
    container_name: mlfoundry-jupyter
    ports:
      - "6888:8888"
    environment:
      JUPYTER_TOKEN: mlfoundry_token
      JUPYTER_ENABLE_LAB: "yes"
    volumes:
      - jupyter-notebooks:/home/jovyan/work
    restart: unless-stopped

  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.18.0
    container_name: mlfoundry-mlflow
    ports:
      - "6000:5000"
    command: >
      mlflow server
        --backend-store-uri postgresql://ai_ready:${DB_PASSWORD}@192.168.6.13:5432/mlfoundry
        --default-artifact-root /mlflow/artifacts
        --host 0.0.0.0
        --port 5000
    volumes:
      - mlflow-artifacts:/mlflow/artifacts
    restart: unless-stopped

volumes:
  jupyter-notebooks:
  mlflow-artifacts:
```

---

## 5. 환경변수 (.env)

```bash
# DB
DB_HOST=192.168.6.13
DB_PORT=5432
DB_NAME=mlfoundry
DB_USER=ai_ready
DB_PASSWORD=비밀번호별도관리

# 서비스
APP_PORT=6080
STREAMLIT_PORT=6501
JUPYTER_BASE_URL=http://localhost:6888
JUPYTER_TOKEN=mlfoundry_token
MLFLOW_BASE_URL=http://localhost:6000

# 파일
FILE_UPLOAD_DIR=/opt/mlfoundry/files
```

---

## 6. 데이터베이스 (PostgreSQL)

```sql
-- 신규 DB 생성 (192.168.6.13:5432, postgres 슈퍼유저)
CREATE DATABASE mlfoundry OWNER ai_ready;

-- 핵심 테이블 (Alembic 또는 수동 DDL)
-- users, board, board_file, datasets, dataset_features,
-- data_query_history, file_download_log
```

> 테이블 DDL은 SQLAlchemy 모델에서 자동 생성 또는 Alembic 마이그레이션으로 관리.

---

## 7. 개발 순서

| Phase | 할 일 | 비고 |
|-------|------|------|
| **1** | 프로젝트 초기화: FastAPI + SQLAlchemy + .env + docker-compose.yml | 환경 구성 |
| **2** | PostgreSQL DB 생성 + SQLAlchemy 모델 정의 + Alembic 설정 | DB |
| **3** | 인증 (로그인 API + Streamlit 로그인 페이지) | 최우선 |
| **4** | 게시판 CRUD (API + Streamlit 페이지) | 기본 기능 |
| **5** | Data Query (SQL 실행 + 스키마 탐색) | 핵심 |
| **6** | JupyterLab 연동 (노트북 목록/열기) | 핵심 |
| **7** | MLflow 연동 (iframe or REST API) | 핵심 |
| **8** | 데이터셋 카탈로그 | 데이터 |
| **9** | 파일 관리 | 부가 |
| **10** | 통합 테스트 | 완료 |

---

## 8. ai-ready-poc와의 관계

| 항목 | 방침 |
|------|------|
| 기술 스택 | **동일** (FastAPI + SQLAlchemy + Streamlit + PostgreSQL) |
| DB 서버 | **동일** (192.168.6.13:5432), DB만 분리 (ai_ready / mlfoundry) |
| 코드 공유 | 현재는 개별 개발, 추후 공통 모듈(인증, DB 설정) 통합 고려 |
| 수정 범위 | **ai-ready-poc는 읽기 전용** — 절대 수정 금지 |

---

## 9. 서버 가동 절차

```bash
# 1. DB 생성 (최초 1회)
psql -h 192.168.6.13 -p 5432 -U postgres -c "CREATE DATABASE mlfoundry OWNER ai_ready;"

# 2. Python 환경
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. 환경변수
cp .env.example .env   # DB_PASSWORD 등 실제값 입력

# 4. Docker (JupyterLab + MLflow)
docker-compose up -d

# 5. 백엔드
uvicorn app.main:app --host 0.0.0.0 --port 6080 --reload

# 6. Streamlit UI
streamlit run ui/streamlit_app.py --server.port 6501

# 7. 접속
#    API: http://localhost:6080/docs
#    UI:  http://localhost:6501
#    JupyterLab: http://localhost:6888
#    MLflow: http://localhost:6000
```

---

## 부록: 삭제된 v1 계획서 (참조용)

| 문서 | 사유 |
|------|------|
| `aws-proxy-integration-tech-spec.plan.md` | AWS 연동 삭제 |
| `aws-infra-migration.plan.md` | AWS 인프라 전환 삭제 |
| `local-jupyter-ec2.plan.md` | Docker로 대체 |
| `menu-improvement-v2.plan.md` | 로컬 PostgreSQL/MLflow로 대체 |
