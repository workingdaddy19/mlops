from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.schemas.auth import UserRead
from app.services.mlflow_service import MlflowService

router = APIRouter(prefix="/mlflow", tags=["mlflow"])


@router.get("/experiments")
async def list_experiments(_: UserRead = Depends(get_current_user)):
    svc = MlflowService()
    try:
        return await svc.list_experiments()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MLflow 연결 오류: {e}") from e


@router.get("/experiments/{experiment_id}/runs")
async def list_runs(experiment_id: str, _: UserRead = Depends(get_current_user)):
    svc = MlflowService()
    try:
        return await svc.list_runs(experiment_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MLflow 연결 오류: {e}") from e


@router.get("/models")
async def list_models(_: UserRead = Depends(get_current_user)):
    svc = MlflowService()
    try:
        return await svc.list_models()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MLflow 연결 오류: {e}") from e


@router.get("/url")
async def mlflow_url(_: UserRead = Depends(get_current_user)):
    svc = MlflowService()
    return {"url": svc.get_ui_url()}


@router.get("/health")
async def mlflow_health():
    svc = MlflowService()
    healthy = await svc.check_health()
    return {"status": "ok" if healthy else "unavailable", "url": svc.get_ui_url()}
