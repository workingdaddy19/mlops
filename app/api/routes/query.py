import logging

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db, get_query_service
from app.models.query_history import DataQueryHistory
from app.repositories.query_history_repo import QueryHistoryRepository
from app.schemas.auth import UserRead
from app.schemas.query import AthenaQueryRequest, AthenaTableInfo, QueryHistoryRead, QueryRequest, QueryResult, SchemaInfo
from app.services.athena_service import AthenaService
from app.services.query_service import QueryService

router = APIRouter(prefix="/query", tags=["query"])
logger = logging.getLogger(__name__)


@router.post("/execute", response_model=QueryResult)
def execute_query(
    body: QueryRequest,
    user: UserRead = Depends(get_current_user),
    service: QueryService = Depends(get_query_service),
):
    try:
        return service.execute_query(body.sql, user.username, body.max_rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"쿼리 실행 오류: {e}") from e


@router.get("/schemas", response_model=list[SchemaInfo])
def get_schemas(
    _: UserRead = Depends(get_current_user),
    service: QueryService = Depends(get_query_service),
):
    return service.get_schemas()


@router.get("/history", response_model=list[QueryHistoryRead])
def get_history(
    user: UserRead = Depends(get_current_user),
    service: QueryService = Depends(get_query_service),
):
    return service.get_history(user.username)


# ──────────────────────────────────────────────
# AWS Athena 엔드포인트
# ──────────────────────────────────────────────

@router.get("/athena/databases", response_model=list[AthenaTableInfo])
def get_athena_databases(
    _: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Athena 데이터베이스 및 테이블 목록 조회"""
    try:
        svc = AthenaService(db=db)
        return svc.list_databases()
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Athena 오류: {e}") from e


@router.post("/athena/execute", response_model=QueryResult)
def execute_athena_query(
    body: AthenaQueryRequest,
    user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Athena SELECT 쿼리 실행 (최대 60초)"""
    hist = QueryHistoryRepository(db)

    def _save(status: str, row_count: int | None = None, error: str | None = None):
        hist.create(DataQueryHistory(
            username=user.username, sql_text=body.sql,
            row_count=row_count, status=status, error_message=error,
        ))

    try:
        svc = AthenaService(db=db)
        result = svc.execute_query(body.sql, body.max_rows)
        _save("success", row_count=result["row_count"])
        return QueryResult(**result)
    except ValueError as e:
        _save("error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TimeoutError as e:
        _save("error", error=str(e))
        raise HTTPException(status_code=504, detail=str(e)) from e
    except ConnectionError as e:
        _save("error", error=str(e))
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        _save("error", error=str(e))
        logger.error(f"Athena execute error: {e}")
        raise HTTPException(status_code=500, detail=f"Athena 실행 오류: {e}") from e

