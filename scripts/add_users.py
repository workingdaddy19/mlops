#!/usr/bin/env python3
"""
Portal 사용자 동적 추가 스크립트 — 배포 없이 DB에 사용자 추가

사용법:
  python scripts/add_users.py <username> <password>
  python scripts/add_users.py <username>              # 비번 = 아이디와 동일

예시:
  python scripts/add_users.py 09930269 09930269
  python scripts/add_users.py 09929689
  python scripts/add_users.py alice mysecret user     # role 지정 (기본: user)
  python scripts/add_users.py bob admin admin         # admin 권한

kubectl exec 실행 예:
  kubectl exec -n mlops -it $(kubectl get pod -n mlops -l app=mlops \
    -o jsonpath='{.items[0].metadata.name}') \
    -- python scripts/add_users.py 09930269 09930269
"""
import sys
import os

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import get_engine
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repo import UserRepository


def add_user(username: str, password: str, name: str = "", role: str = "user") -> None:
    settings = get_settings()
    secret_key = settings.secret_key.get_secret_value()
    engine = get_engine()
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        repo = UserRepository(session)

        existing = repo.get_by_username(username)
        if existing:
            print(f"⚠️  사용자 '{username}' 이미 존재합니다. (role={existing.role})")
            return

        pw_hash = hash_password(password, username, secret_key)
        display_name = name or username
        user = User(username=username, password_hash=pw_hash, name=display_name, role=role)
        repo.create(user)
        print(f"✅ 사용자 추가 완료: username={username}, name={display_name}, role={role}")
    finally:
        session.close()


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    username = args[0]
    password = args[1] if len(args) > 1 else username   # 비번 생략 시 아이디와 동일
    name     = args[2] if len(args) > 2 else username
    role     = args[3] if len(args) > 3 else "user"

    if role not in ("user", "admin"):
        print(f"❌ role은 'user' 또는 'admin'만 허용됩니다. (입력값: {role})")
        sys.exit(1)

    add_user(username, password, name, role)


if __name__ == "__main__":
    main()
