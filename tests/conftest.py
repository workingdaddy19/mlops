"""테스트 부트스트랩 — app import 전에 필수 설정 환경변수를 주입한다.

실제 DB 연결은 발생하지 않는다 (SQLAlchemy engine 객체만 생성됨).
"""
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("JUPYTERHUB_JWT_SECRET", "test-jwt-secret")
