# Feature Design: platform-access-control

> Plan 참조: `docs/01-plan/features/platform-access-control.plan.md`

---

## 1. 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (Portal UI)                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  DOMContentLoaded → GET /api/auth/me/permissions         │   │
│  │  → myPermissions = ['s3','athena','mlflow',...]          │   │
│  │  → 권한 없는 버튼 disabled / 콘텐츠 숨김                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ JWT Bearer
┌──────────────────────────▼──────────────────────────────────────┐
│  FastAPI Backend                                                 │
│  ┌────────────────────┐  ┌────────────────────────────────┐     │
│  │ /api/auth/me/perms │  │ /api/admin/users/{id}/perms    │     │
│  │ (현재 유저 권한)   │  │ (admin: 권한 조회/설정)        │     │
│  └────────────────────┘  └────────────────────────────────┘     │
│  ┌────────────────────┐  ┌────────────────────────────────┐     │
│  │ /api/mlflow/sso    │  │ /api/airflow/sso               │     │
│  │ (MLFlow 자동로그인)│  │ (Airflow 자동로그인)           │     │
│  └───────┬────────────┘  └─────────────┬──────────────────┘     │
│          │ httpx POST (서버→MLFlow)    │ httpx POST (서버→AF)   │
└──────────┼─────────────────────────────┼────────────────────────┘
           ▼                             ▼
   mlflow.mlops.click            airflow.mlops.click
   (HTTP Basic Auth plugin)      (FAB login)
```

---

## 2. 데이터 모델

### 2-1. `UserFeaturePermission` (신규 테이블)

**파일**: `app/models/user_permission.py`

```python
class UserFeaturePermission(Base):
    __tablename__ = "user_feature_permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    feature: Mapped[str] = mapped_column(String(50), nullable=False)
    # feature 값: 's3' | 'athena' | 'jupyter' | 'mlflow' | 'airflow'
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "feature", name="uq_user_feature"),)
```

### 2-2. 권한 판단 규칙

```
유저 role == 'admin'  → 모든 feature 자동 허용 (DB 조회 불필요)
유저 role == 'user'   → user_feature_permissions 테이블에 레코드 있을 때만 허용
```

### 2-3. Alembic 마이그레이션

**파일**: `alembic/versions/xxxx_add_user_feature_permissions.py`

```python
def upgrade():
    op.create_table(
        "user_feature_permissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature", sa.String(50), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "feature", name="uq_user_feature"),
    )
    op.create_index("ix_user_feature_user_id", "user_feature_permissions", ["user_id"])
```

---

## 3. Backend 설계

### 3-1. Repository

**파일**: `app/repositories/user_permission_repo.py`

```python
VALID_FEATURES = frozenset({"s3", "athena", "jupyter", "mlflow", "airflow"})

class UserPermissionRepository:
    def __init__(self, db: Session): ...

    def get_by_user(self, user_id: int) -> list[str]:
        """유저의 허용된 feature 목록 반환"""

    def set_permissions(self, user_id: int, features: list[str]) -> list[str]:
        """기존 권한 전체 삭제 후 새 목록으로 교체 (atomic)"""
        # 트랜잭션: DELETE WHERE user_id=? → INSERT 각 feature
```

### 3-2. API 엔드포인트

#### A. `GET /api/auth/me/permissions`

**파일**: `app/api/routes/auth.py` (추가)

```python
@router.get("/me/permissions", response_model=list[str])
def my_permissions(
    current_user: UserRead = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "admin":
        return list(VALID_FEATURES)  # admin은 전체 반환
    repo = UserPermissionRepository(db)
    return repo.get_by_user(current_user.id)
```

응답 예시:
```json
["s3", "athena", "mlflow"]
```

#### B. `GET /api/admin/users/{user_id}/permissions`

**파일**: `app/api/routes/admin.py` (추가)

```python
@router.get("/users/{user_id}/permissions", response_model=list[str])
def get_user_permissions(user_id: int, ...):
    # admin only, 해당 유저 권한 목록 반환
```

#### C. `PUT /api/admin/users/{user_id}/permissions`

```python
class PermissionUpdate(BaseModel):
    features: list[str]  # 허용할 feature 목록 (전체 교체)

@router.put("/users/{user_id}/permissions", response_model=list[str])
def set_user_permissions(user_id: int, body: PermissionUpdate, ...):
    # 유효성 검증: VALID_FEATURES 에 없는 값 거부
    # set_permissions() 호출 (atomic 교체)
```

#### D. `GET /api/airflow/health`

**파일**: `app/api/routes/airflow.py` (신규)

```python
router = APIRouter(prefix="/airflow", tags=["airflow"])

@router.get("/health")
async def airflow_health():
    svc = AirflowService()
    healthy = await svc.check_health()
    return {"status": "ok" if healthy else "unavailable", "url": svc.get_ui_url()}
```

### 3-3. FastAPI Permission Dependency

**파일**: `app/api/deps.py` (추가)

```python
def require_feature(feature: str):
    """기능별 권한 체크 Depends 팩토리"""
    def _check(
        current_user: UserRead = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> UserRead:
        if current_user.role == "admin":
            return current_user
        repo = UserPermissionRepository(db)
        if feature not in repo.get_by_user(current_user.id):
            raise HTTPException(status_code=403, detail=f"'{feature}' 기능 접근 권한이 없습니다.")
        return current_user
    return _check
```

사용 예:
```python
# athena execute endpoint
@router.post("/athena/execute")
def execute_athena_query(
    user: UserRead = Depends(require_feature("athena")),
    ...
):
```

---

## 4. MLFlow 자동 로그인 (SSO) 설계

### 4-1. 메커니즘

MLFlow 2.x `basic-auth` 플러그인의 로그인 엔드포인트 활용:
```
POST /ajax-api/2.0/mlflow/users/login
Content-Type: application/x-www-form-urlencoded
Body: username=admin&password=Clkyobo11111!

Response:
  Set-Cookie: session=<session_token>; HttpOnly; Path=/
  200 OK
```

백엔드가 이 세션 쿠키를 취득한 후 브라우저에 전달:

```
Browser → GET /api/mlflow/sso
  → Backend: POST mlflow/users/login (httpx)
  → Extract Set-Cookie
  → Response: 302 Location: http://mlflow.mlops.click
              Set-Cookie: session=<token>; Domain=mlflow.mlops.click
```

### 4-2. `MlflowService.get_sso_url()` 설계

**파일**: `app/services/mlflow_service.py`

```python
async def get_session_cookie(self) -> str | None:
    """MLFlow 로그인 후 세션 쿠키값 반환. 실패 시 None."""
    settings = get_settings()
    username = settings.mlflow_username   # "admin"
    password = settings.mlflow_password   # "Clkyobo11111!" (Secret)
    login_url = f"{self.base_url}/ajax-api/2.0/mlflow/users/login"
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.post(
                login_url,
                data={"username": username, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.cookies.get("session")
    except Exception as e:
        logger.warning("MLFlow SSO login failed: %s", e)
    return None
```

### 4-3. SSO 엔드포인트

**파일**: `app/api/routes/mlflow_proxy.py`

```python
@router.get("/sso")
async def mlflow_sso(
    user: UserRead = Depends(require_feature("mlflow")),
):
    """MLFlow 자동 로그인 → 세션 쿠키 포함 Redirect"""
    svc = MlflowService()
    session_cookie = await svc.get_session_cookie()

    target_url = svc.get_ui_url()
    response = RedirectResponse(url=target_url, status_code=302)

    if session_cookie:
        # MLFlow 도메인으로 쿠키 설정
        from urllib.parse import urlparse
        domain = urlparse(target_url).hostname
        response.set_cookie(
            key="session",
            value=session_cookie,
            domain=domain,
            httponly=True,
            samesite="lax",
        )
    return response
```

### 4-4. 폴백 처리

- SSO 쿠키 취득 실패 시 → 쿠키 없이 단순 Redirect (브라우저가 Basic Auth 다이얼로그 표시)
- MLFlow가 Basic Auth 플러그인 미사용 시 → `settings.mlflow_username/password`를 기반으로 URL 임베드 폴백

### 4-5. 인증 정보 저장 위치

**`k8s/backend-secret.yaml`**에 추가 (환경변수):
```yaml
MLFLOW_USERNAME: "admin"
MLFLOW_PASSWORD: "Clkyobo11111!"
```

**`app/core/config.py`** 추가:
```python
mlflow_username: str = Field(default="admin", alias="MLFLOW_USERNAME")
mlflow_password: SecretStr = Field(default="", alias="MLFLOW_PASSWORD")
```

---

## 5. Airflow 신규 메뉴 설계

### 5-1. 설정값 (system_settings seed 추가)

```python
# app/models/system_settings.py SETTINGS_SEED 추가
{
    "key": "AIRFLOW_BASE_URL",
    "value": "https://airflow.mlops.click",
    "label": "Airflow 접속 URL",
    "group": "airflow",
},
{
    "key": "AIRFLOW_USERNAME",
    "value": "admin",
    "label": "Airflow 로그인 계정",
    "group": "airflow",
},
{
    "key": "AIRFLOW_PASSWORD",
    "value": "admin",
    "label": "Airflow 로그인 비밀번호",
    "group": "airflow",
},
```

### 5-2. `AirflowService`

**파일**: `app/services/airflow_service.py`

```python
class AirflowService:
    def __init__(self, db: Session | None = None):
        settings = get_settings()
        if db:
            svc = SettingsService(db)
            self.base_url = svc.get("AIRFLOW_BASE_URL", settings.airflow_base_url)
            self.username = svc.get("AIRFLOW_USERNAME", "")
            self.password = svc.get("AIRFLOW_PASSWORD", "")
        else:
            self.base_url = settings.airflow_base_url
            self.username = ""
            self.password = ""

    async def check_health(self) -> bool: ...
    async def get_session_cookie(self) -> str | None:
        # Airflow FAB login: POST /login → form: username, password, _token
        # Step1: GET /login → extract CSRF _token
        # Step2: POST /login with credentials + _token
        # Step3: return session cookie
        ...
```

### 5-3. SSO 차이점 (Airflow vs MLFlow)

Airflow FAB 로그인은 CSRF 토큰 필요:
```
1. GET {airflow}/login
   → Parse HTML: <input name="_token" value="xxxxx">
2. POST {airflow}/login
   Body: username=...&password=...&_token=xxxxx
   → Set-Cookie: session=...
```

구현 시 `BeautifulSoup` 또는 정규식으로 토큰 파싱.

### 5-4. Airflow 라우트 등록

**`app/api/router.py`**: `from app.api.routes import airflow as airflow_router` 추가
**`app/api/routes/web.py`**: `/airflow` 페이지 라우트 추가

### 5-5. 사이드바 메뉴 추가

**`app/templates/base.html`**의 Models 그룹에 추가:
```html
<a href="/airflow" class="sidebar-subitem {% if active_page=='airflow' %}active{% endif %}">
  <span class="s-icon">🌀</span><span class="s-label">Airflow</span>
</a>
```

---

## 6. 관리자 권한 UI 설계

### 6-1. 사용자 목록 테이블 변경

**`admin_users.html`** 테이블 헤더에 "권한" 컬럼 추가:
```html
<th style="width:200px;">기능 권한</th>
```

각 행에 권한 뱃지 표시:
```html
<!-- 예시: S3, Athena 권한 있는 경우 -->
<td>
  <span class="perm-badge active">S3</span>
  <span class="perm-badge active">Athena</span>
  <span class="perm-badge">Jupyter</span>
  <span class="perm-badge">MLFlow</span>
  <span class="perm-badge">Airflow</span>
</td>
```

```css
.perm-badge {
  font-size: 10px; padding: 1px 6px; border-radius: 99px;
  background: var(--border); color: var(--text-muted);
  margin: 1px; display: inline-block;
}
.perm-badge.active {
  background: #dbeafe; color: #1d4ed8;
}
```

### 6-2. 권한 편집 모달

기존 사용자 편집 모달에 체크박스 섹션 추가:
```html
<div class="form-group">
  <label class="form-label">기능 권한</label>
  <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:4px;">
    <label class="perm-toggle"><input type="checkbox" name="perm" value="s3"> S3 스토리지</label>
    <label class="perm-toggle"><input type="checkbox" name="perm" value="athena"> Athena DB</label>
    <label class="perm-toggle"><input type="checkbox" name="perm" value="jupyter"> Jupyter</label>
    <label class="perm-toggle"><input type="checkbox" name="perm" value="mlflow"> MLFlow</label>
    <label class="perm-toggle"><input type="checkbox" name="perm" value="airflow"> Airflow</label>
  </div>
  <div style="font-size:11px; color:var(--text-muted); margin-top:4px;">
    * admin 계정은 모든 기능 자동 허용
  </div>
</div>
```

### 6-3. JS 플로우

```javascript
async function openEditModal(userId) {
  // 1. 유저 정보 로드 (기존)
  // 2. 권한 목록 로드 (신규)
  const permRes = await apiFetch(`/api/admin/users/${userId}/permissions`);
  const perms = await permRes.json();  // ["s3", "athena"]
  // 3. 체크박스 상태 설정
  document.querySelectorAll('[name="perm"]').forEach(cb => {
    cb.checked = perms.includes(cb.value);
  });
}

async function saveUser(userId) {
  // 기존 저장 로직 + 권한 저장
  const features = [...document.querySelectorAll('[name="perm"]:checked')]
    .map(cb => cb.value);
  await apiFetch(`/api/admin/users/${userId}/permissions`, {
    method: 'PUT',
    body: JSON.stringify({ features }),
  });
}
```

---

## 7. 페이지별 권한 제어 설계

### 7-1. 공통 권한 로드 (base.html or app.js)

**`app/static/js/app.js`** 또는 **`base.html`** `<script>` 블록에 추가:

```javascript
// 전역 권한 캐시
window._myPermissions = null;

async function loadMyPermissions() {
  if (window._myPermissions !== null) return window._myPermissions;
  try {
    const res = await apiFetch('/api/auth/me/permissions');
    if (res && res.ok) {
      window._myPermissions = await res.json();
    } else {
      window._myPermissions = [];
    }
  } catch {
    window._myPermissions = [];
  }
  return window._myPermissions;
}

function hasPermission(feature) {
  return (window._myPermissions || []).includes(feature);
}
```

### 7-2. 각 페이지 권한 제어 상세

#### Athena DB (`query.html`)
```javascript
// DOMContentLoaded 이후
const perms = await loadMyPermissions();
if (!perms.includes('athena')) {
  document.getElementById('athena-sql').disabled = true;
  document.querySelector('button[onclick="runAthenaQuery()"]').disabled = true;
  document.querySelector('button[onclick="runAthenaQuery()"]').title = 'Athena 접근 권한이 없습니다';
  document.getElementById('athena-status').innerHTML =
    '<span style="color:#ef4444;">⛔ Athena DB 접근 권한이 없습니다. 관리자에게 문의하세요.</span>';
}
```

#### Jupyter (`jupyter.html`)
```javascript
const perms = await loadMyPermissions();
if (!perms.includes('jupyter')) {
  document.querySelectorAll('.btn-connect').forEach(btn => {
    btn.disabled = true;
    btn.textContent = '🔒 권한 없음';
    btn.title = 'Jupyter 접근 권한이 없습니다';
  });
}
```

#### MLFlow (`mlflow.html`)
```javascript
const perms = await loadMyPermissions();
const btn = document.getElementById('btn-open');
if (!perms.includes('mlflow')) {
  btn.disabled = true;
  btn.textContent = '🔒 MLFlow 권한 없음';
}
// 열기 버튼 → SSO 엔드포인트로 변경
function openMlflow() {
  window.location.href = '/api/mlflow/sso';  // 브라우저가 따라감
}
```

#### S3 스토리지 (`files.html`)
```javascript
const perms = await loadMyPermissions();
if (!perms.includes('s3')) {
  // 파일 목록 숨기고 안내 표시
  document.getElementById('file-list').innerHTML =
    '<tr><td colspan="5" style="text-align:center; padding:60px; color:#ef4444;">' +
    '⛔ S3 스토리지 접근 권한이 없습니다.</td></tr>';
  // 트리도 비활성화
  document.getElementById('folder-tree').style.pointerEvents = 'none';
  document.getElementById('folder-tree').style.opacity = '0.4';
  // 다운로드 버튼 렌더링 시 제거 (loadFiles 함수에 권한 체크 추가)
}
```

#### Airflow (`airflow.html`)
```javascript
const perms = await loadMyPermissions();
const btn = document.getElementById('btn-open-airflow');
if (!perms.includes('airflow')) {
  btn.disabled = true;
  btn.textContent = '🔒 Airflow 권한 없음';
}
```

---

## 8. Airflow 페이지 레이아웃

**파일**: `app/templates/pages/airflow.html`

MLFlow 페이지와 동일한 구조:
```html
{% extends "base.html" %}
{% block title %}Airflow - MLFoundry{% endblock %}

{% block content %}
<div class="card" style="text-align:center; padding:48px 24px;">
  <div style="font-size:48px; margin-bottom:16px;">🌀</div>
  <div style="font-size:18px; font-weight:700; margin-bottom:8px;">Airflow 워크플로우 관리</div>
  <div style="font-size:13px; color:var(--text-muted); margin-bottom:28px;" id="airflow-url-text">
    연결 중...
  </div>
  <button id="btn-open-airflow" class="btn btn-primary" style="font-size:15px; padding:12px 32px;"
    onclick="openAirflow()">
    🚀 Airflow 열기
  </button>
  <div style="margin-top:20px;">
    <span id="health-badge" style="font-size:12px; color:var(--text-muted);">상태 확인 중...</span>
  </div>
</div>
<div class="card" style="margin-top:0;">
  <div class="card-title" style="font-size:13px; margin-bottom:8px;">💡 사용 안내</div>
  <ul style="font-size:13px; color:var(--text-secondary); line-height:1.8; margin:0; padding-left:20px;">
    <li>버튼 클릭 시 Airflow UI가 <strong>새 탭</strong>으로 열립니다.</li>
    <li>DAG 목록 확인, 스케줄 관리, 실행 이력을 조회합니다.</li>
  </ul>
</div>
{% endblock %}
```

---

## 9. 구현 순서 (Implementation Order)

```
Day 1: Permission 백엔드
  1. app/models/user_permission.py 생성
  2. alembic revision 생성 및 마이그레이션
  3. app/repositories/user_permission_repo.py 생성
  4. app/api/routes/auth.py → me/permissions 추가
  5. app/api/routes/admin.py → users/{id}/permissions CRUD 추가
  6. app/api/deps.py → require_feature() 팩토리 추가

Day 2: MLFlow SSO
  7. app/core/config.py → mlflow_username, mlflow_password 추가
  8. k8s/backend-secret.yaml → MLFLOW_USERNAME, MLFLOW_PASSWORD 추가
  9. app/services/mlflow_service.py → get_session_cookie() 추가
  10. app/api/routes/mlflow_proxy.py → /sso 엔드포인트 추가
  11. app/templates/pages/mlflow.html → openMlflow() SSO 방식으로 변경

Day 3: Airflow 신규 메뉴
  12. app/models/system_settings.py → AIRFLOW_* seed 추가
  13. app/services/airflow_service.py 생성
  14. app/api/routes/airflow.py 생성
  15. app/api/router.py → airflow 라우터 등록
  16. app/api/routes/web.py → /airflow 웹 라우트 추가
  17. app/templates/pages/airflow.html 생성
  18. app/templates/base.html → Airflow 사이드바 메뉴 추가

Day 4: 관리자 권한 UI
  19. app/templates/pages/admin_users.html → 권한 컬럼 + 모달 체크박스 추가

Day 5: 각 페이지 권한 제어
  20. app/static/js/app.js → loadMyPermissions(), hasPermission() 추가
  21. query.html → Athena 권한 제어
  22. jupyter.html → 접속 버튼 권한 제어
  23. mlflow.html → MLFlow 열기 버튼 권한 제어
  24. files.html → S3 파일 목록·다운로드 권한 제어
  25. airflow.html → Airflow 열기 버튼 권한 제어
```

---

## 10. 변경 파일 전체 목록

### 신규 생성 (6개)
| 파일 | 설명 |
|------|------|
| `app/models/user_permission.py` | UserFeaturePermission 모델 |
| `app/repositories/user_permission_repo.py` | Permission CRUD |
| `app/services/airflow_service.py` | Airflow SSO + health |
| `app/api/routes/airflow.py` | Airflow API 라우터 |
| `app/templates/pages/airflow.html` | Airflow 페이지 |
| `alembic/versions/xxxx_add_user_feature_permissions.py` | DB 마이그레이션 |

### 수정 (11개)
| 파일 | 변경 내용 |
|------|----------|
| `app/core/config.py` | mlflow_username, mlflow_password, airflow_base_url 추가 |
| `app/api/deps.py` | require_feature() 팩토리 추가 |
| `app/api/routes/auth.py` | GET /me/permissions 추가 |
| `app/api/routes/admin.py` | GET/PUT /users/{id}/permissions 추가 |
| `app/api/routes/mlflow_proxy.py` | GET /sso 추가 |
| `app/api/router.py` | airflow 라우터 등록 |
| `app/api/routes/web.py` | /airflow 웹 라우트 추가 |
| `app/services/mlflow_service.py` | get_session_cookie() 추가 |
| `app/models/system_settings.py` | AIRFLOW_* seed 추가 |
| `app/templates/base.html` | Airflow 사이드바 + loadMyPermissions() JS |
| `app/templates/pages/admin_users.html` | 권한 뱃지 컬럼 + 편집 모달 체크박스 |
| `app/templates/pages/query.html` | Athena 권한 제어 |
| `app/templates/pages/jupyter.html` | 접속 버튼 권한 제어 |
| `app/templates/pages/mlflow.html` | SSO 방식 + 버튼 권한 제어 |
| `app/templates/pages/files.html` | S3 파일 목록·다운로드 권한 제어 |
| `k8s/backend-secret.yaml` | MLFLOW_USERNAME, MLFLOW_PASSWORD 추가 |

---

## 11. 보안 고려사항

| 항목 | 처리 방법 |
|------|----------|
| MLFlow/Airflow 비밀번호 저장 | k8s Secret (envFrom secretRef) |
| SSO 세션 쿠키 도메인 | 해당 서비스 도메인에만 Set-Cookie |
| 권한 API 호출 빈도 | 페이지 로드 시 1회 + 세션 캐시 (`window._myPermissions`) |
| API 레벨 권한 체크 | `require_feature()` Depends로 서버 검증 (UI 우회 방어) |
| admin 계정 자동 권한 | DB 조회 없이 코드 레벨에서 허용 처리 |
