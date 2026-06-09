from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db  # noqa: F401 — re-exported for admin routes
from app.repositories.board_repo import BoardRepository
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.query_history_repo import QueryHistoryRepository
from app.repositories.user_permission_repo import UserPermissionRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import UserRead
from app.services.auth_service import AuthService
from app.services.board_service import BoardService
from app.services.dataset_service import DatasetService
from app.services.query_service import QueryService

http_bearer = HTTPBearer(auto_error=False)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    settings = get_settings()
    return AuthService(
        user_repo=UserRepository(db),
        secret_key=settings.secret_key.get_secret_value(),
        ttl_minutes=settings.access_token_ttl_minutes,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    service: AuthService = Depends(get_auth_service),
) -> UserRead:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다.")
    try:
        return service.get_current_user(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


def require_admin(current_user: UserRead = Depends(get_current_user)) -> UserRead:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")
    return current_user


def require_feature(feature: str):
    """기능별 권한 체크 Depends 팩토리. admin은 자동 허용."""
    def _check(
        current_user: UserRead = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> UserRead:
        if current_user.role == "admin":
            return current_user
        repo = UserPermissionRepository(db)
        if feature not in repo.get_by_user(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"'{feature}' 기능 접근 권한이 없습니다. 관리자에게 문의하세요.",
            )
        return current_user
    return _check


def get_board_service(db: Session = Depends(get_db)) -> BoardService:
    return BoardService(BoardRepository(db))


def get_dataset_service(db: Session = Depends(get_db)) -> DatasetService:
    return DatasetService(DatasetRepository(db))


def get_query_service(db: Session = Depends(get_db)) -> QueryService:
    return QueryService(db, QueryHistoryRepository(db))
