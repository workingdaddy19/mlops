# 사용자별 서비스 토큰 관리 계획서

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | service-token-management |
| **작성일** | 2026-05-26 |
| **목표** | Jupyter Hub / MLflow에 대한 사용자별 토큰 관리 및 SSO 연동 |
| **대상 범위** | 로그인 사용자 → Jupyter/MLflow 자동 인증 |
| **현재 상태** | 🔴 미구현 (URL 설정만 완료) |

### Value Delivered (4-Perspective)

| 관점 | 내용 |
|------|------|
| **Problem** | 사용자가 Jupyter/MLflow에 별도로 로그인해야 하고, 토큰 관리가 분산됨 |
| **Solution** | 포탈 로그인 → 사용자별 토큰 DB 저장 → Jupyter/MLflow 자동 연동 |
| **Function UX Effect** | 포탈 로그인 후 "Jupyter 이동" 버튼 클릭 → 자동 인증 (단일 로그인) |
| **Core Value** | 통합 사용자 관리 + 편리한 서비스 접근 + 토큰 보안 중앙화 |

---

## 1. 현황 분석 (AS-IS)

### 1.1 현재 상태

```
포탈 (MLFoundry)
├── 로그인: ✅ admin/admin (작동)
├── 사용자: users 테이블에 admin, user 존재
└── 서비스 연결: 미구현

Jupyter Hub
├── URL: http://jupyterhub.mlops.click
├── 접속: 아무 id/pw 입력 가능 (인증 불필요)
└── 포탈과의 연동: ❌ 없음

MLflow
├── URL: http://mlflow.mlops.click
├── 접속: admin / Clkyobo11111!
└── 포탈과의 연동: ❌ 없음
```

### 1.2 문제점

| 문제 | 심각도 | 영향 |
|------|--------|------|
| 사용자가 각 서비스에 별도 로그인 | 중간 | 사용자 경험 불편 |
| 토큰 관리 분산 | 중간 | 보안 위험 |
| 사용자 추적 불가 | 낮음 | 감사 추적 미흡 |

---

## 2. 목표 아키텍처 (TO-BE)

### 2.1 시스템 흐름

```
사용자
  │
  ├─→ 포탈 로그인 (admin/admin)
  │   └─→ 토큰 생성/저장
  │
  ├─→ "Jupyter 이동" 버튼
  │   └─→ /api/auth/service-token/jupyter
  │       └─→ DB에서 토큰 조회
  │           └─→ Jupyter Hub로 리다이렉트 (토큰 전달)
  │               └─→ 자동 로그인 ✅
  │
  └─→ "MLflow 이동" 버튼
      └─→ /api/auth/service-token/mlflow
          └─→ DB에서 토큰 조회
              └─→ MLflow로 리다이렉트 (토큰 전달)
                  └─→ 자동 로그인 ✅
```

### 2.2 DB 스키마

```sql
CREATE TABLE user_service_tokens (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  service VARCHAR(50) NOT NULL,  -- 'jupyter', 'mlflow'
  token VARCHAR(500) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, service)
);
```

### 2.3 API 엔드포인트

| 엔드포인트 | 메서드 | 목적 |
|-----------|--------|------|
| `/api/auth/service-token/{service}` | POST | 토큰 발급/조회 |
| `/api/auth/service-token/{service}/redirect` | GET | 서비스로 리다이렉트 |

---

## 3. 단계별 구현 계획

### Phase 1: DB 및 모델 추가 (1일)

#### 3.1.1 DB 테이블 생성

```bash
psql -h rds-...amazonaws.com -U mlops -d mlops << 'SQL'
CREATE TABLE user_service_tokens (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  service VARCHAR(50) NOT NULL,
  token VARCHAR(500) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, service)
);
SQL
```

#### 3.1.2 SQLAlchemy 모델 추가

**파일**: `app/models/service_token.py`
```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ServiceToken(Base):
    __tablename__ = "user_service_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    token: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

---

### Phase 2: FastAPI 엔드포인트 구현 (1일)

#### 3.2.1 토큰 발급 엔드포인트

**파일**: `app/api/routes/auth.py` (기존 파일에 추가)

```python
@router.post("/service-token/{service}")
def get_service_token(
    service: str,
    current_user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """사용자 서비스 토큰 발급 또는 조회"""
    if service not in ["jupyter", "mlflow"]:
        raise HTTPException(status_code=400, detail="Invalid service")
    
    # DB에서 기존 토큰 조회
    token = db.query(ServiceToken).filter(
        ServiceToken.user_id == current_user.id,
        ServiceToken.service == service
    ).first()
    
    # 없으면 새로 생성
    if not token:
        token_value = f"{service}_{current_user.username}_{uuid4().hex[:16]}"
        token = ServiceToken(
            user_id=current_user.id,
            service=service,
            token=token_value
        )
        db.add(token)
        db.commit()
    
    logger.info(f"✅ Service token issued: user={current_user.username}, service={service}")
    return {"service": service, "token": token.token}


@router.get("/service-token/{service}/redirect")
def redirect_to_service(
    service: str,
    current_user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """서비스로 리다이렉트 (자동 로그인)"""
    if service == "jupyter":
        # Jupyter 토큰 발급
        result = get_service_token(service, current_user, db)
        return RedirectResponse(
            url=f"{settings.jupyter_base_url}?token={result['token']}"
        )
    elif service == "mlflow":
        # MLflow 토큰 발급
        result = get_service_token(service, current_user, db)
        # MLflow의 토큰 전달 방식 (URL 파라미터 또는 헤더)
        return RedirectResponse(
            url=f"{settings.mlflow_base_url}?token={result['token']}"
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid service")
```

---

### Phase 3: 프론트엔드 통합 (1.5일)

#### 3.3.1 대시보드에 서비스 버튼 추가

**파일**: `app/templates/pages/dashboard.html`

```html
<div class="service-shortcuts">
  <h3>빠른 연결</h3>
  <button onclick="goToService('jupyter')" class="btn btn-info">
    📓 Jupyter Hub 이동
  </button>
  <button onclick="goToService('mlflow')" class="btn btn-info">
    📈 MLflow 이동
  </button>
</div>

<script>
async function goToService(service) {
  try {
    const response = await apiFetch(`/api/auth/service-token/${service}/redirect`);
    // 서버에서 자동으로 리다이렉트됨
  } catch (err) {
    alert(`${service} 접속 실패: ${err.message}`);
  }
}
</script>
```

#### 3.3.2 네비게이션 메뉴에 버튼 추가

**파일**: `app/templates/base.html`

```html
<div class="nav-services">
  <a href="#" onclick="goToService('jupyter')" class="nav-link">
    Jupyter
  </a>
  <a href="#" onclick="goToService('mlflow')" class="nav-link">
    MLflow
  </a>
</div>
```

---

### Phase 4: 검증 및 배포 (1일)

#### 3.4.1 테스트

```bash
# 1. 토큰 발급 확인
curl -X POST http://localhost:6080/api/auth/service-token/jupyter \
  -H "Authorization: Bearer <TOKEN>"

# 2. 리다이렉트 확인
curl -X GET http://localhost:6080/api/auth/service-token/jupyter/redirect \
  -H "Authorization: Bearer <TOKEN>" -L
```

#### 3.4.2 Docker 빌드 및 배포

```bash
bash build_and_push.sh
kubectl rollout restart deployment/mlfoundry-backend -n mlops
```

---

## 4. 기술 스택

| 항목 | 선택 | 이유 |
|------|------|------|
| **DB** | PostgreSQL | 기존 RDS 활용 |
| **ORM** | SQLAlchemy | 기존 코드 일관성 |
| **Framework** | FastAPI | 기존 프레임워크 |
| **토큰** | UUID 기반 | 간단하고 안전 |

---

## 5. 위험 요소 & 대응

| 위험 | 확률 | 영향 | 대응 |
|------|------|------|------|
| Jupyter/MLflow 토큰 형식 호환 | 중간 | 높음 | 서비스별 토큰 검증 필요 |
| 사용자 추적 불가 | 낮음 | 낮음 | 로깅 추가 |
| 토큰 만료 | 낮음 | 중간 | TTL 설정 (향후) |

---

## 6. 일정

| Phase | 기간 | 담당 |
|-------|------|------|
| 1. DB 및 모델 | 1일 | 개발팀 |
| 2. API 엔드포인트 | 1일 | 개발팀 |
| 3. 프론트엔드 | 1.5일 | 프론트엔드팀 |
| 4. 검증 및 배포 | 1일 | DevOps |

**Total**: 4.5일

---

## 7. 다음 단계

> `/pdca design service-token-management` 로 상세 설계 진행
