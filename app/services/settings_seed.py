"""시스템 설정 초기 seed 데이터 삽입."""
import logging

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.models.system_settings import SETTINGS_SEED, SystemSetting

logger = logging.getLogger(__name__)


def ensure_default_settings(engine: Engine) -> None:
    """system_settings 테이블에 seed 데이터가 없으면 삽입."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        for item in SETTINGS_SEED:
            existing = session.get(SystemSetting, item["key"])
            if existing is None:
                session.add(SystemSetting(**item))
                logger.info("settings seed: inserted key=%s", item["key"])
        session.commit()
    except Exception as exc:
        logger.error("settings seed error: %s", exc)
        session.rollback()
    finally:
        session.close()
