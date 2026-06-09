import logging
import re

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AirflowService:
    def __init__(self, db: Session | None = None):
        settings = get_settings()
        if db is not None:
            from app.services.settings_service import SettingsService
            svc = SettingsService(db)
            self.base_url = svc.get("AIRFLOW_BASE_URL", settings.airflow_base_url)
            self.username = svc.get("AIRFLOW_USERNAME", "admin")
            self.password = svc.get("AIRFLOW_PASSWORD", "admin")
        else:
            self.base_url = settings.airflow_base_url
            self.username = "admin"
            self.password = "admin"

    def get_ui_url(self) -> str:
        return self.base_url

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def get_session_cookie(self) -> str | None:
        """Airflow FAB 로그인 — CSRF 토큰 파싱 후 POST, 세션 쿠키 반환."""
        login_url = f"{self.base_url}/login"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                # Step 1: GET /login → CSRF 토큰 추출
                get_resp = await client.get(login_url)
                csrf_token = self._extract_csrf(get_resp.text)

                # Step 2: POST 로그인
                post_resp = await client.post(
                    login_url,
                    data={
                        "username": self.username,
                        "password": self.password,
                        "_token": csrf_token or "",
                    },
                    headers={"Referer": login_url},
                )
                if post_resp.status_code in (200, 302):
                    return post_resp.cookies.get("session")
        except Exception as e:
            logger.warning("Airflow SSO login failed: %s", e)
        return None

    @staticmethod
    def _extract_csrf(html: str) -> str | None:
        match = re.search(r'name=["\']_token["\'][^>]*value=["\']([^"\']+)["\']', html)
        if not match:
            match = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']_token["\']', html)
        return match.group(1) if match else None
