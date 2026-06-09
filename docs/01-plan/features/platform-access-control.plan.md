# Feature Plan: platform-access-control

## Executive Summary

| 항목 | 내용 |
|------|------|
| Feature | platform-access-control |
| 시작일 | 2026-06-01 |
| 예상 기간 | 5일 |
| 우선순위 | High |

### Value Delivered (4-Perspective)

| 관점 | 내용 |
|------|------|
| **Problem** | 사용자별 기능 접근 제어 없음, MLFlow/Airflow 수동 로그인 불편, Airflow 메뉴 미존재 |
| **Solution** | DB 기반 Feature Permission 모델 + 자동 로그인 SSO + Airflow 신규 메뉴 |
| **Function UX Effect** | 권한 없는 버튼 비활성화·숨김, MLFlow/Airflow 원클릭 접속, 관리자 권한 토글 UI |
| **Core Value** | 보안 강화 + 사용자 경험 개선 + 플랫폼 통합 완성 |

---

## 1. 요구사항 요약

### 1-1. Airflow 신규 메뉴
- URL: `https://airflow.mlops.click` (접속 정보 별도 전달 예정)
- 사이드바에 Airflow 메뉴 추가
- 권한 있는 사용자만 "Airflow 열기" 버튼 활성화
- 현재 MLFlow 페이지와 동일한 레이아웃 패턴

### 1-2. MLFlow 자동 로그인
- 현재: 사용자가 MLFlow 열기 클릭 → 새 탭 → 수동 로그인
- 목표: MLFlow 권한 있는 사용자가 클릭 → 자동 인증된 상태로 접속
- MLFlow URL: `http://mlflow.mlops.click`
- 인증 정보: admin / Clkyobo11111! (공유 계정, 포털에서만 관리)

### 1-3. Jupyter ↔ Experiment 연동 (분석과제 접속)
- 현재: Jupyter 접속 버튼 → JupyterHub 홈으로 이동
- 목표: MLFlow Experiment와 Jupyter 작업 폴더를 자연스럽게 연결
- 방향: MLFlow 실험 목록에서 "Jupyter에서 열기" 버튼 or
  Jupyter 접속 시 experiment 이름 기반 폴더로 직접 이동

### 1-4. 기능별 사용자 권한 관리
- 대상 기능 5가지: `s3`, `athena`, `jupyter`, `mlflow`, `airflow`
- 관리 화면: 기존 사용자 관리 페이지에 권한 컬럼/모달 추가
- 적용 방식: 페이지 로드 시 권한 확인 후 UI 요소 제어

---

## 2. 기술 설계 방향

### 2-1. Permission 데이터 모델
```
UserFeaturePermission (신규 테이블)
├── id: int PK
├── user_id: int FK → users.id
├── feature: str  # 's3' | 'athena' | 'jupyter' | 'mlflow' | 'airflow'
└── granted_at: datetime
```
- `admin` 역할은 모든 기능 자동 허용 (DB 레코드 불필요)
- `user` 역할은 명시적 레코드 있을 때만 허용

### 2-2. API 설계
```
GET  /api/auth/me/permissions          → 현재 로그인 유저 권한 목록
GET  /api/admin/users/{id}/permissions → 특정 유저 권한 조회 (admin)
PUT  /api/admin/users/{id}/permissions → 권한 일괄 설정 (admin)
     body: { features: ["s3", "athena"] }
```

### 2-3. MLFlow 자동 로그인 방식
**채택: Backend SSO Redirect (보안·호환성 균형)**
- `/api/mlflow/sso` 엔드포인트가 다음을 수행:
  1. 현재 사용자 mlflow 권한 확인
  2. MLFlow Basic Auth 세션 쿠키 취득 (서버 측 requests)
  3. `Set-Cookie` 포함 Redirect 응답 반환
- 폴백: URL 임베드 방식 `http://admin:pass@mlflow.mlops.click`
  (모던 브라우저 제한 있으므로 SSO 방식 우선)

### 2-4. Airflow 자동 로그인
- MLFlow와 동일한 SSO 패턴 적용
- 접속 정보: **admin / admin** (확정)
- system_settings 테이블에 저장 (`AIRFLOW_URL`, `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD`)

### 2-5. Jupyter ↔ Experiment 연동 방향
**권고: 단계별 접근**
- **1단계 (이번 스프린트)**: Jupyter 접속 시 lab 화면으로 이동 (현재와 동일, JWT SSO 유지)
- **2단계 (다음)**: MLFlow 페이지에 실험 목록 조회 + 각 실험에 "Jupyter에서 열기" 버튼
  → 클릭 시 `/user/{username}/lab/tree/{experiment_name}` 경로로 이동
- JupyterHub 서버 내 `~/experiments/{experiment_name}/` 폴더 규칙 사전 정의 필요

### 2-6. UI 권한 제어 방식
- 페이지 로드 시 `GET /api/auth/me/permissions` 호출
- 반환값 기반으로 각 페이지 JS에서 버튼 제어
- **화면별 제어 내용**:

| 화면 | 권한 없을 때 |
|------|------------|
| Athena DB | 실행 버튼 disabled + 안내 tooltip |
| Jupyter | 접속 버튼 disabled |
| MLFlow | MLFlow 열기 버튼 disabled |
| S3 스토리지 | 파일 목록 숨김 + 다운로드 버튼 제거 |
| Airflow | Airflow 열기 버튼 disabled |

---

## 3. 구현 범위 (이번 스프린트)

### Phase A: Permission 백엔드 (Day 1-2)
- [ ] `UserFeaturePermission` 모델 + Alembic 마이그레이션
- [ ] `UserPermissionRepository` CRUD
- [ ] `GET /api/auth/me/permissions` API
- [ ] `GET/PUT /api/admin/users/{id}/permissions` API
- [ ] `require_feature_permission("mlflow")` FastAPI Depends 헬퍼

### Phase B: MLFlow SSO (Day 2)
- [ ] `/api/mlflow/sso` 엔드포인트 구현
- [ ] mlflow.html 버튼 → SSO 엔드포인트 호출 방식으로 변경
- [ ] 권한 없는 경우 버튼 disabled 처리

### Phase C: Airflow 신규 메뉴 (Day 3)
- [ ] `app/templates/pages/airflow.html` 생성 (mlflow.html 패턴)
- [ ] `app/api/routes/airflow.py` 생성 (health check + SSO)
- [ ] `app/services/airflow_service.py` 생성
- [ ] 사이드바 네비게이션에 Airflow 메뉴 추가 (base.html)
- [ ] `/airflow` 웹 라우트 등록 (web.py)
- [ ] system_settings에 `AIRFLOW_URL`, `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD` seed

### Phase D: 관리자 권한 UI (Day 3-4)
- [ ] `admin_users.html`: 사용자 행에 권한 뱃지 컬럼 추가
- [ ] 사용자 편집 모달에 기능 권한 토글 (5개 체크박스) 추가
- [ ] 권한 저장 API 연동

### Phase E: 각 페이지 권한 제어 (Day 4-5)
- [ ] `base.html` or 공통 JS에 `loadMyPermissions()` 함수 추가
- [ ] `query.html` (Athena): 권한 확인 후 실행 버튼 제어
- [ ] `jupyter.html`: 권한 확인 후 접속 버튼 제어
- [ ] `mlflow.html`: 권한 확인 후 열기 버튼 제어
- [ ] `files.html` (S3): 권한 확인 후 파일 목록·다운로드 제어
- [ ] `airflow.html`: 권한 확인 후 열기 버튼 제어

---

## 4. 이번 스프린트 제외 (다음 스프린트)

- MLFlow 실험 목록 in-portal 조회 (Jupyter 연동 2단계)
- Airflow DAG 목록 in-portal 조회
- 권한 변경 이력(audit log)

---

## 5. 변경 파일 목록 (예상)

```
신규:
  app/models/user_permission.py
  app/repositories/user_permission_repo.py
  app/api/routes/airflow.py
  app/services/airflow_service.py
  app/templates/pages/airflow.html
  alembic/versions/xxxx_add_user_feature_permissions.py

수정:
  app/api/routes/admin.py         (권한 관리 API 추가)
  app/api/routes/auth.py          (me/permissions 엔드포인트 추가)
  app/api/routes/mlflow_proxy.py  (SSO 엔드포인트 추가)
  app/api/router.py               (airflow 라우터 등록)
  app/api/routes/web.py           (airflow 웹 라우트)
  app/services/mlflow_service.py  (SSO 로직 추가)
  app/services/settings_seed.py   (Airflow 설정 seed 추가)
  app/templates/base.html         (Airflow 메뉴 + 공통 권한 JS)
  app/templates/pages/admin_users.html  (권한 토글 UI)
  app/templates/pages/query.html  (Athena 권한 제어)
  app/templates/pages/jupyter.html
  app/templates/pages/mlflow.html
  app/templates/pages/files.html
```

---

## 6. 위험 요소 및 대응

| 위험 | 대응 |
|------|------|
| MLFlow Basic Auth SSO → 브라우저 CORS | 서버사이드 프록시로 쿠키 전달, 폴백 URL 방식 유지 |
| Airflow 인증 방식 미확정 | system_settings에 설정 저장, 전달받은 후 SSO 구현 |
| DB 마이그레이션 (운영 중 스키마 변경) | Alembic migration, nullable 컬럼으로 안전하게 추가 |
| 기존 admin 사용자 권한 처리 | admin role → 모든 기능 자동 허용 (코드 레벨) |
