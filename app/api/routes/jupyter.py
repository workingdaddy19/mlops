"""JupyterHub API 라우트 — 토큰 발급 기반 자동 로그인."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.schemas.auth import UserRead
from app.services.jupyter_service import JupyterService

router = APIRouter(prefix="/jupyter", tags=["jupyter"])
logger = logging.getLogger(__name__)


class TokenRequest(BaseModel):
    server: str = ""


@router.get("/envs")
async def get_jupyter_envs(
    current_user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Jupyter 환경 목록 반환 (토큰 미포함)."""
    svc = JupyterService(db=db)
    try:
        envs = await svc.get_user_envs()
        return {"username": current_user.username, "envs": envs}
    except Exception as e:
        logger.error("JupyterHub envs error: %s", e)
        raise HTTPException(status_code=502, detail=f"JupyterHub 연결 오류: {e}") from e


@router.get("/token")
async def get_jupyter_token(
    server: str = Query(default="", description="Named server 이름 (비워두면 기본 서버)"),
    current_user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """버튼 클릭 → 토큰 발급 → 접속 URL 반환.

    응답:
      url          : 새 탭으로 열어야 할 JupyterLab URL (토큰 포함)
      token_issued : 토큰 발급 성공 여부 (false면 로그인 페이지로 이동될 수 있음)
      error        : 실패 사유 (성공 시 null)
      username     : 접속 대상 JupyterHub 사용자명
    """
    svc = JupyterService(db=db)
    try:
        result = await svc.get_token_url(current_user.username, server)
        logger.info(
            "token request  user=%-12s  server=%r  token_issued=%s  url=%s",
            current_user.username, server or "(default)",
            result["token_issued"], result["url"],
        )
        # JupyterHub 5.x: token_issued는 서버 자동시작 확인용.
        # 브라우저 접속은 항상 직접 lab URL로 이동 (세션 쿠키로 인증).
        return {
            "url":          result["url"],
            "token_issued": result["token_issued"],
            "error":        result.get("error") or None,
            "username":     current_user.username,
            "server":       server,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("JupyterHub token error for %s: %s", current_user.username, e)
        raise HTTPException(status_code=502, detail=f"JupyterHub 토큰 발급 오류: {e}") from e


@router.post("/token")
async def post_jupyter_token(
    body: TokenRequest,
    current_user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST 방식 토큰 발급 — server는 request body에 담아 전송."""
    svc = JupyterService(db=db)
    try:
        result = await svc.get_token_url(current_user.username, body.server)
        logger.info(
            "token request  user=%-12s  server=%r  token_issued=%s",
            current_user.username, body.server or "(default)", result["token_issued"],
        )
        return {
            "url":          result["url"],
            "token_issued": result["token_issued"],
            "error":        result.get("error") or None,
            "username":     current_user.username,
            "server":       body.server,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("JupyterHub token error for %s: %s", current_user.username, e)
        raise HTTPException(status_code=502, detail=f"JupyterHub 토큰 발급 오류: {e}") from e


@router.get("/health")
async def jupyter_health(db: Session = Depends(get_db)):
    """JupyterHub 헬스체크"""
    svc = JupyterService(db=db)
    healthy = await svc.check_health()
    url = svc.get_lab_url()
    return {"status": "ok" if healthy else "unavailable", "url": url}


@router.get("/stats")
async def jupyter_stats(
    _: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """JupyterHub 서버 현황."""
    svc = JupyterService(db=db)
    return await svc.get_hub_stats()


@router.get("/debug-token")
async def debug_jupyter_token(
    current_user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """토큰 발급 진단 — 브라우저 개발자 도구에서 확인용.

    토큰 발급 → 검증 → curl 명령어 제공
    실제 운영에서는 제거하거나 admin only로 변경 권장.
    """
    svc = JupyterService(db=db)
    username = current_user.username

    # 토큰 발급
    result = await svc.get_token_url(username, "")

    # 토큰 검증 (발급 성공 시)
    token_info = None
    if result["token_issued"]:
        token_value = result["url"].split("?token=")[-1] if "?token=" in result["url"] else ""
        if token_value:
            token_info = await svc.validate_token(token_value)

    return {
        "username":        username,
        "admin_token_set": bool(svc.admin_token),
        "base_url":        svc.base_url,
        "token_issued":    result["token_issued"],
        "error":           result["error"],
        "target_url":      result["url"],
        "token_valid":     token_info is not None,
        "token_user":      token_info.get("name") if token_info else None,
        "curl_test": (
            f"curl -s -H 'Authorization: token {svc.admin_token}' "
            f"'{svc.base_url}/hub/api/users/{username}/tokens' -X POST "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"note\":\"test\",\"expires_in\":3600}}'"
        ) if svc.admin_token else "JUPYTERHUB_ADMIN_TOKEN 미설정",
    }

