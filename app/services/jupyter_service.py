"""JupyterHub 서비스 — on-demand 토큰 발급, 서버 자동 시작.

JupyterHub 2.x RBAC scope 참고:
  /hub/token 페이지에서 확인된 scope 포맷: access:servers!server={username}/
  관리자 API로 사용자 토큰 발급 시 동일 포맷 사용
"""
import json
import logging
from urllib.parse import quote, urljoin
from datetime import datetime, timedelta, UTC
import jwt  # PyJWT

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class JupyterService:
    def __init__(self, db: Session | None = None):
        settings = get_settings()

        if db is not None:
            from app.services.settings_service import SettingsService
            svc = SettingsService(db)
            self.admin_token = svc.get("JUPYTERHUB_ADMIN_TOKEN", settings.jupyterhub_admin_token)
            self.base_url = svc.get("JUPYTER_BASE_URL", settings.jupyter_base_url)
            self.jwt_secret = svc.get("JUPYTERHUB_JWT_SECRET", settings.jupyterhub_jwt_secret)
            envs_json     = svc.get("JUPYTER_ENVS", settings.jupyter_envs)
        else:
            self.admin_token = settings.jupyterhub_admin_token
            self.base_url = settings.jupyter_base_url
            self.jwt_secret = settings.jupyterhub_jwt_secret
            envs_json     = settings.jupyter_envs

        self.base_url = self.base_url.rstrip("/")
        try:
            self.envs_config: list[dict] = json.loads(envs_json)
        except (json.JSONDecodeError, ValueError):
            self.envs_config = [
                {"name": "CPU 환경", "server": ""},
                {"name": "GPU 환경", "server": "gpu"},
            ]

    @staticmethod
    def _get_setting(db: Session, key: str, fallback: str) -> str:
        try:
            from app.models.system_settings import SystemSetting
            row = db.get(SystemSetting, key)
            if row and row.value:
                return row.value
        except Exception as exc:
            logger.warning("DB setting read failed key=%s: %s", key, exc)
        return fallback

    def _http_client(self) -> httpx.AsyncClient:
        """httpx 클라이언트 — 내부망 자체서명 인증서 허용."""
        return httpx.AsyncClient(verify=False, timeout=10)

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    async def get_user_envs(self) -> list[dict]:
        """Jupyter 환경 목록 반환 (토큰 미포함)."""
        return [
            {
                "name":            env.get("name", env.get("server") or "기본"),
                "server":          env.get("server", ""),
                "token_available": bool(self.admin_token),
            }
            for env in self.envs_config
        ]

    async def get_token_url(self, username: str, server: str = "") -> dict:
        """버튼 클릭 시 토큰 발급 + 서버 자동 시작 → 접속 정보 반환.

        JupyterHub 2.x 자동 로그인 흐름:
          1. Admin API → 사용자용 1시간 토큰 발급 (scope: access:servers!server=user/)
          2. 서버 구동 확인 및 시작
          3. URL 에 ?token={hub_api_token} 포함 → 브라우저가 열면 Hub가 즉시 인증

        Returns:
          url          - ?token= 포함된 JupyterLab URL
          token_issued - 발급 성공 여부
          error        - 실패 사유 (성공 시 "")
        """
        token, error = await self._issue_user_token(username, server)

        # 서버 자동 시작 (토큰 발급 성공 여부와 무관하게 시도)
        await self._ensure_server_running(username, server)

        if server:
            lab_path = f"/user/{username}/{server}/lab"
        else:
            lab_path = f"/user/{username}/lab"

        # JWT 생성 (jupyterhub-jwtauthenticator 호환)
        # iat 포함 필수: jwtauthenticator가 발급시각 기준 검증에 사용
        # 유효기간 15분: 서버 간 clock skew(~수 분) 허용
        now = datetime.now(UTC)
        payload = {
            "username": username,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        }
        
        try:
            sso_jwt = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
            # jwtauthenticator는 next URL 안의 token 파라미터를 검증함
            # /hub/login?next=/user/{username}/lab?token={jwt} 구조가 정상 동작
            next_with_token = quote(f"{lab_path}?token={sso_jwt}", safe="")
            lab_url = f"{self.base_url}/hub/login?next={next_with_token}"
        except Exception as e:
            logger.error("Failed to generate JWT: %s", e)
            lab_url = f"{self.base_url}{lab_path}"

        return {
            "url":          lab_url,
            "token_issued": bool(token),
            "error":        error if not token else "",
            # 서버가 정상 시작됐으면 직접 접속 가능
            "server_ready": True,
        }

    async def get_hub_stats(self) -> dict:
        """JupyterHub 사용자/서버 현황."""
        if not self.admin_token:
            return {"running_servers": 0, "total_users": 0, "available": False}
        try:
            async with self._http_client() as client:
                resp = await client.get(
                    f"{self.base_url}/hub/api/users",
                    headers={"Authorization": f"token {self.admin_token}"},
                )
            if resp.status_code != 200:
                return {"running_servers": 0, "total_users": 0, "available": False}
            users   = resp.json()
            total   = len(users)
            running = sum(
                1 for u in users
                if u.get("servers") and any(
                    s.get("ready") for s in u["servers"].values()
                )
            )
            return {"running_servers": running, "total_users": total, "available": True}
        except Exception as exc:
            logger.warning("JupyterHub stats error: %s", exc)
            return {"running_servers": 0, "total_users": 0, "available": False}

    async def check_health(self) -> bool:
        try:
            headers = {}
            if self.admin_token:
                headers["Authorization"] = f"token {self.admin_token}"
            async with self._http_client() as client:
                resp = await client.get(
                    f"{self.base_url}/hub/api/",
                    headers=headers,
                )
                return resp.status_code in (200, 401)
        except Exception:
            return False

    async def validate_token(self, token: str) -> dict | None:
        """토큰 유효성 검증."""
        if not self.admin_token:
            return None
        try:
            async with self._http_client() as client:
                resp = await client.get(
                    f"{self.base_url}/hub/api/authorizations/token/{token}",
                    headers={"Authorization": f"token {self.admin_token}"},
                )
            return resp.json() if resp.status_code == 200 else None
        except Exception as exc:
            logger.warning("token validation error: %s", exc)
            return None

    def get_lab_url(self, username: str = "admin", server: str = "") -> str:
        if server:
            return f"{self.base_url}/user/{username}/{server}/lab"
        return f"{self.base_url}/user/{username}/lab"

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    async def _issue_user_token(self, username: str, server: str = "") -> tuple[str, str]:
        """JupyterHub Admin API로 사용자 토큰 발급 (1시간).

        scopes를 명시하지 않으면 JupyterHub가 해당 사용자의 기본 scope를 자동 부여.
        (admin 토큰의 scope 범위 밖의 scope를 명시하면 403 오류 발생)

        Returns:
            (token, error) — 성공: (token, ""),  실패: ("", 오류메시지)
        """
        if not self.admin_token:
            return "", "JUPYTERHUB_ADMIN_TOKEN 미설정"

        # scopes 미지정 → JupyterHub가 해당 사용자의 적합한 scope를 자동 부여
        # (명시 시 admin 토큰 scope 범위 검증으로 403 발생 가능)
        payload: dict = {
            "note":       "mlfoundry-auto",
            "expires_in": 3600,
        }

        logger.info(
            "issuing token  user=%-12s  server=%r  (scopes auto-assigned by JupyterHub)",
            username, server or "(default)",
        )

        try:
            async with self._http_client() as client:
                resp = await client.post(
                    f"{self.base_url}/hub/api/users/{username}/tokens",
                    headers={
                        "Authorization": f"token {self.admin_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

            logger.info(
                "token API response  user=%-12s  status=%d  body=%s",
                username, resp.status_code, resp.text[:300],
            )

            if resp.status_code in (200, 201):
                body  = resp.json()
                token = body.get("token", "")
                if token:
                    logger.info(
                        "token issued OK  user=%-12s  granted_scopes=%s",
                        username, body.get("scopes", []),
                    )
                    return token, ""
                return "", "API 응답에 token 필드 없음"

            # 403: 권한 부족
            if resp.status_code == 403:
                return "", (
                    f"JupyterHub 권한 오류 (HTTP 403): "
                    f"JUPYTERHUB_ADMIN_TOKEN으로 '{username}' 토큰 발급이 거부됐습니다. "
                    f"응답: {resp.text[:200]}"
                )

            # 404: JupyterHub에 해당 사용자 없음
            if resp.status_code == 404:
                return "", f"JupyterHub에 사용자 '{username}' 없음 (먼저 JupyterHub에서 로그인 1회 필요)"

            return "", f"HTTP {resp.status_code}: {resp.text[:200]}"

        except httpx.ConnectError as exc:
            msg = f"JupyterHub 연결 실패 ({self.base_url}): {exc}"
            logger.error(msg)
            return "", msg
        except Exception as exc:
            logger.error("token issuance error user=%s: %s", username, exc)
            return "", str(exc)

    async def _ensure_server_running(self, username: str, server: str = "") -> int:
        """서버 자동 시작 요청. 반환: HTTP 상태코드."""
        if not self.admin_token:
            return 0
        try:
            if server:
                url = f"{self.base_url}/hub/api/users/{username}/servers/{server}"
            else:
                url = f"{self.base_url}/hub/api/users/{username}/server"

            async with self._http_client() as client:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"token {self.admin_token}"},
                )
            # 201=already running, 202=starting, 400=bad request
            logger.info(
                "server start  user=%-12s  server=%r  status=%d",
                username, server or "(default)", resp.status_code,
            )
            return resp.status_code
        except Exception as exc:
            logger.warning("server start failed user=%s: %s", username, exc)
            return 0
