"""시스템 설정 서비스 — DB 우선, env 폴백, 60초 TTL 캐시."""
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.system_settings import SystemSetting
from app.repositories.settings_repo import SettingsRepository

logger = logging.getLogger(__name__)

# 인메모리 캐시: {key: (value, expire_at)}
_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 60  # seconds


def _cache_get(key: str) -> str | None:
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _cache_set(key: str, value: str) -> None:
    _cache[key] = (value, time.monotonic() + _CACHE_TTL)


def _cache_invalidate(key: str | None = None) -> None:
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()


class SettingsService:
    def __init__(self, db: Session):
        self.repo = SettingsRepository(db)
        self._env = get_settings()

    # ──────────────────────────────────────────
    # Public: single value (cache + DB + env fallback)
    # ──────────────────────────────────────────

    def get(self, key: str, default: str = "") -> str:
        """캐시 → DB → env → default 순으로 반환."""
        cached = _cache_get(key)
        if cached is not None:
            return cached
        try:
            db_val = self.repo.get_value(key)
            if db_val is not None:
                _cache_set(key, db_val)
                return db_val
        except Exception as exc:
            logger.warning("settings DB read failed for key=%s: %s", key, exc)

        # env 폴백
        env_val = self._env_fallback(key, default)
        return env_val

    def _env_fallback(self, key: str, default: str) -> str:
        mapping: dict[str, Any] = {
            "MLFLOW_BASE_URL":   self._env.mlflow_base_url,
            "JUPYTER_BASE_URL":  self._env.jupyter_base_url,
            "JUPYTER_ENVS":      self._env.jupyter_envs,
            "ATHENA_DATABASE":   self._env.athena_database,
            "ATHENA_S3_OUTPUT":  self._env.athena_s3_output,
            "S3_BUCKET_NAME":    self._env.s3_bucket_name,
            "JUPYTERHUB_ADMIN_TOKEN": self._env.jupyterhub_admin_token,
            "ATHENA_REGION":     self._env.athena_region,
            "S3_REGION":         self._env.s3_region,
        }
        return str(mapping.get(key, default))

    # ──────────────────────────────────────────
    # Public: list / update
    # ──────────────────────────────────────────

    def list_all(self) -> list[SystemSetting]:
        return self.repo.list_all()

    def update(self, key: str, value: str) -> SystemSetting:
        row = self.repo.set_value(key, value)
        _cache_invalidate(key)
        return row
