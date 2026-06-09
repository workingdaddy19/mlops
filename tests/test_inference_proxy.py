"""추론 프록시 단위 테스트 (Mock 기반, 외부 서버 불필요).

실행:
    pip install -r requirements.txt pytest
    pytest tests/test_inference_proxy.py -v
"""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.services.inference_service import InferenceProxyService


# ── 서비스 레벨에서 httpx.AsyncClient 를 대체하는 가짜 클라이언트 ──────────────
class _FakeAsyncClient:
    """httpx.AsyncClient 대체. 마지막 호출 인자를 클래스 변수에 기록."""
    last_call: dict = {}

    def __init__(self, *, response=None, exc=None):
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        type(self).last_call = {"url": url, "json": json, "headers": headers or {}}
        if self._exc is not None:
            raise self._exc
        return self._response


def _patch_client(monkeypatch, *, response=None, exc=None):
    def factory(*args, **kwargs):
        return _FakeAsyncClient(response=response, exc=exc)
    monkeypatch.setattr("app.services.inference_service.httpx.AsyncClient", factory)


def _run(coro):
    return asyncio.run(coro)


ALB = "http://k8s-sharedalb-0882a5287f-595901001.ap-northeast-2.elb.amazonaws.com/predict"
SAMPLE = {"gpt_ivt_jg_seq": "JG_TEST_001", "ltv_rte": 65.0}


# ============================================================
# 서비스: proxy()
# ============================================================
class TestProxyService:
    def test_normal_proxy(self, monkeypatch):
        resp = httpx.Response(200, json={"invest_yn": "N", "invest_prob": 0.1882})
        _patch_client(monkeypatch, response=resp)
        out = _run(InferenceProxyService().proxy(ALB, SAMPLE))
        assert out["status_code"] == 200
        assert out["ok"] is True
        assert out["body"]["invest_yn"] == "N"
        assert isinstance(out["elapsed_ms"], int)

    def test_passthrough_422(self, monkeypatch):
        resp = httpx.Response(422, json={"detail": "validation error"})
        _patch_client(monkeypatch, response=resp)
        out = _run(InferenceProxyService().proxy(ALB, SAMPLE))
        assert out["status_code"] == 422
        assert out["ok"] is False

    def test_passthrough_500(self, monkeypatch):
        resp = httpx.Response(500, json={"detail": "server error"})
        _patch_client(monkeypatch, response=resp)
        out = _run(InferenceProxyService().proxy(ALB, SAMPLE))
        assert out["status_code"] == 500
        assert out["ok"] is False

    def test_non_json_body_returns_text(self, monkeypatch):
        resp = httpx.Response(200, text="plain text not json")
        _patch_client(monkeypatch, response=resp)
        out = _run(InferenceProxyService().proxy(ALB, SAMPLE))
        assert out["body"] == "plain text not json"

    def test_host_header_forwarded(self, monkeypatch):
        resp = httpx.Response(200, json={"ok": True})
        _patch_client(monkeypatch, response=resp)
        _run(InferenceProxyService().proxy(ALB, SAMPLE, host_header="api.mlops.click"))
        assert _FakeAsyncClient.last_call["headers"].get("Host") == "api.mlops.click"

    def test_connect_error_raises(self, monkeypatch):
        _patch_client(monkeypatch, exc=httpx.ConnectError("refused"))
        with pytest.raises(httpx.ConnectError):
            _run(InferenceProxyService().proxy(ALB, SAMPLE))

    def test_timeout_raises(self, monkeypatch):
        _patch_client(monkeypatch, exc=httpx.TimeoutException("timeout"))
        with pytest.raises(httpx.TimeoutException):
            _run(InferenceProxyService().proxy(ALB, SAMPLE))


# ============================================================
# 서비스: _assert_safe_url() (SSRF 방어)
# ============================================================
class TestSafeUrl:
    def test_non_http_scheme_rejected(self):
        with pytest.raises(ValueError):
            InferenceProxyService._assert_safe_url("file:///etc/passwd")

    def test_imds_host_rejected(self):
        with pytest.raises(ValueError):
            InferenceProxyService._assert_safe_url("http://169.254.169.254/latest/meta-data")

    def test_valid_url_passes(self):
        InferenceProxyService._assert_safe_url(ALB)  # 예외 없어야 함

    def test_allowed_hosts_restriction(self, monkeypatch):
        from app.core import config
        config.get_settings.cache_clear()
        monkeypatch.setenv("INFERENCE_ALLOWED_HOSTS", '["api.mlops.click"]')
        try:
            with pytest.raises(ValueError):
                InferenceProxyService._assert_safe_url("http://evil.example.com/predict")
        finally:
            config.get_settings.cache_clear()


# ============================================================
# 라우트: POST /api/inference/proxy
# ============================================================
@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: object()
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def _patch_route_proxy(monkeypatch, *, result=None, exc=None):
    async def fake_proxy(self, target_url, payload, host_header=None, timeout=30):
        if exc is not None:
            raise exc
        return result
    monkeypatch.setattr(InferenceProxyService, "proxy", fake_proxy)


class TestProxyRoute:
    def test_200(self, client, monkeypatch):
        _patch_route_proxy(monkeypatch, result={
            "status_code": 200, "elapsed_ms": 12, "ok": True, "body": {"invest_yn": "N"}})
        r = client.post("/api/inference/proxy", json={"target_url": ALB, "payload": SAMPLE})
        assert r.status_code == 200
        assert r.json()["body"]["invest_yn"] == "N"

    def test_400_on_value_error(self, client, monkeypatch):
        _patch_route_proxy(monkeypatch, exc=ValueError("http/https URL만 허용됩니다."))
        r = client.post("/api/inference/proxy", json={"target_url": "file://x", "payload": {}})
        assert r.status_code == 400

    def test_502_on_connect_error(self, client, monkeypatch):
        _patch_route_proxy(monkeypatch, exc=httpx.ConnectError("refused"))
        r = client.post("/api/inference/proxy", json={"target_url": ALB, "payload": {}})
        assert r.status_code == 502

    def test_504_on_timeout(self, client, monkeypatch):
        _patch_route_proxy(monkeypatch, exc=httpx.TimeoutException("timeout"))
        r = client.post("/api/inference/proxy", json={"target_url": ALB, "payload": {}})
        assert r.status_code == 504

    def test_422_on_missing_target_url(self, client):
        r = client.post("/api/inference/proxy", json={"payload": {}})
        assert r.status_code == 422
