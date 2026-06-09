# Plan: portal-redesign

## Executive Summary

| 항목 | 내용 |
|------|------|
| Feature | portal-redesign |
| 작성일 | 2026-05-27 |
| 예상 기간 | 2~3일 |
| 우선순위 | High |

| 관점 | 설명 |
|------|------|
| **Problem** | 상단 탭 메뉴와 좌측 사이드바가 이중으로 존재해 UX 혼란 발생. 사용자 등록·권한 관리 UI 없어 CLI/kubectl만으로 운영. 환경 설정 변경 시마다 소스 배포 필요. |
| **Solution** | 상단 탭 제거 → 좌측 단일 사이드바로 통합. 접기/펼치기 가능한 accordion 메뉴. 사용자 관리 Admin 페이지. DB 기반 시스템 설정 관리. |
| **Function UX Effect** | 화면 상단 공간 확보(60px 절약), 메뉴 계층 직관적 시각화, Admin만 관리 메뉴 표시, 설정 변경 즉시 반영 (재배포 불필요). |
| **Core Value** | 운영자 생산성 향상 — 사용자 등록·설정 변경을 UI에서 직접 처리, 개발·배포 의존성 제거. |

---

## 1. 배경 및 목표

### 1.1 현황

| 항목 | 현재 상태 | 문제점 |
|------|-----------|--------|
| 상단 네비 탭 | 홈, Data, AI ML, 게시판, S3 스토리지 | 좌측 사이드바와 역할 중복, 화면 낭비 |
| 좌측 사이드바 | 탭별 서브 메뉴만 표시 | 전체 메뉴 구조 파악 불가, 접기 불가 |
| 사용자 관리 | `scripts/add_users.py` + kubectl exec | UI 없음, 비기술직 운영자 불가 |
| 설정 관리 | `backend-secret.yaml` → k8s Secret | 설정 변경마다 재배포 필요 |
| 브랜드명 "AI ML" | base.html에 이미 "AI 데이터 분석" | 사이드바 섹션 타이틀은 여전히 "AI ML" |

### 1.2 목표

1. **네비게이션 단일화**: 상단 탭 완전 제거, 좌측 사이드바 단일 메뉴 체계
2. **사이드바 UX**: 햄버거 버튼으로 접기/펼치기, 대메뉴 accordion 토글
3. **사용자 관리 Admin UI**: 목록 조회, 신규 등록, 역할(user/admin) 변경, 삭제
4. **설정 DB 화**: 비민감 설정값을 `system_settings` 테이블로 이관 → UI에서 수정
5. **메뉴 구조 재편**: 새 계층 구조로 URL 라우트 및 breadcrumb 정리

---

## 2. 요구사항

### 2.1 기능 요구사항

#### FR-01: 상단 네비게이션 탭 제거
- `base.html` `.nav-tabs` 영역 완전 삭제
- 브랜드 로고 + 사용자명 + 로그아웃 버튼만 남김
- 또는 상단 bar 전체 제거 후 사이드바 상단에 브랜드/유저 정보 통합 (옵션)

#### FR-02: 좌측 사이드바 — 전체 메뉴 항상 표시
현재: 탭에 따라 해당 섹션만 표시 (조건부 렌더링)
변경: 모든 대메뉴를 항상 좌측에 표시

```
┌─────────────────────┐
│  🏠 Home            │
│  📢 Notice          │
│  📁 Data          ▼ │ ← accordion 열림
│    ├ 🗄️ S3 스토리지 │
│    └ 📊 Athena DB   │
│  🔬 Analysis      ▶ │ ← accordion 닫힘
│  📈 Models        ▶ │
│  ⚙️ Management    ▼ │ ← admin만 표시
│    ├ 👥 Users       │
│    └ 🔧 Settings    │
└─────────────────────┘
```

#### FR-03: 사이드바 접기/펼치기
- 햄버거(☰) 버튼 클릭 → `--sidebar-width: 240px` → `0px` (완전 숨김)
- 또는 collapsed 상태: `--sidebar-collapsed-width: 56px` (아이콘만 표시)
- 상태는 `localStorage.sidebarCollapsed` 유지

#### FR-04: 대메뉴 Accordion 토글
- Data, Analysis, Models, Management 각 대메뉴 클릭 시 하위 메뉴 접기/펼치기
- 현재 활성 페이지 소속 대메뉴는 자동 열림
- 상태는 `localStorage.menuOpen_{section}` 유지

#### FR-05: URL 구조 — 신규 라우트 추가
| 메뉴 | URL | 비고 |
|------|-----|------|
| Home | `/dashboard` | 기존 유지 |
| Notice | `/board` | 기존 유지 |
| S3 스토리지 | `/files` | 기존 유지 |
| Athena DB | `/data/query` | 기존 유지 |
| Jupyter | `/aiml/jupyter` | 기존 유지 |
| MLFlow | `/aiml/mlflow` | 기존 유지 |
| Users | `/admin/users` | **신규** |
| Settings | `/admin/settings` | **신규** |

#### FR-06: Admin 사용자 관리 페이지 (`/admin/users`)
- **목록 조회**: username, name, role, created_at 테이블
- **신규 등록**: 모달 팝업 — username, password, name, role(user/admin)
- **역할 변경**: role 드롭다운 인라인 변경 → API PUT
- **삭제**: 확인 다이얼로그 → API DELETE (자기 자신 삭제 방지)
- **권한**: `role == "admin"` 사용자만 접근 (서버 사이드 체크 + 사이드바 표시 조건)

#### FR-07: 사용자 관리 API (`/api/admin/users`)
```
GET    /api/admin/users          목록 (admin only)
POST   /api/admin/users          신규 등록 (admin only)
PUT    /api/admin/users/{id}     역할/이름 수정 (admin only)
DELETE /api/admin/users/{id}     삭제 (admin only, 자기 자신 제외)
```

#### FR-08: 시스템 설정 DB 테이블 (`system_settings`)
```sql
CREATE TABLE system_settings (
  key   VARCHAR(100) PRIMARY KEY,
  value TEXT NOT NULL,
  label VARCHAR(200),          -- 화면 표시용 한글명
  group VARCHAR(50),           -- 'jupyter', 'mlflow', 'athena', 's3'
  updated_at TIMESTAMP DEFAULT now()
);
```

초기 데이터 (Secret에서 이관):
| key | value | label | group |
|-----|-------|-------|-------|
| `MLFLOW_BASE_URL` | `http://mlflow.mlops.click` | MLFlow 접속 URL | mlflow |
| `JUPYTER_BASE_URL` | `http://jupyterhub.mlops.click` | JupyterHub 접속 URL | jupyter |
| `JUPYTER_ENVS` | `[{"name":"CPU 환경","server":""},...]` | Jupyter 환경 목록 (JSON) | jupyter |
| `ATHENA_DATABASE` | `mlops` | Athena 기본 데이터베이스 | athena |
| `ATHENA_S3_OUTPUT` | `s3://s3-an2-mlflow/athena-results/` | Athena 결과 저장 경로 | athena |
| `S3_BUCKET_NAME` | `s3-an2-mlflow` | S3 버킷명 | s3 |

> **민감 정보는 DB에 저장하지 않음**: DB_PASSWORD, SECRET_KEY, JUPYTERHUB_ADMIN_TOKEN, AWS 자격증명 — 계속 k8s Secret 사용

#### FR-09: 설정 관리 페이지 (`/admin/settings`)
- 그룹별 탭 (Jupyter, MLFlow, Athena, S3)
- 각 설정 키/값 인라인 편집 → 저장
- 저장 후 서비스 캐시 무효화 (설정 즉시 반영)
- **권한**: admin only

#### FR-10: 설정 API (`/api/admin/settings`)
```
GET  /api/admin/settings         전체 목록 (admin only)
GET  /api/admin/settings/{key}   단건 조회 (services에서 내부 호출)
PUT  /api/admin/settings/{key}   값 변경 (admin only)
```

#### FR-11: 서비스 레이어 — DB 설정 우선, env 폴백
```python
# config 로딩 우선순위:
# 1. DB system_settings 테이블
# 2. 환경변수 (.env / k8s Secret)
# 3. 하드코딩 기본값
```

### 2.2 비기능 요구사항

| 항목 | 요구사항 |
|------|----------|
| 설정 캐시 | DB 설정값은 앱 메모리에 캐시 (TTL 60초), 저장 시 캐시 즉시 무효화 |
| 권한 통일 | Admin API는 `get_current_admin_user` 의존성으로 일괄 적용 |
| 마이그레이션 | Alembic migration 또는 앱 시작 시 `CREATE TABLE IF NOT EXISTS` |
| 반응형 | 사이드바 접힌 상태에서 콘텐츠 영역 100% 사용 |
| 브라우저 호환 | CSS custom properties + `localStorage` — 최신 Chrome/Edge |

---

## 3. 구현 범위 (Scope)

### In Scope
- [x] `base.html` 전면 개편 (상단 탭 제거, 사이드바 accordion)
- [x] `main.css` 레이아웃 변수 수정 (navbar 제거 또는 슬림화)
- [x] `app/static/js/app.js` 사이드바 토글 JS
- [x] `app/models/system_settings.py` 신규 모델
- [x] `app/repositories/settings_repo.py` 신규 레포지토리
- [x] `app/services/settings_service.py` 캐시 포함
- [x] `app/api/routes/admin.py` (users + settings API)
- [x] `app/api/routes/web.py` 신규 라우트 2개 추가
- [x] `app/templates/pages/admin_users.html` 신규
- [x] `app/templates/pages/admin_settings.html` 신규
- [x] `app/services/jupyter_service.py` → DB 설정 참조로 변경
- [x] `app/services/query_service.py` (Athena) → DB 설정 참조로 변경
- [x] `app/api/deps.py` → `get_current_admin_user` 의존성 추가

### Out of Scope
- 권한 세분화 (user / admin 2단계로 충분)
- 민감 정보(암호화 키, DB 비번)의 DB 이관
- 사이드바 드래그 리사이즈
- 다크모드

---

## 4. 구현 순서

### Phase A: DB 모델 & 마이그레이션 (Day 1 AM)
1. `app/models/system_settings.py` — SystemSetting 모델
2. DB 초기화 시 테이블 생성 + seed 데이터 삽입
3. `app/repositories/settings_repo.py` — get/set/list
4. `app/services/settings_service.py` — 캐시 (60초 TTL)

### Phase B: Admin API (Day 1 PM)
5. `app/api/deps.py` — `get_current_admin_user` 추가
6. `app/api/routes/admin.py` — Users CRUD + Settings CRUD
7. `app/main.py` — admin router include

### Phase C: 네비게이션 리디자인 (Day 2 AM)
8. `app/static/css/main.css` — navbar 높이 제거, sidebar 전체 메뉴 스타일
9. `app/templates/base.html` — 상단 탭 제거, accordion 사이드바
10. `app/static/js/app.js` — 사이드바 토글, accordion 토글
11. `app/api/routes/web.py` — `/admin/users`, `/admin/settings` 라우트 추가

### Phase D: Admin UI 페이지 (Day 2 PM)
12. `app/templates/pages/admin_users.html` — 목록/등록/수정/삭제
13. `app/templates/pages/admin_settings.html` — 그룹별 설정 편집

### Phase E: 서비스 레이어 DB 연동 & 통합 테스트 (Day 3)
14. `JupyterService` — DB에서 `JUPYTER_BASE_URL`, `JUPYTER_ENVS` 읽기
15. `QueryService` (Athena) — DB에서 `ATHENA_DATABASE`, `ATHENA_S3_OUTPUT` 읽기
16. E2E 테스트: 설정 변경 → 즉시 반영 확인

---

## 5. 파일 변경 목록

### 신규 생성
| 파일 | 설명 |
|------|------|
| `app/models/system_settings.py` | SystemSetting ORM 모델 |
| `app/repositories/settings_repo.py` | 설정 CRUD 레포지토리 |
| `app/services/settings_service.py` | 설정 서비스 (캐시 포함) |
| `app/api/routes/admin.py` | Admin API 라우터 |
| `app/templates/pages/admin_users.html` | 사용자 관리 페이지 |
| `app/templates/pages/admin_settings.html` | 설정 관리 페이지 |

### 수정
| 파일 | 변경 내용 |
|------|-----------|
| `app/templates/base.html` | 상단 탭 제거, accordion 사이드바 전체 메뉴 |
| `app/static/css/main.css` | 레이아웃 변수, navbar 슬림/제거, sidebar 스타일 |
| `app/static/js/app.js` | 사이드바 토글, accordion JS |
| `app/api/routes/web.py` | admin 페이지 라우트 2개 추가 |
| `app/api/deps.py` | `get_current_admin_user` 추가 |
| `app/main.py` | admin router 등록 |
| `app/models/__init__.py` | SystemSetting import 추가 |
| `app/core/database.py` | seed 데이터 삽입 로직 추가 |
| `app/services/jupyter_service.py` | DB 설정 우선 참조 |
| `app/services/query_service.py` | DB 설정 우선 참조 |

---

## 6. 위험 요소 및 대응

| 위험 | 영향 | 대응 |
|------|------|------|
| 기존 페이지 active_tab 로직 깨짐 | 메뉴 활성화 표시 오류 | `active_page` 값 기반으로 사이드바 active 판단 통일 |
| DB 설정 로드 실패 시 서비스 중단 | JupyterHub/Athena 접속 불가 | `try/except` + env 폴백 보장 |
| Admin 권한 체크 누락 | 일반 사용자가 관리 기능 접근 | `get_current_admin_user` deps 일괄 적용 + 403 반환 |
| 사이드바 접힘 시 레이아웃 깨짐 | 콘텐츠 영역 오버랩 | CSS `transition` + `margin-left` 동적 조정 |
