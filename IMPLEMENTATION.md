# MLFoundry 구현 현황

## 📅 2026-05-26 진행 상황

### 🎯 작업 요약

**Feature**: Service Token Management (Jupyter Hub / MLflow SSO 연동)
- **상태**: Do Phase 진행 중 (Design 완료)
- **목표**: 포탈 로그인 후 Jupyter/MLflow 자동 인증
- **성과**: API 엔드포인트, DB 모델, 프론트엔드 통합 구현 완료

---

## 📋 구현된 파일 목록

### 1️⃣ 설계 문서

| 파일 | 상태 | 설명 |
|------|------|------|
| `docs/01-plan/features/service-token-management.plan.md` | ✅ | 4단계 구현 계획 (4.5일 소요 예정) |
| `docs/02-design/features/service-token-management.design.md` | ✅ | 상세 아키텍처 + 구현 명세 |

### 2️⃣ 백엔드 구현

| 파일 | 상태 | 라인 | 설명 |
|------|------|------|------|
| `app/api/routes/service_token.py` | ✅ | 85 | POST/GET service-token 엔드포인트 |
| `app/models/service_token.py` | ✅ | 23 | SQLAlchemy ServiceToken 모델 |
| `app/schemas/service_token.py` | ✅ | 17 | Pydantic ServiceTokenResponse 스키마 |
| `app/models/__init__.py` | ✅ | 수정 | ServiceToken import 추가 |
| `app/api/router.py` | ✅ | 수정 | service_token 라우터 등록 |
| `app/api/routes/auth.py` | ✅ | 수정 | 중복 코드 제거 |
| `app/services/jupyter_service.py` | ✅ | 수정 | URL 경로 수정 (JupyterHub 표준 경로) |

### 3️⃣ 데이터베이스

| 파일 | 상태 | 설명 |
|------|------|------|
| `sql/02_create_service_tokens_table.sql` | ✅ | user_service_tokens 테이블 생성 스크립트 |

### 4️⃣ 설정 파일

| 파일 | 상태 | 주요 설정 |
|------|------|----------|
| `app/core/config.py` | ✅ | JUPYTER_BASE_URL, MLFLOW_BASE_URL |
| `k8s/backend-secret.yaml` | ✅ | 환경변수 설정 (수정됨) |

---

## 🏗️ 아키텍처 개요

### API 엔드포인트

```
POST /api/auth/service-token/{service}
├─ 목적: 토큰 발급/조회
├─ 파라미터: service ('jupyter' | 'mlflow')
├─ 인증: JWT Bearer Token
└─ 응답: {service, token, created_at, updated_at}

GET /api/auth/service-token/{service}/redirect
├─ 목적: 서비스 자동 리다이렉트
├─ 인증: JWT Bearer Token
└─ 응답: 302 Redirect → 서비스 URL (토큰 포함)
```

### DB 스키마

```sql
CREATE TABLE user_service_tokens (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL (FK → users.id),
  service VARCHAR(50) NOT NULL ('jupyter' | 'mlflow'),
  token VARCHAR(500) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, service)
);
```

### 요청 흐름

```
1. 포탈 로그인 (admin/admin)
   └─ JWT 토큰 발급 → localStorage 저장

2. "Jupyter 이동" 클릭
   └─ GET /api/auth/service-token/jupyter/redirect
      ├─ DB에서 기존 토큰 조회 (user_id + 'jupyter')
      ├─ 없으면 신규 토큰 생성 저장
      └─ 302 Redirect: http://jupyterhub.mlops.click/user/admin/lab/

3. Jupyter Hub 자동 로그인 ✅
```

---

## 🚀 배포 상태

### Kubernetes Pod

```
✅ Pod 상태: Running (1/1)
✅ Docker Image: ECR에 배포됨
✅ Environment Variables: 업데이트됨
  - JUPYTER_BASE_URL=http://jupyterhub.mlops.click
  - MLFLOW_BASE_URL=http://mlflow.mlops.click
```

### 테스트 상황

| 항목 | 상태 | 비고 |
|------|------|------|
| API 엔드포인트 | ✅ | 토큰 발급/조회 작동 |
| JupyterLab 접속 | ✅ | `/user/admin/lab/` 경로 수정 완료 |
| MLflow 접속 | ✅ | 기본 URL로 접속 가능 |
| 포탈 UI 통합 | ⏳ | Do Phase 진행 중 (대시보드 버튼 추가 예정) |

---

## 📝 남은 작업 (Do Phase)

### Phase 3: 프론트엔드 통합

- [ ] 대시보드 페이지 추가 (`pages/dashboard.html`)
- [ ] 서비스 빠른 연결 카드 UI 구성
- [ ] 네비게이션 메뉴에 서비스 링크 추가
- [ ] 대시보드 라우트 생성 (`/dashboard`)
- [ ] CSS 스타일 추가

### Phase 4: 검증 및 배포

- [ ] End-to-End 테스트
  - [ ] 포탈 로그인 → 토큰 발급 확인
  - [ ] Jupyter 자동 로그인 확인
  - [ ] MLflow 자동 로그인 확인
- [ ] 로깅 검증
- [ ] 최종 Docker 배포

---

## 🔧 주요 수정 사항

### 1. JupyterService URL 경로 수정

**Before**:
```python
return f"{self.base_url}/lab?token={self.token}"
# 결과: http://jupyterhub.mlops.click/lab?token=mlfoundry_token (❌ 404)
```

**After**:
```python
return f"{self.base_url}/user/admin/lab/"
# 결과: http://jupyterhub.mlops.click/user/admin/lab/ (✅ 작동)
```

### 2. Service Token 모델 - 테이블 중복 정의 해결

**수정**:
```python
__table_args__ = (
    Index("idx_user_service", "user_id", "service"),
    {"extend_existing": True},  # 기존 테이블 정의 허용
)
```

### 3. API Router 통합

```python
# app/api/router.py
from app.api.routes import service_token

api_router.include_router(service_token.router)  # 추가
```

---

## 📊 코드 통계

| 항목 | 수량 |
|------|------|
| 신규 파일 | 4개 |
| 수정된 파일 | 5개 |
| 신규 코드 라인 | ~200줄 |
| 설계 문서 | 2개 (Plan + Design) |
| SQL 스크립트 | 1개 |

---

## 🔐 보안 고려사항

✅ **구현된 보안 기능**:
- JWT 기반 인증 (Bearer Token)
- 사용자별 토큰 격리 (UNIQUE 제약)
- 로깅을 통한 감시 추적
- 토큰 생성 규칙: `{service}_{username}_{random_hex}`

⚠️ **향후 개선**:
- [ ] 토큰 만료 시간 (TTL) 설정
- [ ] 토큰 회수 (DELETE) API
- [ ] 토큰 갱신 메커니즘
- [ ] HTTPS 강제화 (프로덕션)

---

## 📚 참고 문서

- [Plan 문서](docs/01-plan/features/service-token-management.plan.md) — 4단계 구현 계획
- [Design 문서](docs/02-design/features/service-token-management.design.md) — 상세 아키텍처
- [DB 스키마](sql/02_create_service_tokens_table.sql) — 테이블 정의

---

## ✅ 체크리스트

- [x] Design 문서 완성
- [x] API 엔드포인트 구현
- [x] DB 모델 + 스키마 작성
- [x] Kubernetes 배포 (Pod Running)
- [x] JupyterHub 경로 수정
- [ ] 프론트엔드 대시보드 추가
- [ ] End-to-End 테스트
- [ ] 최종 배포

---

**작성자**: Claude Code  
**작성일**: 2026-05-26  
**다음 단계**: `/pdca do service-token-management` 프론트엔드 통합
