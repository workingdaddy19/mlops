"""추론 프록시 서비스.

포탈은 추론을 **자체 처리하지 않는다**. 모델 로드/전처리/예측은 별도 Pod에 배포된
invest-app 프로젝트 서비스(=invest-inference Deployment)가 전담하며, 본 서비스는
사용자가 입력한 추론 API URL로 JSON 페이로드를 그대로 POST 중계(proxy)한다.

(이전 버전은 mlflow.xgboost 로 모델을 직접 로드하고 전처리를 재구현했으나,
 invest-app Pod 로직과 중복되어 전면 제거하고 HTTP 호출 방식으로 전환함.)
"""
import logging
import time
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# SSRF 차단 대상 (클라우드 메타데이터 엔드포인트)
_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}


class InferenceProxyService:
    """임의의 추론 엔드포인트로 JSON POST를 중계하는 얇은 클라이언트."""

    @staticmethod
    def _assert_safe_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("http/https URL만 허용됩니다.")
        host = parsed.hostname
        if not host:
            raise ValueError("유효한 호스트가 없습니다.")
        if host in _BLOCKED_HOSTS:
            raise ValueError("허용되지 않은 호스트입니다.")
        allowed = get_settings().inference_allowed_hosts  # 빈 값 = 전체 허용
        if allowed and not any(host == h or host.endswith("." + h) for h in allowed):
            raise ValueError(f"허용되지 않은 호스트입니다: {host}")

    async def proxy(
        self,
        target_url: str,
        payload: dict,
        host_header: str | None = None,
        timeout: int = 30,
    ) -> dict:
        self._assert_safe_url(target_url)

        headers = {"Content-Type": "application/json"}
        if host_header:
            headers["Host"] = host_header

        logger.info("Inference proxy → %s (Host=%s)", target_url, host_header or "-")
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(target_url, json=payload, headers=headers)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        try:
            body = resp.json()
        except ValueError:
            body = resp.text

        return {
            "status_code": resp.status_code,
            "elapsed_ms": elapsed_ms,
            "ok": resp.is_success,
            "body": body,
        }
