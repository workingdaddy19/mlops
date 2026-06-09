# 사용자별 서비스 토큰 관리 설계 문서

> Plan 문서 참조: [service-token-management.plan.md](../../01-plan/features/service-token-management.plan.md)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | Jupyter Hub / MLflow 서비스 토큰 관리 및 SSO 연동 |
| **설계일** | 2026-05-26 |
| **기술 스택** | FastAPI + SQLAlchemy + PostgreSQL + JavaScript Fetch |
| **참조 시스템** | 기존 사용자 인증 (JWT) + 신규 서비스 토큰 저장소 |

### Value Delivered

| 관점 | 내용 |
|------|------|
| **Problem** | 사용자가 Jupyter/MLflow에 별도로 로그인하고 토큰을 분산관리 → 보안 위험, UX 불편 |
| **Solution** | 포탈 로그인 후 토큰을 중앙 DB에 저장 → 클릭 하나로 각 서비스 자동 인증 |
| **Function UX Effect** | "Jupyter 이동" 버튼 클릭 → 토큰 자동 전달 → Jupyter 자동 로그인 (SSO 경험) |
| **Core Value** | 통합 사용자 관리, 편리한 서비스 접근, 토큰 보안 중앙화, 감사 추적 가능 |

---

## 1. 전체 아키텍처

### 1.1 시스템 흐름도

```
사용자 (포탈)
  │
  ├─→ 로그인 (admin/admin) ✅
  │   └─→ JWT 토큰 발급 (session)
  │
  ├─→ "Jupyter 이동" 버튼 클릭
  │   │
  │   └─→ GET /api/auth/service-token/jupyter/redirect
  │       ├─→ current_user 검증 (JWT Bearer)
  │       ├─→ DB에서 user_id + 'jupyter' 토큰 조회
  │       │   ├─ 있으면: 기존 토큰 사용
  │       │   └─ 없으면: 신규 토큰 생성 + 저장
  │       └─→ 302 Redirect: http://jupyterhub.mlops.click?token={TOKEN}
  │           └─→ Jupyter Hub 자동 로그인 ✅
  │
  └─→ "MLflow 이동" 버튼 클릭
      │
      └─→ GET /api/auth/service-token/mlflow/redirect
          └─→ http://mlflow.mlops.click?token={TOKEN}
              └─→ MLflow 자동 로그인 ✅
```

### 1.2 컴포넌트 상호작용

```
┌─────────────────┐
│   포탈 UI       │  (Jinja2 + JS)
│  - 대시보드     │
│  - 네비게이션  │
└────────┬────────┘
         │ fetch()
         ↓
┌─────────────────────────────────────┐
│   FastAPI Backend                   │
│  ┌────────────────────────────────┐ │
│  │ POST /api/auth/login           │ │
│  │   → access_token               │ │
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │ GET /api/auth/service-token/{service} │
│  │   → 토큰 발급/조회              │
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │ GET /api/auth/service-token/{service}/redirect │
│  │   → Jupyter/MLflow로 리다이렉트 │
│  └────────────────────────────────┘ │
└─────────────────┬───────────────────┘
                  │ (SQLAlchemy ORM)
                  ↓
         ┌─────────────────┐
         │ PostgreSQL RDS  │
         │                 │
         │ users 테이블    │
         │ user_service_   │
         │   tokens 테이블 │
         └─────────────────┘
                  │
                  ├─→ Jupyter Hub (HTTP)
                  └─→ MLflow (HTTP)
```

---

## 2. 데이터베이스 설계

### 2.1 `user_service_tokens` 테이블 스키마

```sql
CREATE TABLE user_service_tokens (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL,
  service VARCHAR(50) NOT NULL,
  token VARCHAR(500) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT uk_user_service UNIQUE(user_id, service)
);

CREATE INDEX idx_user_service ON user_service_tokens(user_id, service);
CREATE INDEX idx_service ON user_service_tokens(service);
```

**필드 설명**:
- `id`: 고유 식별자 (기본키)
- `user_id`: 사용자 ID (users 테이블 참조)
- `service`: 서비스명 (jupyter, mlflow)
- `token`: 서비스별 토큰 (UUID 기반, 최대 500자)
- `created_at`: 토큰 생성 시간
- `updated_at`: 토큰 갱신 시간
- `UNIQUE(user_id, service)`: 사용자당 서비스별 토큰은 1개만 허용

### 2.2 SQLAlchemy 모델

**파일**: `app/models/service_token.py`

```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ServiceToken(Base):
    __tablename__ = "user_service_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_user_service", "user_id", "service"),
    )
```

### 2.3 Pydantic 스키마

**파일**: `app/schemas/service_token.py`

```python
from datetime import datetime

from pydantic import BaseModel


class ServiceTokenCreate(BaseModel):
    service: str  # 'jupyter' | 'mlflow'


class ServiceTokenResponse(BaseModel):
    id: int
    user_id: int
    service: str
    token: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

---

## 3. API 설계

### 3.1 엔드포인트 목록

| 엔드포인트 | 메서드 | 인증 | 목적 | 응답 |
|-----------|--------|------|------|------|
| `/api/auth/service-token/{service}` | POST | JWT | 토큰 발급/조회 | `{service, token, created_at}` |
| `/api/auth/service-token/{service}/redirect` | GET | JWT | 서비스로 자동 리다이렉트 | 302 Redirect |

### 3.2 POST `/api/auth/service-token/{service}` — 토큰 발급/조회

**요청**:
```
POST /api/auth/service-token/jupyter
Authorization: Bearer <ACCESS_TOKEN>
```

**파라미터**:
- `service` (path): 서비스명 (`jupyter`, `mlflow`)

**응답 (200 OK)**:
```json
{
  "service": "jupyter",
  "token": "jupyter_admin_a1b2c3d4e5f6g7h8",
  "created_at": "2026-05-26T10:30:00Z",
  "is_new": false
}
```

**에러 응답**:
- `400 Bad Request`: service가 허용되지 않음 (`jupyter`, `mlflow` 외)
- `401 Unauthorized`: JWT 토큰 없음 또는 유효하지 않음
- `500 Internal Server Error`: DB 오류

**로직**:
1. JWT 토큰에서 current_user 추출
2. service 값 검증 (`jupyter`, `mlflow` only)
3. DB 조회: `user_id + service` 조합
   - 있으면: 기존 토큰 반환 (`is_new: false`)
   - 없으면: 신규 토큰 생성 + 저장 + 반환 (`is_new: true`)
4. 로깅: `✅ Service token issued: user=admin, service=jupyter`

### 3.3 GET `/api/auth/service-token/{service}/redirect` — 서비스 리다이렉트

**요청**:
```
GET /api/auth/service-token/jupyter/redirect
Authorization: Bearer <ACCESS_TOKEN>
```

**응답 (302 Found)**:
```
Location: http://jupyterhub.mlops.click?token=jupyter_admin_a1b2c3d4e5f6g7h8
```

**에러 응답**:
- `400 Bad Request`: 허용되지 않는 service
- `401 Unauthorized`: JWT 토큰 없음
- `500 Internal Server Error`: 토큰 발급 실패

**로직**:
1. POST `/api/auth/service-token/{service}` 호출 (토큰 발급/조회)
2. 응답에서 token 추출
3. 서비스별 기본 URL에 토큰 파라미터 추가
   - Jupyter: `settings.jupyter_base_url?token={token}`
   - MLflow: `settings.mlflow_base_url?token={token}`
4. 302 Redirect 응답

---

## 4. 프론트엔드 설계

### 4.1 대시보드에 서비스 버튼 추가

**파일**: `app/templates/pages/dashboard.html` (신규)

```html
<div class="page-content">
  <h1>대시보드</h1>
  
  <!-- 서비스 빠른 연결 카드 -->
  <div class="service-shortcuts">
    <h2>빠른 연결</h2>
    <div class="service-grid">
      <button class="service-card" onclick="goToService('jupyter')">
        <div class="service-icon">📓</div>
        <div class="service-name">Jupyter Hub</div>
        <div class="service-desc">ML 분석 및 개발</div>
      </button>
      
      <button class="service-card" onclick="goToService('mlflow')">
        <div class="service-icon">📈</div>
        <div class="service-name">MLflow</div>
        <div class="service-desc">실험 추적 및 관리</div>
      </button>
    </div>
  </div>
</div>

<script>
async function goToService(service) {
  try {
    // 리다이렉트 엔드포인트 호출 (자동으로 리다이렉트됨)
    window.location.href = `/api/auth/service-token/${service}/redirect`;
  } catch (err) {
    console.error(err);
    alert(`${service} 접속 실패: ${err.message}`);
  }
}
</script>
```

**CSS** (`app/static/css/main.css`에 추가):
```css
.service-shortcuts {
  margin-bottom: 32px;
}

.service-shortcuts h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.service-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.service-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px;
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
  border: none;
}

.service-card:hover {
  background: #f1f5f9;
  border-color: var(--primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(13, 148, 136, 0.1);
}

.service-icon {
  font-size: 32px;
}

.service-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.service-desc {
  font-size: 12px;
  color: var(--text-secondary);
}
```

### 4.2 네비게이션 메뉴에 서비스 링크 추가

**파일**: `app/templates/base.html` (수정)

기존 `nav-tabs` 다음에 서비스 링크 추가:

```html
<nav class="navbar">
  <!-- 기존 brand, tabs, user -->
  
  <div class="nav-services">
    <a href="#" onclick="goToService('jupyter')" class="nav-service-link" title="새 탭에서 열기">
      📓 Jupyter
    </a>
    <a href="#" onclick="goToService('mlflow')" class="nav-service-link" title="새 탭에서 열기">
      📈 MLflow
    </a>
  </div>
</nav>

<script>
async function goToService(service) {
  window.location.href = `/api/auth/service-token/${service}/redirect`;
}
</script>
```

**CSS**:
```css
.nav-services {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-left: 24px;
  padding-left: 24px;
  border-left: 1px solid var(--border);
}

.nav-service-link {
  text-decoration: none;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.15s;
  cursor: pointer;
  border: none;
  background: none;
}

.nav-service-link:hover {
  color: var(--primary);
  background: var(--primary-light);
}
```

### 4.3 대시보드 라우트 추가

**파일**: `app/api/routes/web.py` (추가)

```python
@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("pages/dashboard.html",
        {"request": request, "active_tab": "dashboard", "active_page": "dashboard"})
```

---

## 5. FastAPI 엔드포인트 구현

### 5.1 새 파일 생성

**파일**: `app/api/routes/service_token.py` (신규)

```python
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.service_token import ServiceToken
from app.models.user import User
from app.schemas.service_token import ServiceTokenResponse
from app.security import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

ALLOWED_SERVICES = {"jupyter", "mlflow"}


@router.post("/service-token/{service}", response_model=ServiceTokenResponse)
def get_service_token(
    service: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """사용자 서비스 토큰 발급 또는 조회"""
    
    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service: {service}")
    
    # DB에서 기존 토큰 조회
    token_record = db.query(ServiceToken).filter(
        ServiceToken.user_id == current_user.id,
        ServiceToken.service == service
    ).first()
    
    # 없으면 새로 생성
    if not token_record:
        token_value = f"{service}_{current_user.username}_{uuid4().hex[:16]}"
        token_record = ServiceToken(
            user_id=current_user.id,
            service=service,
            token=token_value
        )
        db.add(token_record)
        db.commit()
        db.refresh(token_record)
        logger.info(f"✅ Service token created: user={current_user.username}, service={service}")
    else:
        logger.info(f"✅ Service token retrieved: user={current_user.username}, service={service}")
    
    return token_record


@router.get("/service-token/{service}/redirect")
def redirect_to_service(
    service: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """서비스로 자동 리다이렉트"""
    from fastapi.responses import RedirectResponse
    
    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service: {service}")
    
    # 토큰 발급/조회
    token_record = get_service_token(service, current_user, db)
    
    settings = get_settings()
    
    if service == "jupyter":
        redirect_url = f"{settings.jupyter_base_url}?token={token_record.token}"
    elif service == "mlflow":
        redirect_url = f"{settings.mlflow_base_url}?token={token_record.token}"
    
    logger.info(f"🔄 Redirect to service: user={current_user.username}, service={service}, url={redirect_url}")
    
    return RedirectResponse(url=redirect_url, status_code=302)
```

### 5.2 API 라우터에 포함

**파일**: `app/api/router.py` (수정)

```python
from app.api.routes.service_token import router as service_token_router

api_router = APIRouter()
api_router.include_router(service_token_router)  # 서비스 토큰 라우터 추가
# 기존 라우터들...
```

---

## 6. 인증 및 보안

### 6.1 JWT 검증 플로우

```
요청 헤더: Authorization: Bearer <ACCESS_TOKEN>
  │
  ├─→ FastAPI Depends(get_current_user)
  │   ├─ 토큰 추출 (Bearer scheme)
  │   ├─ JWT 검증 (secret_key, 만료 시간)
  │   └─ user_id 복원
  │
  ├─→ DB에서 User 조회
  │
  └─→ current_user: User 객체 (view에 전달)
```

### 6.2 토큰 생성 규칙

토큰 형식: `{service}_{username}_{random_hex}`

예시:
- `jupyter_admin_a1b2c3d4e5f6g7h8`
- `mlflow_user_x9y8z7w6v5u4t3s2`

**특징**:
- 서비스별 독립적 토큰
- 사용자명 포함 (감시/감사 용이)
- 16자 난수 (충돌 확률 극저)

### 6.3 토큰 저장 및 조회

- 토큰은 **평문**으로 DB에 저장 (Jupyter/MLflow가 평문 토큰으로 검증)
- `UNIQUE(user_id, service)` 제약으로 중복 생성 방지
- 조회 시 기존 토큰 재사용 (통계 추적, 토큰 변동 최소화)

---

## 7. 로깅 및 감사

**로그 형식** (`app/api/routes/service_token.py`):

```
✅ Service token created: user=admin, service=jupyter
✅ Service token retrieved: user=admin, service=jupyter
🔄 Redirect to service: user=admin, service=jupyter, url=http://jupyterhub.mlops.click?token=...
```

감사 추적:
- 언제 누가 어느 서비스 토큰을 발급받았는가
- 토큰 재사용 vs 신규 발급
- 리다이렉트 성공 여부

---

## 8. 설정 통합

**파일**: `app/core/config.py` (기존)

```python
jupyter_base_url: str = Field(default="http://jupyterhub.mlops.click", alias="JUPYTER_BASE_URL")
mlflow_base_url: str = Field(default="http://mlflow.mlops.click", alias="MLFLOW_BASE_URL")
```

**환경 변수** (`.env` 또는 Kubernetes Secret):
```
JUPYTER_BASE_URL=http://jupyterhub.mlops.click
MLFLOW_BASE_URL=http://mlflow.mlops.click
```

---

## 9. 오류 처리

| 시나리오 | HTTP 상태 | 응답 |
|---------|----------|------|
| 허용되지 않는 service | 400 | `{"detail": "Invalid service: xyz"}` |
| JWT 토큰 없음 | 401 | `{"detail": "Not authenticated"}` |
| JWT 토큰 만료 | 401 | `{"detail": "Token expired"}` |
| DB 조회 실패 | 500 | `{"detail": "Internal Server Error"}` |

---

## 10. 구현 순서 (Phase 계획)

| Phase | 단계 | 파일 | 산출물 |
|-------|------|------|--------|
| **1** | DB 테이블 생성 | RDS SQL | `user_service_tokens` 테이블 |
| **1** | SQLAlchemy 모델 | `app/models/service_token.py` | ServiceToken 클래스 |
| **1** | Pydantic 스키마 | `app/schemas/service_token.py` | ServiceTokenResponse 클래스 |
| **2** | API 엔드포인트 구현 | `app/api/routes/service_token.py` | POST, GET /service-token/{service} |
| **2** | 라우터 등록 | `app/api/router.py` | service_token_router 포함 |
| **3** | 대시보드 페이지 추가 | `app/templates/pages/dashboard.html` | 서비스 카드 UI |
| **3** | 네비게이션 통합 | `app/templates/base.html` | 서비스 빠른 링크 |
| **3** | CSS 스타일 | `app/static/css/main.css` | 카드, 버튼 스타일 |
| **3** | 대시보드 라우트 | `app/api/routes/web.py` | GET /dashboard |
| **4** | Docker 빌드 및 배포 | `build_and_push.sh` | ECR 이미지 푸시 |
| **4** | Kubernetes 배포 | `kubectl rollout restart` | 새 Pod 시작 |
| **4** | 기능 테스트 | 브라우저 | Jupyter/MLflow 자동 로그인 확인 |

---

## 11. 테스트 시나리오

### 11.1 토큰 발급 테스트

```bash
# 1. Jupyter 토큰 발급
curl -X POST http://localhost:6080/api/auth/service-token/jupyter \
  -H "Authorization: Bearer {TOKEN}"

# 응답
{
  "id": 1,
  "user_id": 1,
  "service": "jupyter",
  "token": "jupyter_admin_a1b2c3d4e5f6g7h8",
  "created_at": "2026-05-26T10:30:00Z",
  "updated_at": "2026-05-26T10:30:00Z"
}

# 2. 동일한 서비스 재요청 (토큰 재사용)
curl -X POST http://localhost:6080/api/auth/service-token/jupyter \
  -H "Authorization: Bearer {TOKEN}"
# 응답: 동일한 token 값
```

### 11.2 리다이렉트 테스트

```bash
# 3. Jupyter로 리다이렉트
curl -X GET http://localhost:6080/api/auth/service-token/jupyter/redirect \
  -H "Authorization: Bearer {TOKEN}" \
  -L

# 응답: 302 Location: http://jupyterhub.mlops.click?token=jupyter_admin_a1b2c3d4e5f6g7h8
```

### 11.3 UI 테스트

1. 포탈 로그인 (admin/admin)
2. 대시보드 접속
3. "Jupyter Hub 이동" 버튼 클릭 → Jupyter 자동 로그인 확인
4. "MLflow 이동" 버튼 클릭 → MLflow 자동 로그인 확인
5. 로그에 토큰 발급/조회 로그 확인

---

## 12. 향후 고려사항

### 12.1 토큰 만료 (TTL)

현재: 토큰 무한 유효

향후: TTL 설정 및 갱신 로직
- `expires_at` 필드 추가
- 만료된 토큰 자동 갱신
- 사용자가 수동으로 토큰 재발급 가능

### 12.2 토큰 회수

향후: 특정 토큰 무효화
- 삭제 API: `DELETE /api/auth/service-token/{service}`
- 사용자가 토큰 로그아웃 (Jupyter/MLflow 세션 종료)

### 12.3 다중 서비스 확장

현재: Jupyter, MLflow (2개)

향후: 추가 서비스 통합
- Airflow, Superset, Metabase 등
- 동일한 메커니즘으로 확장 가능

### 12.4 OAuth 2.0 / OIDC

현재: 포탈 → 서비스 단방향 토큰 전달

향후: 표준 OAuth 2.0 / OIDC 구현
- Jupyter Hub의 OAuthenticator
- MLflow의 OIDC 지원
- 더욱 강력한 인증 표준화

---

## 13. 파일 체크리스트

| 파일 | 상태 | 비고 |
|------|------|------|
| `app/models/service_token.py` | 신규 | SQLAlchemy 모델 |
| `app/schemas/service_token.py` | 신규 | Pydantic 스키마 |
| `app/api/routes/service_token.py` | 신규 | API 엔드포인트 |
| `app/api/router.py` | 수정 | service_token_router 포함 |
| `app/templates/pages/dashboard.html` | 신규 | 대시보드 페이지 |
| `app/templates/base.html` | 수정 | 서비스 네비게이션 추가 |
| `app/static/css/main.css` | 수정 | 스타일 추가 |
| `app/api/routes/web.py` | 수정 | /dashboard 라우트 추가 |
| RDS (SQL) | 신규 | user_service_tokens 테이블 |
