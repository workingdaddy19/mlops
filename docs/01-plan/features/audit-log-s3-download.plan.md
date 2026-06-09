# Feature Plan: audit-log-s3-download

## Executive Summary

| 항목 | 내용 |
|------|------|
| Feature | audit-log-s3-download |
| 시작일 | 2026-06-01 |
| 예상 기간 | 3일 |
| 우선순위 | High (금융사 컴플라이언스 요건) |

### Value Delivered (4-Perspective)

| 관점 | 내용 |
|------|------|
| **Problem** | 사용자 행동 추적 없음 → 보안 감사 불가, S3 파일 다운로드 사유 미기록 → 데이터 유출 관리 불가 |
| **Solution** | DB 기반 감사 로그 + 사이드바 접속기록 메뉴 + S3 다운로드 사유 입력 팝업 |
| **Function UX Effect** | 관리자 실시간 접속 현황 조회, 다운로드 시 사유 입력 강제, 이력 검색/필터 |
| **Core Value** | 금융사 컴플라이언스 충족 + 내부 보안 감사 대응 + 데이터 접근 책임 추적 |

---

## 1. 요구사항

### 1-1. 접속 기록 (Audit Log)
- **위치**: Management 그룹에 Users와 Settings 사이에 "접속기록" 메뉴 추가
- **접근 권한**: admin only
- **기록 대상 이벤트**:
  | 이벤트 유형 | 설명 | 예시 |
  |------------|------|------|
  | `login` | 로그인 성공/실패 | 사용자명, 결과, IP |
  | `logout` | 로그아웃 | 세션 시간 |
  | `page_view` | 메뉴 이동 / 페이지 접근 | `/data/query`, `/files` |
  | `button_click` | 주요 버튼 클릭 | "Athena 실행", "MLFlow 열기", "Jupyter 접속" |
  | `query_execute` | Athena/로컬 DB 쿼리 실행 | SQL 앞 100자 |
  | `download` | S3 파일 다운로드 | 파일 키, 사유 |
- **화면 기능**: 날짜 범위 필터, 사용자명 필터, 이벤트 유형 필터, 목록 조회

### 1-2. S3 다운로드 사유 기록
- **트리거**: S3 스토리지 화면에서 다운로드 버튼 클릭
- **팝업 내용**:
  - 파일명 표시
  - 다운로드 사유 텍스트 입력 (최소 10자)
  - 확인 / 취소 버튼
- **저장**: `audit_log` 테이블에 `download` 이벤트 + 사유 기록
- **취소 시**: 다운로드 중단

---

## 2. 기술 설계 방향

### 2-1. 감사 로그 데이터 모델
```
AuditLog (신규 테이블)
├── id: int PK autoincrement
├── username: str           # 행위자 (미로그인은 'anonymous')
├── event_type: str         # 'login' | 'logout' | 'page_view' | 'button_click' | 'query_execute' | 'download'
├── target: str nullable    # 대상 (페이지 경로, 버튼명, 파일키)
├── detail: text nullable   # 상세 (SQL, 다운로드 사유 등)
├── ip_address: str nullable
├── user_agent: str nullable
└── created_at: datetime
```

### 2-2. 로깅 방식 (Hybrid)

| 이벤트 | 방식 | 근거 |
|--------|------|------|
| login/logout | **Backend** (FastAPI route) | 서버 검증 필수, 위변조 불가 |
| query_execute | **Backend** (API route) | 이미 API 호출 시점에 처리 가능 |
| download | **Backend** (API route + 사유 포함) | 사유 저장, 서버 검증 필요 |
| page_view | **Frontend → API** (페이지 로드 시 비동기 POST) | 백엔드 API 없는 화면 이동 추적 |
| button_click | **Frontend → API** (클릭 시 비동기 POST, fire-and-forget) | UI 이벤트는 프론트에서 감지 |

> **Fire-and-forget 원칙**: 감사 로그 실패가 정상 기능을 막으면 안 됨.
> 모든 로그 API 호출은 오류가 나도 무시하고 진행.

### 2-3. API 설계
```
POST /api/audit/log
  body: { event_type, target?, detail? }
  → 현재 로그인 유저 + IP 자동 추출
  → fire-and-forget (항상 200 반환)

GET /api/admin/audit-log
  query: ?username=&event_type=&from=&to=&limit=100
  → admin only
  → 목록 반환 (최신순)
```

### 2-4. S3 다운로드 플로우 변경

**현재**: 다운로드 버튼 → `GET /api/s3/download?key=xxx` → presigned URL → `window.open()`

**변경 후**:
```
다운로드 버튼 클릭
  → 팝업 (사유 입력, 최소 10자)
  → 확인 클릭
  → POST /api/s3/download
       body: { key, reason }
    → DB에 audit_log 저장 (event_type='download', detail=reason)
    → presigned URL 반환
  → window.open(presigned_url)
```

S3 다운로드 API를 GET → POST로 변경하고 `reason` 필드 추가.

### 2-5. 접속기록 페이지 기능
- 날짜 범위 picker (오늘/7일/30일/직접입력)
- 사용자명 드롭다운 필터
- 이벤트 유형 탭 또는 드롭다운
- 테이블 컬럼: 일시, 사용자, 이벤트, 대상, 상세, IP
- 페이지네이션 (100건 단위)

---

## 3. 구현 범위

### Phase A: 백엔드 (Day 1)
- [ ] `AuditLog` 모델 생성 (`app/models/audit_log.py`)
- [ ] Alembic 마이그레이션
- [ ] `AuditLogRepository` CRUD (`app/repositories/audit_log_repo.py`)
- [ ] `AuditLogService` (`app/services/audit_log_service.py`)
- [ ] `POST /api/audit/log` 엔드포인트 (로그인 불필요, Bearer 있으면 유저명 추출)
- [ ] `GET /api/admin/audit-log` 엔드포인트 (admin only, 필터 파라미터)
- [ ] auth.py 로그인/로그아웃 이벤트 기록 추가
- [ ] S3 다운로드 API: GET → POST 변경, reason 필드 추가, audit_log 저장

### Phase B: 프론트엔드 - 공통 JS (Day 2)
- [ ] `app/static/js/app.js`에 `logEvent(event_type, target, detail)` 추가
  - fire-and-forget: `apiFetch('/api/audit/log', {method:'POST', ...}).catch(()=>{})`
- [ ] `DOMContentLoaded`에 `page_view` 자동 기록 (현재 pathname)
- [ ] 주요 버튼 클릭 시 `logEvent('button_click', ...)` 추가:
  - Athena 실행, Jupyter 접속, MLFlow 열기, Airflow 열기, S3 새로고침

### Phase C: S3 다운로드 팝업 (Day 2)
- [ ] `files.html` 다운로드 버튼 → `requestDownload(key, filename)` 함수로 변경
- [ ] 사유 입력 모달 HTML/CSS 추가
- [ ] 사유 유효성 검증 (10자 미만 → 확인 버튼 비활성화)
- [ ] 확인 후 `POST /api/s3/download` 호출

### Phase D: 접속기록 관리 페이지 (Day 3)
- [ ] `app/templates/pages/admin_audit_log.html` 생성
- [ ] `app/api/routes/web.py`에 `/admin/audit-log` 웹 라우트 추가
- [ ] `base.html` 사이드바에 "접속기록" 메뉴 추가 (Users와 Settings 사이)

---

## 4. 변경 파일 목록

```
신규:
  app/models/audit_log.py
  app/repositories/audit_log_repo.py
  app/services/audit_log_service.py
  app/api/routes/audit.py
  app/templates/pages/admin_audit_log.html
  alembic/versions/xxxx_add_audit_log.py

수정:
  app/api/routes/auth.py        (login/logout 이벤트 기록)
  app/api/routes/s3_storage.py  (download GET→POST, reason 파라미터)
  app/api/routes/admin.py       (GET /admin/audit-log 추가)
  app/api/router.py             (audit 라우터 등록)
  app/api/routes/web.py         (접속기록 웹 라우트)
  app/static/js/app.js          (logEvent() 공통 함수, page_view 자동기록)
  app/templates/base.html       (접속기록 사이드바 메뉴)
  app/templates/pages/files.html (다운로드 팝업 + POST 방식 변경)
```

---

## 5. 위험 요소 및 대응

| 위험 | 대응 |
|------|------|
| 로그 폭주로 DB 부하 | page_view는 페이지당 1회, button_click은 주요 버튼만 선별 기록 |
| 감사 로그 실패가 정상 기능 차단 | 모든 log API 호출은 try/catch + fire-and-forget |
| S3 download API 변경 (GET→POST) | 기존 GET 엔드포인트 유지 or 버전 분기 (폴백 없음, 현재 내부 사용만) |
| 대용량 로그 조회 성능 | `created_at` 인덱스 + 100건 페이지네이션 |
| IP 주소 수집 (개인정보) | 내부 포털 전용 + 관리자만 조회 가능 |
