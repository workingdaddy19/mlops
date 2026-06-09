import logging
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_auth_service, get_current_user, get_db
from app.models.user_permission import VALID_FEATURES
from app.repositories.user_permission_repo import UserPermissionRepository
from app.schemas.auth import LoginResponse, UserRead
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    username: str = Form(),
    password: str = Form(),
    service: AuthService = Depends(get_auth_service),
):
    logger.info(f"📝 Login attempt: username={username}")
    try:
        result = service.login(username, password)
        logger.info(f"✅ Login success: username={username}")
        return result
    except ValueError as e:
        logger.error(f"❌ Login failed: username={username}, error={str(e)}")
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.get("/me", response_model=UserRead)
def me(current_user: UserRead = Depends(get_current_user)):
    return current_user


@router.get("/me/permissions", response_model=list[str])
def my_permissions(
    current_user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """현재 로그인 유저의 허용된 기능 목록. admin은 전체 반환."""
    if current_user.role == "admin":
        return sorted(VALID_FEATURES)
    return UserPermissionRepository(db).get_by_user(current_user.id)