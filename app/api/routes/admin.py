"""Admin API — 사용자 관리 + 시스템 설정 관리 (admin role 전용)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_admin
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User
from app.models.user_permission import VALID_FEATURES
from app.repositories.settings_repo import SettingsRepository
from app.repositories.user_permission_repo import UserPermissionRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import UserRead
from app.services.settings_service import SettingsService, _cache_invalidate

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════

class UserAdminRead(BaseModel):
    id: int
    username: str
    name: str
    role: str
    created_at: str | None = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_user(cls, user) -> "UserAdminRead":
        return cls(
            id=user.id,
            username=user.username,
            name=user.name,
            role=user.role,
            created_at=str(user.created_at) if user.created_at else None,
        )


class UserCreate(BaseModel):
    username: str
    password: str
    name: str = ""
    role: str = "user"


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None


class SettingUpdate(BaseModel):
    value: str


# ═══════════════════════════════════════════
# Users API
# ═══════════════════════════════════════════

@router.get("/users/count")
def count_users(
    db: Session = Depends(get_db),
    _: UserRead = Depends(get_current_user),
):
    """포털 사용자 수 (로그인한 사용자라면 누구나 조회 가능)."""
    repo = UserRepository(db)
    return {"count": len(repo.list_all())}


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _admin: UserRead = Depends(require_admin),
):
    """사용자 목록 조회 (admin only)."""
    repo = UserRepository(db)
    return [UserAdminRead.from_orm_user(u) for u in repo.list_all()]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _admin: UserRead = Depends(require_admin),
):
    """신규 사용자 등록 (admin only)."""
    if body.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="role은 'user' 또는 'admin'만 허용됩니다.")

    repo = UserRepository(db)
    if repo.get_by_username(body.username):
        raise HTTPException(status_code=409, detail=f"사용자명 '{body.username}'이 이미 존재합니다.")

    settings = get_settings()
    secret_key = settings.secret_key.get_secret_value()
    pw_hash = hash_password(body.password, body.username, secret_key)
    display_name = body.name or body.username

    user = User(username=body.username, password_hash=pw_hash, name=display_name, role=body.role)
    created = repo.create(user)
    return UserAdminRead.from_orm_user(created)


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    _admin: UserRead = Depends(require_admin),
):
    """사용자 정보 수정 (name, role) — admin only."""
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    if body.role and body.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="role은 'user' 또는 'admin'만 허용됩니다.")

    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = body.role

    db.commit()
    db.refresh(user)
    return UserAdminRead.from_orm_user(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: UserRead = Depends(require_admin),
):
    """사용자 삭제 — admin only. 자기 자신 삭제 불가."""
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="자기 자신은 삭제할 수 없습니다.")

    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    db.delete(user)
    db.commit()


# ═══════════════════════════════════════════
# Feature Permissions API
# ═══════════════════════════════════════════

class PermissionUpdate(BaseModel):
    features: list[str]


@router.get("/users/{user_id}/permissions", response_model=list[str])
def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: UserRead = Depends(require_admin),
):
    """특정 유저의 기능 권한 목록 (admin only)."""
    return UserPermissionRepository(db).get_by_user(user_id)


@router.put("/users/{user_id}/permissions", response_model=list[str])
def set_user_permissions(
    user_id: int,
    body: PermissionUpdate,
    db: Session = Depends(get_db),
    _admin: UserRead = Depends(require_admin),
):
    """유저 기능 권한 일괄 설정 (admin only). 유효하지 않은 feature는 무시."""
    invalid = [f for f in body.features if f not in VALID_FEATURES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 기능: {invalid}")
    repo = UserRepository(db)
    if not repo.get_by_id(user_id):
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return UserPermissionRepository(db).set_permissions(user_id, body.features)


# ═══════════════════════════════════════════
# Settings API
# ═══════════════════════════════════════════

@router.get("/settings")
def list_settings(
    db: Session = Depends(get_db),
    _admin: UserRead = Depends(require_admin),
):
    """시스템 설정 전체 목록 (admin only)."""
    svc = SettingsService(db)
    rows = svc.list_all()
    return [
        {"key": r.key, "value": r.value, "label": r.label, "group": r.group, "updated_at": r.updated_at}
        for r in rows
    ]


@router.put("/settings/{key}")
def update_setting(
    key: str,
    body: SettingUpdate,
    db: Session = Depends(get_db),
    _admin: UserRead = Depends(require_admin),
):
    """설정값 변경 — 즉시 캐시 무효화하여 서비스에 반영 (admin only)."""
    repo = SettingsRepository(db)
    existing = repo.get(key)
    if not existing:
        raise HTTPException(status_code=404, detail=f"설정 키 '{key}'가 존재하지 않습니다.")

    row = repo.set_value(key, body.value)
    _cache_invalidate(key)
    logger.info("setting updated: key=%s", key)
    return {"key": row.key, "value": row.value, "label": row.label, "group": row.group}
