from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_feature
from app.schemas.auth import UserRead
from app.services.airflow_service import AirflowService

router = APIRouter(prefix="/airflow", tags=["airflow"])


@router.get("/health")
async def airflow_health(db: Session = Depends(get_db)):
    svc = AirflowService(db=db)
    healthy = await svc.check_health()
    return {"status": "ok" if healthy else "unavailable", "url": svc.get_ui_url()}


@router.get("/sso")
async def airflow_sso(
    _: UserRead = Depends(require_feature("airflow")),
    db: Session = Depends(get_db),
):
    """Airflow 자동 로그인 — 세션 쿠키 포함 302 Redirect."""
    svc = AirflowService(db=db)
    target_url = svc.get_ui_url()
    session_cookie = await svc.get_session_cookie()

    response = RedirectResponse(url=target_url, status_code=302)
    if session_cookie:
        domain = urlparse(target_url).hostname
        response.set_cookie(
            key="session",
            value=session_cookie,
            domain=domain,
            httponly=True,
            samesite="lax",
        )
    return response
