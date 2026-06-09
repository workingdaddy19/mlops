import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.schemas.auth import UserRead
from app.schemas.inference import ProxyRequest, ProxyResponse
from app.services.inference_service import InferenceProxyService

router = APIRouter(prefix="/inference", tags=["inference"])


@router.post("/proxy", response_model=ProxyResponse)
async def proxy(req: ProxyRequest, _: UserRead = Depends(get_current_user)):
    """입력한 추론 API URL로 JSON 페이로드를 POST 중계한다.

    대상 서버가 4xx/5xx를 반환해도 프록시 자체는 200으로 감싸 status_code/body를
    그대로 전달한다 (테스터 도구가 원본 응답을 확인할 수 있도록). 프록시 자체 실패
    (검증/연결/타임아웃)만 4xx/5xx로 구분한다.
    """
    svc = InferenceProxyService()
    try:
        return await svc.proxy(req.target_url, req.payload, req.host_header, req.timeout)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"추론 서버 연결 오류: {e}") from e
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504, detail="추론 서버 응답 시간 초과") from e
