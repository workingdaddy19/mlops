import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.service_token import ServiceToken
from app.schemas.auth import UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

ALLOWED_SERVICES = {"jupyter", "mlflow"}


@router.post("/service-token/{service}")
def get_service_token(
    service: str,
    current_user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """사용자 서비스 토큰 발급 또는 조회"""

    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service: {service}")

    # DB에서 기존 토큰 조회
    token_record = db.query(ServiceToken).filter(
        ServiceToken.user_id == current_user.id,
        ServiceToken.service == service
    ).first()

    # 없으면 새로 생성
    if not token_record:
        token_value = f"{service}_{current_user.username}_{uuid4().hex[:16]}"
        token_record = ServiceToken(
            user_id=current_user.id,
            service=service,
            token=token_value
        )
        db.add(token_record)
        db.commit()
        db.refresh(token_record)
        logger.info(f"✅ Service token created: user={current_user.username}, service={service}")
    else:
        logger.info(f"✅ Service token retrieved: user={current_user.username}, service={service}")

    return {
        "service": service,
        "token": token_record.token,
        "created_at": token_record.created_at,
        "updated_at": token_record.updated_at,
    }


@router.get("/service-token/{service}/redirect")
def redirect_to_service(
    service: str,
    current_user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """서비스로 자동 리다이렉트"""

    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service: {service}")

    # 토큰 발급/조회 (DB 기록 목적 — URL에는 username 기반 경로 사용)
    get_service_token(service, current_user, db)

    settings = get_settings()

    if service == "jupyter":
        # JupyterHub 표준 경로: /user/{username}/lab/
        redirect_url = f"{settings.jupyter_base_url}/user/{current_user.username}/lab/"
    elif service == "mlflow":
        redirect_url = settings.mlflow_base_url

    logger.info(f"🔄 Redirect to service: user={current_user.username}, service={service}, url={redirect_url}")

    return RedirectResponse(url=redirect_url, status_code=302)