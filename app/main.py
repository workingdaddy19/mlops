from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.api.routes.web import router as web_router
from app.core.config import get_settings
from app.core.database import Base, get_engine
from app.services.auth_service import ensure_default_users
from app.services.settings_seed import ensure_default_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    ensure_default_users(engine)
    ensure_default_settings(engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="AI 데이터 분석 - 엔터프라이즈 데이터 분석 플랫폼",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.mount("/static", StaticFiles(directory="app/static"), name="static")
    application.include_router(web_router)
    application.include_router(api_router)

    @application.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "service": settings.app_name}

    return application


app = create_app()
