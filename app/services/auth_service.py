from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import LoginResponse, UserRead


class AuthService:
    def __init__(self, user_repo: UserRepository, secret_key: str, ttl_minutes: int):
        self.user_repo = user_repo
        self.secret_key = secret_key
        self.ttl_minutes = ttl_minutes

    def login(self, username: str, password: str) -> LoginResponse:
        user = self.user_repo.get_by_username(username)
        if user is None:
            raise ValueError("아이디 또는 비밀번호가 올바르지 않습니다.")
        if not verify_password(password, username, self.secret_key, user.password_hash):
            raise ValueError("아이디 또는 비밀번호가 올바르지 않습니다.")
        token = create_access_token(
            username=user.username,
            role=user.role,
            secret_key=self.secret_key,
            expires_in_minutes=self.ttl_minutes,
        )
        return LoginResponse(access_token=token, username=user.username, role=user.role)

    def get_current_user(self, token: str) -> UserRead:
        payload = decode_access_token(token, self.secret_key)
        username = payload.get("sub")
        if not username:
            raise ValueError("유효하지 않은 토큰입니다.")
        user = self.user_repo.get_by_username(username)
        if user is None:
            raise ValueError("사용자를 찾을 수 없습니다.")
        return UserRead.model_validate(user)


def ensure_default_users(engine: Engine) -> None:
    settings = get_settings()
    secret_key = settings.secret_key.get_secret_value()
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        repo = UserRepository(session)
        for username, name, role in [("admin", "관리자", "admin"), ("user", "사용자", "user")]:
            if repo.get_by_username(username) is None:
                pw_hash = hash_password(username, username, secret_key)
                user = User(username=username, password_hash=pw_hash, name=name, role=role)
                repo.create(user)
    finally:
        session.close()
