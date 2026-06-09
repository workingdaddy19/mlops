from fastapi import APIRouter

from app.api.routes import airflow, auth, board, datasets, inference, jupyter, mlflow_proxy, query, s3_storage, service_token
from app.api.routes.admin import router as admin_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(service_token.router)
api_router.include_router(board.router)
api_router.include_router(query.router)
api_router.include_router(datasets.router)
api_router.include_router(jupyter.router)
api_router.include_router(mlflow_proxy.router)
api_router.include_router(airflow.router)
api_router.include_router(s3_storage.router)
api_router.include_router(inference.router)
api_router.include_router(admin_router)
