"""추론 프록시 요청/응답 스키마.

포탈은 추론을 자체 처리하지 않는다. 사용자가 입력한 추론 API URL로
JSON 페이로드를 그대로 POST 중계(proxy)하고 응답을 반환한다.
"""
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProxyRequest(BaseModel):
    target_url: str = Field(..., description="추론 API 엔드포인트 URL")
    payload: dict[str, Any] = Field(default_factory=dict, description="추론 요청 JSON")
    host_header: str | None = Field(
        default=None,
        description="ALB Host 기반 라우팅용 Host 헤더 (예: api.mlops.click). DNS 미등록 시 필수",
    )
    timeout: int = Field(default=30, ge=1, le=120, description="초 단위 타임아웃")

    @field_validator("target_url")
    @classmethod
    def _strip_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target_url is required")
        return v

    @field_validator("host_header")
    @classmethod
    def _strip_host(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ProxyResponse(BaseModel):
    status_code: int = Field(..., description="대상 서버 응답 코드")
    elapsed_ms: int = Field(..., description="호출 소요 시간(ms)")
    ok: bool = Field(..., description="대상 응답이 2xx 인지 여부")
    body: Any = Field(..., description="대상 응답 본문 (JSON dict/list 또는 원문 text)")
