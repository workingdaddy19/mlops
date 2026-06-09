# mlfoundry 프로젝트 설계 문서 (v2)

> Plan 문서 참조: [mlfoundry.plan.md](../../01-plan/features/mlfoundry.plan.md)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | mlfoundry - 로컬 ML 데이터 플랫폼 포털 |
| **설계일** | 2026-04-04 (2026-04-24 v2 Python 전환) |
| **서버 환경** | Ubuntu Linux (로컬 서버 단독) |
| **기술 스택** | Python + FastAPI + SQLAlchemy + Streamlit |
| **UI 참조** | ai-ready-poc Streamlit 패턴 |

---

## 1. 시스템 아키텍처

### 1.1 전체 구성도

```
┌──────────────────────────────────────────────────────┐
│                   사용자 브라우저                      │
└──────────────────────────┬───────────────────────────┘
                           │ :6080 (HTML + REST API)
            ┌──────────────▼──────────────┐
            │       FastAPI Portal        │
            │  (Jinja2 Templates + API)   │
            └──────────────┬──────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
   ┌────────▼────────┐  ┌──▼──────────┐  ┌──▼──────────┐
   │  PostgreSQL     │  │  JupyterLab │  │  MLflow     │
   │  192.168.6.13   │  │  Docker     │  │  Docker     │
   │  :5432          │  │  :6888      │  │  :6000      │
   └─────────────────┘  └─────────────┘  └─────────────┘
```

### 1.2 레이어 아키텍처

```
Web Route (app/api/routes/web.py) → Jinja2 Templates (app/templates/)
                                          │ (fetch API)
                                          ▼
API Route (app/api/routes/*) → Service → Repository → DB
```

---

## 2. UI 설계 (FastAPI + Jinja2)

### 2.1 레이아웃 구조 (base.html)

스크린샷 기준 전문 포털 레이아웃 구현:

```
┌─────────────────────────────────────────────────────────────┐
│ [F] MLFoundry             Data | AI ML | 게시판 | 파일    Admin admin [로그아웃] │
├──────────────────┬──────────────────────────────────────────┤
│ 사이드바          │  브레드크럼                               │
│ (탭별 서브메뉴)    ├──────────────────────────────────────────┤
│                  │                                          │
│  ○ 메뉴 1        │  메인 콘텐츠 영역                         │
│  ● 메뉴 2 (Active)│  (Jinja2 block content)                  │
│  ○ 메뉴 3        │                                          │
│                  │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

### 2.2 디자인 토큰 (main.css)

| Token | 값 | 용도 |
|-------|----|------|
| primary | `#0d9488` | 탭 활성, 버튼 (teal-600) |
| primary-hover | `#0f766e` | Hover (teal-700) |
| bg-nav | `#ffffff` | 상단바 배경 |
| bg-sidebar | `#f8fafc` | 좌측 사이드바 배경 |
| border | `#e2e8f0` | 테두리 |
| text-primary | `#0f172a` | 주요 텍스트 |

### 2.3 탭 및 메뉴 구성

| 상단 탭 | 좌측 서브메뉴 | 링크 |
|---------|--------------|------|
| **Data** | EDA (SQL Query) | `/data/query` |
|          | 데이터셋 카탈로그 | `/data/datasets` |
| **AI ML** | ML Analysis (JupyterLab) | `/aiml/jupyter` |
|           | MLflow 실험 | `/aiml/mlflow` |
| **게시판** | 공지/자료실 | `/board` |
| **파일** | 업로드/다운로드 | `/files` |

### 2.4 클라이언트 사이드 로직 (app.js)

- **인증**: 로그인 성공 시 JWT를 `localStorage`의 `mf_token`에 저장.
- **API 호출**: `fetch()` 사용 시 `Authorization: Bearer <token>` 헤더 자동 첨부.
- **인터랙션**: 데이터 테이블 렌더링, 폼 제출, 파일 업로드 등 Vanilla JS 처리.

---

## 3. API 설계 (FastAPI)

> REST API 설계는 v2와 동일하게 유지됨.
> 단, UI 페이지 서빙을 위한 `/` 및 `/login` 등 Web 라우트 추가.

### 3.1 Web 라우트 목록 (web.py)

| Method | Path | Template | 설명 |
|--------|------|----------|------|
| GET | `/` | (Redirect) | `/data/query`로 이동 |
| GET | `/login` | `login.html` | 로그인 페이지 |
| GET | `/data/query` | `pages/query.html` | SQL 실행 페이지 |
| GET | `/aiml/jupyter`| `pages/jupyter.html`| JupyterLab 페이지 |
| ... | ... | ... | ... |

---

## 4. 프로젝트 구조 (v2 개편)

```
mlfoundry/
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── web.py           # UI 페이지 라우트
│   ├── templates/               # Jinja2 템플릿
│   │   ├── base.html            # 공통 레이아웃
│   │   ├── login.html           # 로그인
│   │   └── pages/               # 기능별 상세 페이지
│   └── static/                  # 정적 파일
│       ├── css/main.css         # 스타일
│       └── js/app.js            # 클라이언트 로직
```

---

## 5. DB 스키마 (PostgreSQL)

### 5.1 users

```sql
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    user_id     VARCHAR(100) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,       -- bcrypt
    name        VARCHAR(100),
    email       VARCHAR(200),
    role        VARCHAR(20) NOT NULL DEFAULT 'USER',   -- ADMIN / USER
    department  VARCHAR(100),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO users (user_id, password, name, role)
VALUES ('admin', '$2b$12$...', 'Admin', 'ADMIN')
ON CONFLICT (user_id) DO NOTHING;
```

### 5.2 board / board_file

```sql
CREATE TABLE board (
    id          BIGSERIAL PRIMARY KEY,
    board_type  VARCHAR(20) NOT NULL DEFAULT 'notice',
    title       VARCHAR(300) NOT NULL,
    content     TEXT,
    author_id   VARCHAR(100) NOT NULL,
    view_count  INT NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE board_file (
    id          BIGSERIAL PRIMARY KEY,
    board_id    BIGINT NOT NULL REFERENCES board(id) ON DELETE CASCADE,
    file_name   VARCHAR(500) NOT NULL,
    file_path   VARCHAR(1000) NOT NULL,
    file_size   BIGINT,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.3 datasets / dataset_features

```sql
CREATE TABLE datasets (
    id            VARCHAR(36) PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    version       VARCHAR(50) NOT NULL DEFAULT '1.0',
    description   TEXT,
    source_type   VARCHAR(50),
    source_uri    TEXT,
    row_count     BIGINT,
    column_count  INT,
    tags          JSONB,
    owner         VARCHAR(100),
    quality_score NUMERIC(5,2),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE dataset_features (
    id          VARCHAR(36) PRIMARY KEY,
    dataset_id  VARCHAR(36) NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,
    dtype       VARCHAR(50) NOT NULL,
    description TEXT,
    stats       JSONB,
    is_target   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.4 data_query_history

```sql
CREATE TABLE data_query_history (
    id          BIGSERIAL PRIMARY KEY,
    user_id     VARCHAR(100) NOT NULL,
    query_sql   TEXT,
    status      VARCHAR(20),
    row_count   INT DEFAULT 0,
    duration_ms BIGINT DEFAULT 0,
    error_msg   TEXT,
    executed_at TIMESTAMP DEFAULT NOW()
);
```

### 5.5 file_download_log

```sql
CREATE TABLE file_download_log (
    id            BIGSERIAL PRIMARY KEY,
    user_id       VARCHAR(100) NOT NULL,
    file_path     VARCHAR(1000) NOT NULL,
    reason        TEXT,
    downloaded_at TIMESTAMP DEFAULT NOW()
);
```

---

## 6. SQLAlchemy 모델 예시

```python
# app/models/user.py
from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    name = Column(String(100))
    email = Column(String(200))
    role = Column(String(20), nullable=False, default="USER")
    department = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

---

## 7. 설정 (pydantic-settings)

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # DB
    DB_HOST: str = "192.168.6.13"
    DB_PORT: int = 5432
    DB_NAME: str = "mlfoundry"
    DB_USER: str = "ai_ready"
    DB_PASSWORD: str = ""

    # App
    APP_PORT: int = 6080
    SECRET_KEY: str = "change-me"

    # Jupyter
    JUPYTER_BASE_URL: str = "http://localhost:6888"
    JUPYTER_TOKEN: str = "mlfoundry_token"
    JUPYTER_ENABLED: bool = True

    # MLflow
    MLFLOW_BASE_URL: str = "http://localhost:6000"
    MLFLOW_ENABLED: bool = True

    # File
    FILE_UPLOAD_DIR: str = "/opt/mlfoundry/files"

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
```

---

## 8. 서비스 연동 설계

### 8.1 JupyterLab 연동 (jupyter_service.py)

```python
import httpx

class JupyterService:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"token {token}"}

    async def list_notebooks(self, path: str = "") -> list:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/api/contents/{path}",
                headers=self.headers
            )
            return r.json().get("content", [])

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{self.base_url}/api/status", headers=self.headers)
                return r.status_code == 200
        except:
            return False
```

### 8.2 MLflow 연동 (mlflow_service.py)

```python
class MlflowService:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def list_experiments(self) -> list:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}/api/2.0/mlflow/experiments/search")
            return r.json().get("experiments", [])

    async def list_runs(self, experiment_id: str) -> list:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base_url}/api/2.0/mlflow/runs/search",
                json={"experiment_ids": [experiment_id]}
            )
            return r.json().get("runs", [])

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{self.base_url}/health")
                return r.status_code == 200
        except:
            return False
```

### 8.3 Query 서비스 (query_service.py)

```python
from sqlalchemy import text

class QueryService:
    def __init__(self, engine):
        self.engine = engine

    def execute_query(self, sql: str, limit: int = 100) -> dict:
        """읽기 전용 SQL 실행"""
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchmany(limit)]
            return {"columns": columns, "rows": rows, "row_count": len(rows)}

    def get_schemas(self) -> list:
        sql = "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema')"
        with self.engine.connect() as conn:
            return [r[0] for r in conn.execute(text(sql))]

    def get_tables(self, schema: str = "public") -> list:
        sql = "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"
        with self.engine.connect() as conn:
            return [r[0] for r in conn.execute(text(sql), {"schema": schema})]
```

---

## 9. 상태 배지 / 컴포넌트 (Streamlit)

### 9.1 상태 배지

```python
def status_badge(status: str):
    colors = {
        "running": ("🟢", "실행중"),
        "stopped": ("⚪", "중지됨"),
        "error":   ("🔴", "오류"),
    }
    icon, label = colors.get(status, ("⚪", status))
    st.markdown(f"{icon} **{label}**")
```

### 9.2 데이터 테이블

```python
# 쿼리 결과 표시
result = api.execute_query(sql)
st.dataframe(
    result["rows"],
    use_container_width=True,
    hide_index=True,
)
st.caption(f"{result['row_count']} rows, {result['duration_ms']}ms")
```

### 9.3 메트릭 카드

```python
# 대시보드 서비스 상태
col1, col2, col3, col4 = st.columns(4)
col1.metric("PostgreSQL", "● 연결됨" if db_ok else "○ 연결 실패")
col2.metric("JupyterLab", "● 실행중" if jupyter_ok else "○ 중지")
col3.metric("MLflow", "● 실행중" if mlflow_ok else "○ 중지")
col4.metric("API", "● 정상" if api_ok else "○ 오류")
```

---

## 10. ai-ready-poc 호환 설계 포인트

향후 통합을 고려하여 ai-ready-poc와 동일한 패턴을 적용:

| 항목 | ai-ready-poc | mlfoundry (동일 적용) |
|------|-------------|----------------------|
| 레이어 규칙 | Route → Service → Repository | 동일 |
| 설정 | pydantic-settings + .env | 동일 |
| DB | SQLAlchemy 2.x + psycopg | 동일 |
| 인증 | JWT (login → token) | 동일 |
| 코딩 컨벤션 | snake_case, PascalCase, type hints | 동일 |
| 테스트 | pytest + httpx | 동일 |
| UI | Streamlit (pages/ 구조) | 동일 |

---

## 부록: v1 설계서에서 삭제된 항목

| 항목 | 사유 |
|------|------|
| Spring Security / Thymeleaf / MyBatis | Python 전환 |
| AWS SDK Agent 계층 | AWS 연동 삭제 |
| Ollama LLM 서비스 | 삭제 |
| SSO Filter / DRM | 삭제 |
| SageMaker 상태 뱃지 CSS | SageMaker 삭제 |
| S3 파일 트리 (jsTree) | 로컬 파일시스템으로 대체 |
| QuickSight iframe | MLflow iframe으로 대체 |
