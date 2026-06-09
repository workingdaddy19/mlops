import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta


def hash_password(password: str, username: str, secret_key: str) -> str:
    salt = f"{username}:{secret_key}".encode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return digest.hex()


def verify_password(password: str, username: str, secret_key: str, expected_hash: str) -> bool:
    candidate = hash_password(password, username, secret_key)
    return hmac.compare_digest(candidate, expected_hash)


def create_access_token(*, username: str, role: str, secret_key: str, expires_in_minutes: int) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
    payload = {"sub": username, "role": role, "exp": int(expires_at.timestamp())}
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _urlsafe_b64encode(payload_json)
    signature = hmac.new(secret_key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    signature_b64 = _urlsafe_b64encode(signature)
    return f"{payload_b64}.{signature_b64}"


def decode_access_token(token: str, secret_key: str) -> dict[str, str | int]:
    parts = token.split(".", maxsplit=1)
    if len(parts) != 2:
        raise ValueError("유효하지 않은 토큰 형식입니다.")

    payload_b64, signature_b64 = parts
    expected_signature = hmac.new(secret_key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    expected_signature_b64 = _urlsafe_b64encode(expected_signature)
    if not hmac.compare_digest(signature_b64, expected_signature_b64):
        raise ValueError("토큰 서명이 올바르지 않습니다.")

    payload_json = _urlsafe_b64decode(payload_b64)
    payload = json.loads(payload_json.decode("utf-8"))

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or datetime.now(UTC).timestamp() > expires_at:
        raise ValueError("토큰이 만료되었습니다.")
    return payload


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))
