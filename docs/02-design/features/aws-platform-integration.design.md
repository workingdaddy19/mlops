# AWS Platform Integration Design Document

> **Summary**: AWS Athena/S3/JupyterHub 통합 + 불필요 코드 정리 상세 설계
>
> **Project**: MLFoundry (AI 데이터 분석 플랫폼)
> **Version**: 1.0
> **Author**: Claude Code
> **Date**: 2026-05-27
> **Status**: Draft
> **Plan Reference**: [aws-platform-integration.plan.md](../01-plan/features/aws-platform-integration.plan.md)

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | 로컬 파일 시스템 임시 구현, PostgreSQL 전용 EDA Query, iframe 방식 JupyterHub, k8s 설정 불일치 |
| **Solution** | boto3 기반 Athena/S3 서비스 신규 구현, JupyterHub Admin API 토큰 발급, S3 탐색기 UI, 불필요 코드 삭제 |
| **Function/UX Effect** | 데이터 레이크 SELECT 쿼리, 윈도우 탐색기 스타일 S3 브라우저, 개인별 Jupyter 환경(CPU/GPU) 리스트 뷰 |
| **Core Value** | MLOps 플랫폼 AWS 네이티브 통합 — boto3 단일 SDK로 Athena/S3/JupyterHub 일관 연동 |

---

## 1. 전체 아키텍처

### 1.1 컴포넌트 변경 개요

```
현재 (Before)                          변경 후 (After)
─────────────────────────────────────────────────────────────
app/services/
  file_service.py  (로컬 FS)    →  [삭제]
  jupyter_service.py (iframe)   →  jupyter_service.py (Admin API)
  query_service.py (PostgreSQL) →  query_service.py (PostgreSQL 유지)
                                    + athena_service.py (신규)
                                    + s3_service.py (신규)

app/api/routes/
  files.py (로컬 FS)            →  [삭제]
  jupyter.py (url/health)       →  jupyter.py (envs/token 추가)
  query.py (RDB)                →  query.py (Athena 엔드포인트 추가)
                                    + s3_storage.py (신규)

app/templates/pages/
  files.html (업로드 UI)        →  files.html (S3 탐색기 UI)
  jupyter.html (iframe)         →  jupyter.html (환경 리스트 뷰)
  query.html (단순 SQL)         →  query.html (Athena DB 선택 추가)

app/core/
  config.py                     →  config.py (Athena/S3/JupyterHub 설정 추가)

k8s/
  backend-secret.yaml (내부DNS) →  backend-secret.yaml (외부URL + 신규 변수)
  backend-ingress.yaml (잘못됨) →  backend-ingress.yaml (서비스명 mlops)
```

### 1.2 신규 API 엔드포인트

```
[Athena Query]
POST /api/query/athena/execute        SELECT 쿼리 실행 (비동기, polling 방식)
GET  /api/query/athena/databases      DB/테이블 목록
# (서버 측 동기 polling 방식으로 구현 — /status 엔드포인트 불필요)

[S3 Storage]
GET  /api/s3/browse                   파일/폴더 목록 (prefix 파라미터)
GET  /api/s3/download                 Presigned 다운로드 URL 발급

[JupyterHub]
GET  /api/jupyter/envs                사용자별 Jupyter 환경 목록
GET  /api/jupyter/health              헬스체크 (유지)

[삭제]
DELETE /api/files/*                   기존 로컬 파일 API 전체 제거
DELETE /api/jupyter/notebooks/*       기존 notebook API 제거 (미사용)
```

---

## 2. Phase A: 코드 정리 (Code Cleanup)

### 2.1 삭제 대상 파일

| 파일 | 이유 | 대체 |
|------|------|------|
| `app/services/file_service.py` | 로컬 `/uploads` 기반, S3로 대체 | `app/services/s3_service.py` |
| `app/api/routes/files.py` | 로컬 파일 API 전체 | `app/api/routes/s3_storage.py` |

### 2.2 수정 대상 파일

**`app/api/router.py`**
```python
# 변경 전
from app.api.routes import auth, board, datasets, files, jupyter, mlflow_proxy, query, service_token

api_router.include_router(files.router)     # 삭제

# 변경 후
from app.api.routes import auth, board, datasets, jupyter, mlflow_proxy, query, service_token, s3_storage

api_router.include_router(s3_storage.router)  # 추가
```

**`app/api/routes/jupyter.py`** — 미사용 엔드포인트 제거
```python
# 삭제 (미사용)
@router.get("/notebooks")       # 사용 안 함
@router.get("/notebooks/{path}") # 사용 안 함
```

---

## 3. Phase B: AWS Athena 쿼리 통합

### 3.1 `app/services/athena_service.py` (신규)

```python
import boto3
import time
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class AthenaService:
    def __init__(self):
        settings = get_settings()
        self.client = boto3.client(
            "athena",
            region_name=settings.athena_region,
        )
        self.database = settings.athena_database
        self.output_location = settings.athena_s3_output

    def execute_query(self, sql: str, max_rows: int = 500) -> dict:
        """Athena SELECT 쿼리 실행 (동기 방식, 최대 30초 대기)"""
        # 1. 쿼리 제출
        response = self.client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": self.database},
            ResultConfiguration={"OutputLocation": self.output_location},
        )
        query_id = response["QueryExecutionId"]
        logger.info(f"Athena query submitted: {query_id}")

        # 2. 완료 대기 (polling, 최대 30초)
        for _ in range(60):  # 0.5초 간격 × 60 = 30초
            status = self.get_query_status(query_id)
            if status["state"] == "SUCCEEDED":
                break
            elif status["state"] in ("FAILED", "CANCELLED"):
                raise ValueError(f"Athena query failed: {status.get('reason', '')}")
            time.sleep(0.5)
        else:
            raise TimeoutError("Athena query timed out (30s)")

        # 3. 결과 조회
        return self._fetch_results(query_id, max_rows)

    def get_query_status(self, query_id: str) -> dict:
        resp = self.client.get_query_execution(QueryExecutionId=query_id)
        exec_info = resp["QueryExecution"]["Status"]
        return {
            "state": exec_info["State"],
            "reason": exec_info.get("StateChangeReason", ""),
        }

    def _fetch_results(self, query_id: str, max_rows: int) -> dict:
        paginator = self.client.get_paginator("get_query_results")
        pages = paginator.paginate(
            QueryExecutionId=query_id,
            PaginationConfig={"MaxItems": max_rows + 1},
        )
        columns, rows = [], []
        first_page = True
        for page in pages:
            result_rows = page["ResultSet"]["Rows"]
            if first_page:
                columns = [c["VarCharValue"] for c in result_rows[0]["Data"]]
                result_rows = result_rows[1:]  # 헤더 제거
                first_page = False
            for row in result_rows:
                rows.append([c.get("VarCharValue", None) for c in row["Data"]])
        truncated = len(rows) > max_rows
        return {
            "columns": columns,
            "rows": rows[:max_rows],
            "row_count": len(rows[:max_rows]),
            "truncated": truncated,
        }

    def list_databases(self) -> list[dict]:
        """Athena 데이터베이스 및 테이블 목록"""
        resp = self.client.list_databases(CatalogName="AwsDataCatalog")
        databases = []
        for db in resp.get("DatabaseList", []):
            db_name = db["Name"]
            tables = self._list_tables(db_name)
            databases.append({"database": db_name, "tables": tables})
        return databases

    def _list_tables(self, database: str) -> list[str]:
        try:
            resp = self.client.list_table_metadata(
                CatalogName="AwsDataCatalog",
                DatabaseName=database,
            )
            return [t["Name"] for t in resp.get("TableMetadataList", [])]
        except Exception:
            return []
```

### 3.2 `app/api/routes/query.py` 수정 (Athena 엔드포인트 추가)

```python
# 기존 PostgreSQL 엔드포인트 유지 + 아래 추가

from app.services.athena_service import AthenaService

router = APIRouter(prefix="/query", tags=["query"])

@router.get("/athena/databases")
def get_athena_databases(_: UserRead = Depends(get_current_user)):
    """Athena 데이터베이스/테이블 목록"""
    try:
        svc = AthenaService()
        return svc.list_databases()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Athena 연결 오류: {e}")


@router.post("/athena/execute", response_model=QueryResult)
def execute_athena_query(
    body: QueryRequest,
    user: UserRead = Depends(get_current_user),
):
    """Athena SELECT 쿼리 실행"""
    sql = body.sql.strip()
    if not sql.upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="SELECT 쿼리만 허용됩니다.")
    try:
        svc = AthenaService()
        result = svc.execute_query(sql, body.max_rows)
        return QueryResult(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Athena 오류: {e}")
```

### 3.3 `app/schemas/query.py` 수정 (Athena 스키마 추가)

```python
# 기존 스키마 유지 + 추가

class AthenaQueryRequest(BaseModel):
    sql: str
    max_rows: int = 500
    database: str | None = None  # None이면 config 기본 DB 사용

class AthenaTableInfo(BaseModel):
    database: str
    tables: list[str]
```

### 3.4 `app/core/config.py` Athena 설정 추가

```python
# 기존 설정에 추가
athena_region: str = Field(default="ap-northeast-2", alias="ATHENA_REGION")
athena_database: str = Field(default="mlops", alias="ATHENA_DATABASE")
athena_s3_output: str = Field(
    default="s3://s3-an2-mlflow/athena-results/",
    alias="ATHENA_S3_OUTPUT"
)
```

### 3.5 `app/templates/pages/query.html` UI 수정 — Athena 탭 추가

```
현재 UI:
┌─────────────────────────────────────────┐
│  SQL 쿼리 실행                          │
│  [textarea: SELECT * FROM users...]     │
│  [실행 버튼]                            │
└─────────────────────────────────────────┘

변경 후 UI:
┌─────────────────────────────────────────┐
│  [ PostgreSQL ] [ AWS Athena ]  ← 탭   │
├─────────────────────────────────────────┤
│  (Athena 탭 선택 시)                   │
│  DB: [드롭다운 ▼]  테이블: [드롭다운 ▼] │
│  [textarea: SELECT * FROM ... ]         │
│  [실행 버튼]  ← Athena API 호출         │
└─────────────────────────────────────────┘
```

---

## 4. Phase C: S3 스토리지 통합

### 4.1 `app/services/s3_service.py` (신규)

```python
import boto3
import logging
from datetime import datetime
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        settings = get_settings()
        self.s3 = boto3.client("s3", region_name=settings.s3_region)
        self.bucket = settings.s3_bucket_name

    def browse(self, prefix: str = "") -> dict:
        """
        S3 버켓 탐색 — 현재 prefix의 폴더와 파일 목록 반환
        Returns: {"folders": [...], "files": [...]}
        """
        # prefix 정규화 (빈 문자열 또는 '/'로 끝나야 함)
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        resp = self.s3.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix,
            Delimiter="/",
            MaxKeys=1000,
        )

        folders = []
        for cp in resp.get("CommonPrefixes", []):
            folder_key = cp["Prefix"]
            folder_name = folder_key.rstrip("/").split("/")[-1]
            folders.append({
                "name": folder_name,
                "prefix": folder_key,
                "type": "folder",
            })

        files = []
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key == prefix:  # prefix 자체는 제외
                continue
            name = key.split("/")[-1]
            if not name:
                continue
            files.append({
                "name": name,
                "key": key,
                "size": obj["Size"],
                "size_display": self._format_size(obj["Size"]),
                "last_modified": obj["LastModified"].strftime("%Y-%m-%d %H:%M"),
                "type": "file",
            })

        return {
            "prefix": prefix,
            "folders": folders,
            "files": files,
            "bucket": self.bucket,
        }

    def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """파일 다운로드용 Presigned URL 생성 (기본 1시간)"""
        url = self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
```

### 4.2 `app/api/routes/s3_storage.py` (신규)

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import get_current_user
from app.schemas.auth import UserRead
from app.services.s3_service import S3Service

router = APIRouter(prefix="/s3", tags=["s3"])


@router.get("/browse")
def browse_s3(
    prefix: str = Query(default="", description="S3 경로 prefix"),
    _: UserRead = Depends(get_current_user),
):
    """S3 버켓 파일/폴더 목록 조회"""
    try:
        svc = S3Service()
        return svc.browse(prefix)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"S3 연결 오류: {e}")


@router.get("/download")
def get_download_url(
    key: str = Query(..., description="S3 객체 키"),
    _: UserRead = Depends(get_current_user),
):
    """파일 다운로드 Presigned URL 발급 (1시간 유효)"""
    try:
        svc = S3Service()
        url = svc.get_presigned_url(key)
        return {"url": url, "expires_in": 3600}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"S3 URL 생성 오류: {e}")
```

### 4.3 `app/core/config.py` S3 설정 추가

```python
s3_bucket_name: str = Field(default="s3-an2-mlflow", alias="S3_BUCKET_NAME")
s3_region: str = Field(default="ap-northeast-2", alias="S3_REGION")
```

### 4.4 `app/templates/pages/files.html` — S3 탐색기 UI (전면 교체)

```
┌─────────────────────────────────────────────────────────────────┐
│  S3 스토리지  (버켓: s3-an2-mlflow)      [새로고침 🔄]         │
├──────────────────┬──────────────────────────────────────────────┤
│  📁 폴더 트리    │  📄 파일 목록                                │
│                  │                                              │
│  📁 / (루트)     │  이름          │ 크기      │ 수정일          │
│  ├─📁 data/      │  📁 checkpoints│   -       │ 2026-05-20     │
│  │  └─📁 raw/    │  📄 model.pkl  │  2.3 MB   │ 2026-05-21     │
│  ├─📁 mlflow/    │  📄 config.yaml│  1.1 KB   │ 2026-05-22     │
│  │  ├─📁 models/ │  📄 train.log  │ 45.2 KB   │ 2026-05-23     │
│  │  └─📁 runs/   │                │           │                │
│  └─📁 notebooks/ │   [다운로드 링크: 파일명 클릭 → Presigned]  │
│                  │                                              │
│  (+ 클릭으로     │   업로드 기능 없음 (읽기 전용)               │
│   폴더 펼치기)   │                                              │
└──────────────────┴──────────────────────────────────────────────┘

동작:
- 좌측 트리: + 클릭 → API /api/s3/browse?prefix=data/ 호출 → 하위 폴더 로드
- 우측 목록: 트리에서 폴더 선택 시 해당 prefix의 파일/폴더 표시
- 파일명 클릭: /api/s3/download?key=data/model.pkl → Presigned URL → 새 탭에서 다운로드
```

### 4.5 `app/templates/base.html` 메뉴명 변경

```html
<!-- 변경 전 -->
<a href="/files" class="nav-tab ...">파일 관리</a>
...
<div class="sidebar-section-title">파일 관리</div>
<a href="/files" ...><span class="icon">📁</span> 업로드/다운로드</a>

<!-- 변경 후 -->
<a href="/files" class="nav-tab ...">S3 스토리지</a>
...
<div class="sidebar-section-title">S3 스토리지</div>
<a href="/files" ...><span class="icon">🗄️</span> 파일 탐색</a>
```

---

## 5. Phase D: JupyterHub 개인별 접속 개선

### 5.1 JupyterHub Admin API 토큰 발급 방식

**현재 방식 (iframe)**:
```
포탈 → GET /api/jupyter/url → iframe src 설정 → 로드 실패 (CSP)
```

**개선 방식 (Admin API)**:
```
포탈 사용자 → GET /api/jupyter/envs
  → JupyterHub Admin API 호출:
       POST http://jupyterhub.mlops.click/hub/api/users/{username}/tokens
       Authorization: token {JUPYTERHUB_ADMIN_TOKEN}
  → 토큰 발급 후 환경별 URL 조합:
       CPU: http://jupyterhub.mlops.click/user/{username}/lab/?token={token}
       GPU: http://jupyterhub.mlops.click/user/{username}/gpu/lab/?token={token}
  → 리스트 반환 → 프론트엔드 카드 뷰 표시 → "새 탭에서 열기"
```

> **참고 - JupyterHub Named Server URL 규칙**:
> - 기본 서버: `/user/{username}/lab/`
> - Named 서버: `/user/{username}/{server_name}/lab/`
> - GPU pod는 named server `gpu`로 spawning 예정

### 5.2 `app/services/jupyter_service.py` 수정

```python
import httpx
import json
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class JupyterService:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.jupyter_base_url  # http://jupyterhub.mlops.click
        self.admin_token = settings.jupyterhub_admin_token
        self.envs_config = json.loads(settings.jupyter_envs)
        # 예: [{"name": "CPU 환경", "server": ""}, {"name": "GPU 환경", "server": "gpu"}]

    async def get_user_envs(self, username: str) -> list[dict]:
        """사용자별 Jupyter 환경 목록 + 접속 URL 반환"""
        try:
            # JupyterHub Admin API로 사용자 토큰 발급
            token = await self._get_user_token(username)
        except Exception as e:
            logger.warning(f"JupyterHub token API failed: {e}. Returning URL without token.")
            token = None

        envs = []
        for env_cfg in self.envs_config:
            server = env_cfg.get("server", "")
            if server:
                # Named server: /user/{username}/{server}/lab/
                lab_path = f"/user/{username}/{server}/lab/"
            else:
                # Default server: /user/{username}/lab/
                lab_path = f"/user/{username}/lab/"

            url = f"{self.base_url}{lab_path}"
            if token:
                url += f"?token={token}"

            envs.append({
                "name": env_cfg["name"],
                "server": server,
                "url": url,
                "lab_path": lab_path,
            })

        return envs

    async def _get_user_token(self, username: str) -> str:
        """JupyterHub Admin API로 사용자 액세스 토큰 발급"""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/hub/api/users/{username}/tokens",
                headers={
                    "Authorization": f"token {self.admin_token}",
                    "Content-Type": "application/json",
                },
                json={"note": "MLFoundry portal access", "expires_in": None},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["token"]

    async def check_health(self) -> bool:
        """JupyterHub Hub API 상태 확인"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.base_url}/hub/api/",
                    headers={"Authorization": f"token {self.admin_token}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def get_lab_url(self, username: str = "admin", path: str = "") -> str:
        """기본 lab URL (하위 호환)"""
        if path:
            return f"{self.base_url}/user/{username}/lab/tree/{path}"
        return f"{self.base_url}/user/{username}/lab/"
```

### 5.3 `app/api/routes/jupyter.py` 수정

```python
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_user
from app.schemas.auth import UserRead
from app.services.jupyter_service import JupyterService

router = APIRouter(prefix="/jupyter", tags=["jupyter"])


@router.get("/envs")
async def get_jupyter_envs(current_user: UserRead = Depends(get_current_user)):
    """사용자의 Jupyter 환경 목록 (CPU/GPU 등) + 접속 URL"""
    svc = JupyterService()
    try:
        envs = await svc.get_user_envs(current_user.username)
        return {"username": current_user.username, "envs": envs}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"JupyterHub 연결 오류: {e}")


@router.get("/health")
async def jupyter_health():
    """JupyterHub 헬스체크"""
    svc = JupyterService()
    healthy = await svc.check_health()
    return {"status": "ok" if healthy else "unavailable"}
```

### 5.4 `app/templates/pages/jupyter.html` — 리스트 뷰 (전면 교체)

```
현재 UI (iframe):
┌───────────────────────────────────────────┐
│ JupyterLab 접속         [새 탭에서 열기]  │
│ JupyterLab URL: http://...               │
│ ┌─────────────────────────────────────┐  │
│ │   iframe (대부분 로드 실패)          │  │
│ └─────────────────────────────────────┘  │
└───────────────────────────────────────────┘

변경 후 UI (리스트 뷰):
┌───────────────────────────────────────────────────┐
│ ML Analysis — Jupyter 환경                        │
├───────────────────────────────────────────────────┤
│ 🖥️ CPU 환경                                       │
│ URL: http://jupyterhub.mlops.click/user/admin/lab/│
│ [새 탭에서 열기 🔗]                               │
├───────────────────────────────────────────────────┤
│ 🎮 GPU 환경                                       │
│ URL: http://jupyterhub.mlops.click/user/admin/gpu/│
│ [새 탭에서 열기 🔗]                               │
└───────────────────────────────────────────────────┘
```

### 5.5 `app/core/config.py` JupyterHub Admin 설정 추가

```python
jupyterhub_admin_token: str = Field(default="", alias="JUPYTERHUB_ADMIN_TOKEN")
jupyter_envs: str = Field(
    default='[{"name":"CPU 환경","server":""},{"name":"GPU 환경","server":"gpu"}]',
    alias="JUPYTER_ENVS"
)
```

---

## 6. k8s 설정 변경

### 6.1 `k8s/backend-secret.yaml` 최종 상태

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: backend-secret
  namespace: mlops
type: Opaque
stringData:
  # DB
  DB_HOST: "rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com"
  DB_PORT: "5432"
  DB_NAME: "mlops"
  DB_USER: "mlops"
  DB_PASSWORD: "kyobo11!"
  # 서비스 외부 URL (수정됨)
  MLFLOW_BASE_URL: "http://mlflow.mlops.click"
  JUPYTER_BASE_URL: "http://jupyterhub.mlops.click"
  JUPYTER_TOKEN: "mlfoundry_token"
  # AWS Athena (신규)
  ATHENA_REGION: "ap-northeast-2"
  ATHENA_DATABASE: "mlops"
  ATHENA_S3_OUTPUT: "s3://s3-an2-mlflow/athena-results/"
  # AWS S3 (신규)
  S3_BUCKET_NAME: "s3-an2-mlflow"
  S3_REGION: "ap-northeast-2"
  # JupyterHub Admin API (신규)
  JUPYTERHUB_ADMIN_TOKEN: "실제_admin_token_입력"
  JUPYTER_ENVS: '[{"name":"CPU 환경","server":""},{"name":"GPU 환경","server":"gpu"}]'
```

### 6.2 AWS IAM 권한 요구사항

EKS Pod (IRSA 또는 Node IAM Role)에 다음 권한 필요:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:ListDatabases",
        "athena:ListTableMetadata",
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:GetTables"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::s3-an2-mlflow",
        "arn:aws:s3:::s3-an2-mlflow/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::s3-an2-mlflow/athena-results/*"
    }
  ]
}
```

---

## 7. requirements.txt 변경

```txt
# 기존 유지
fastapi
uvicorn
sqlalchemy
psycopg
pydantic
pydantic-settings
httpx
python-jose
passlib
python-multipart

# 신규 추가
boto3>=1.34.0          # AWS SDK (Athena, S3)
```

---

## 8. 파일 변경 요약

### 신규 생성 (4개)

| 파일 | 설명 |
|------|------|
| `app/services/athena_service.py` | AWS Athena 쿼리 서비스 |
| `app/services/s3_service.py` | AWS S3 탐색/다운로드 서비스 |
| `app/api/routes/s3_storage.py` | S3 스토리지 API 라우터 |
| `docs/02-design/features/aws-platform-integration.design.md` | 본 문서 |

### 수정 (9개)

| 파일 | 변경 내용 |
|------|-----------|
| `app/core/config.py` | Athena/S3/JupyterHub Admin 설정 추가 |
| `app/api/router.py` | files 라우터 제거, s3_storage 라우터 추가 |
| `app/api/routes/query.py` | Athena 엔드포인트 추가 |
| `app/api/routes/jupyter.py` | `/envs` 엔드포인트 추가, 미사용 제거 |
| `app/services/jupyter_service.py` | Admin API 토큰 발급 방식으로 교체 |
| `app/schemas/query.py` | Athena 스키마 추가 |
| `app/templates/pages/query.html` | Athena 탭 추가 |
| `app/templates/pages/files.html` | S3 탐색기 UI 전면 교체 |
| `app/templates/pages/jupyter.html` | 리스트 뷰 전면 교체 |
| `app/templates/base.html` | 메뉴명 변경 |
| `k8s/backend-secret.yaml` | 외부 URL + Athena/S3/JupyterHub 환경변수 추가 |
| `requirements.txt` | boto3 추가 |

### 삭제 (2개)

| 파일 | 이유 |
|------|------|
| `app/services/file_service.py` | 로컬 FS 기반, S3로 대체 |
| `app/api/routes/files.py` | 로컬 파일 API, S3 라우터로 대체 |

---

## 9. 구현 체크리스트 (Do Phase용)

### Phase A: 코드 정리
- [ ] `app/services/file_service.py` 삭제
- [ ] `app/api/routes/files.py` 삭제
- [ ] `app/api/router.py` import/include 정리
- [ ] `app/api/routes/jupyter.py` 미사용 엔드포인트 제거

### Phase B: Athena 통합
- [ ] `requirements.txt`에 `boto3` 추가
- [ ] `app/services/athena_service.py` 생성
- [ ] `app/core/config.py` Athena 설정 추가
- [ ] `app/schemas/query.py` Athena 스키마 추가
- [ ] `app/api/routes/query.py` Athena 엔드포인트 추가
- [ ] `app/templates/pages/query.html` Athena 탭 UI 추가
- [ ] `k8s/backend-secret.yaml` Athena 환경변수 추가

### Phase C: S3 통합
- [ ] `app/services/s3_service.py` 생성
- [ ] `app/api/routes/s3_storage.py` 생성
- [ ] `app/core/config.py` S3 설정 추가
- [ ] `app/api/router.py` s3_storage 라우터 등록
- [ ] `app/templates/pages/files.html` S3 탐색기 UI 교체
- [ ] `app/templates/base.html` 메뉴명 변경
- [ ] `k8s/backend-secret.yaml` S3 환경변수 추가

### Phase D: JupyterHub 개선
- [ ] `app/core/config.py` JupyterHub Admin 설정 추가
- [ ] `app/services/jupyter_service.py` Admin API 방식 교체
- [ ] `app/api/routes/jupyter.py` `/envs` 추가
- [ ] `app/templates/pages/jupyter.html` 리스트 뷰 교체
- [ ] `k8s/backend-secret.yaml` `JUPYTERHUB_ADMIN_TOKEN` 추가
- [ ] EC2 동기화 및 Docker 재빌드

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-05-27 | Initial design | Claude Code |
