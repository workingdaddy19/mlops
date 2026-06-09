# UI 전면 개편 설계 문서

> Plan 문서 참조: [ui-redesign.plan.md](../../01-plan/features/ui-redesign.plan.md)

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | UI 메뉴구조 및 화면 스타일 전면 개편 |
| **설계일** | 2026-04-28 |
| **기술 스택** | FastAPI + Jinja2 + Vanilla JS (Streamlit 제거) |
| **참조 스크린샷** | ai-ready-poc (상단 탭 + 좌측 서브메뉴 + teal 컬러) |

### Value Delivered

| 관점 | 내용 |
|------|------|
| **Problem** | Streamlit 단순 라디오 버튼 메뉴 — 계층 구조 없음, 전문 포털 UX 미달 |
| **Solution** | FastAPI Jinja2 HTML로 전환, 상단 탭 + 좌측 서브메뉴 레이아웃 완전 구현 |
| **Function UX Effect** | 탭 전환 + 서브메뉴 + 브레드크럼 + JWT localStorage 인증 일관된 SPA 경험 |
| **Core Value** | 스크린샷 참조와 동일한 teal 전문 포털 완성도, 단일 FastAPI 포트(6080)로 통합 |

---

## 1. 전체 아키텍처

### 1.1 변경 전후 비교

| 구분 | Before (Streamlit) | After (FastAPI + Jinja2) |
|------|-------------------|--------------------------|
| 서빙 방식 | Streamlit :6501 (별도 프로세스) | FastAPI :6080 (통합) |
| UI 엔진 | Python 컴포넌트 렌더링 | Jinja2 HTML 템플릿 |
| 라우팅 | st.radio 라디오 버튼 | URL 기반 (탭/서브메뉴) |
| 인증 | st.session_state | JWT localStorage + fetch Bearer |
| 스타일 | Streamlit 기본 + CSS 핵 | 커스텀 CSS (teal 색상 토큰) |

### 1.2 요청 흐름

```
브라우저
  │
  ├── GET /login             → login.html (레이아웃 없음)
  ├── POST /api/auth/login   → JSON {access_token}  → localStorage
  │
  └── GET /data/query        → base.html + query.html
      GET /data/datasets     → base.html + datasets.html
      GET /aiml/jupyter      → base.html + jupyter.html
      GET /aiml/mlflow       → base.html + mlflow.html
      GET /board             → base.html + board.html
      GET /files             → base.html + files.html
      │
      └── fetch() /api/*     → FastAPI REST (Authorization: Bearer <token>)
```

### 1.3 파일 구조

```
app/
├── templates/
│   ├── base.html                   # 상단바 + 사이드바 레이아웃 쉘
│   ├── login.html                  # 독립 로그인 페이지
│   └── pages/
│       ├── query.html              # Data > EDA Query
│       ├── datasets.html           # Data > 데이터셋
│       ├── jupyter.html            # AI ML > JupyterLab
│       ├── mlflow.html             # AI ML > MLflow
│       ├── board.html              # 게시판
│       └── files.html              # 파일 관리
├── static/
│   ├── css/
│   │   └── main.css               # 색상 토큰 + 레이아웃 + 컴포넌트
│   └── js/
│       └── app.js                 # 인증 + 탭 전환 + API 헬퍼
└── api/
    └── routes/
        └── web.py                 # Jinja2 HTML 라우트 (신규)
```

---

## 2. CSS 설계

### 2.1 색상 토큰 (`main.css`)

```css
:root {
  /* Primary */
  --primary:          #0d9488;   /* teal-600 — 탭 활성, 버튼 */
  --primary-hover:    #0f766e;   /* teal-700 — hover */
  --primary-light:    #f0fdfa;   /* teal-50  — 활성 배경 */

  /* Layout backgrounds */
  --bg-nav:           #ffffff;
  --bg-sidebar:       #f8fafc;
  --bg-content:       #ffffff;

  /* Borders */
  --border:           #e2e8f0;

  /* Text */
  --text-primary:     #0f172a;
  --text-secondary:   #64748b;
  --text-muted:       #94a3b8;

  /* Sidebar active */
  --sidebar-active:    var(--primary);
  --sidebar-active-bg: var(--primary-light);

  /* Sizes */
  --nav-height:        60px;
  --sidebar-width:     240px;
}
```

### 2.2 레이아웃 구조

```css
/* 최상위 구조 */
body {
  margin: 0;
  font-family: 'Pretendard', -apple-system, sans-serif;
  background: var(--bg-content);
}

/* 상단바 60px 고정 */
.navbar {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: var(--nav-height);
  background: var(--bg-nav);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 24px;
  z-index: 100;
  gap: 0;
}

/* 좌측 사이드바 240px 고정 */
.sidebar {
  position: fixed;
  top: var(--nav-height);
  left: 0;
  bottom: 0;
  width: var(--sidebar-width);
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  z-index: 50;
}

/* 메인 콘텐츠 영역 */
.main-content {
  margin-top: var(--nav-height);
  margin-left: var(--sidebar-width);
  padding: 24px;
  min-height: calc(100vh - var(--nav-height));
}
```

### 2.3 상단 네비게이션 바 세부

```
┌─────────────────────────────────────────────────────────────────┐
│ [F] MLFoundry   [Data] [AI ML] [게시판] [파일관리]   Admin admin [로그아웃] │
└─────────────────────────────────────────────────────────────────┘
  └─ brand (좌)    └─ tabs (중앙, flex-grow:1)          └─ user (우)
```

- **brand**: `[F]` 아이콘(teal 배경 흰글자) + `MLFoundry` 텍스트, min-width 200px
- **tabs**: `<a>` 태그 목록, 활성 탭 = teal 하단 밑줄 2px + teal 텍스트
- **user**: username + role 텍스트 + `[로그아웃]` 버튼

```css
.nav-tabs { display: flex; gap: 4px; flex: 1; justify-content: center; }
.nav-tab {
  padding: 6px 16px;
  text-decoration: none;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  font-size: 14px;
  font-weight: 500;
  transition: color 0.15s, border-color 0.15s;
}
.nav-tab.active, .nav-tab:hover {
  color: var(--primary);
  border-bottom-color: var(--primary);
}
```

### 2.4 좌측 사이드바 세부

```
┌──────────────────┐
│ ▸ DATA           │  ← 섹션 제목 (현재 탭명)
│                  │
│  📊 EDA Query    │  ← 서브메뉴 항목 (활성: teal bg)
│  📋 데이터셋      │
└──────────────────┘
```

```css
.sidebar-section-title {
  padding: 16px 16px 8px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  border-radius: 6px;
  margin: 2px 8px;
  transition: background 0.15s, color 0.15s;
}
.sidebar-item:hover { background: var(--border); color: var(--text-primary); }
.sidebar-item.active {
  background: var(--sidebar-active-bg);
  color: var(--sidebar-active);
  font-weight: 500;
}

.sidebar-item .icon { font-size: 16px; width: 20px; text-align: center; }
```

---

## 3. HTML 템플릿 설계

### 3.1 `base.html` — 레이아웃 쉘

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}MLFoundry{% endblock %}</title>
  <link rel="stylesheet" href="/static/css/main.css">
</head>
<body data-tab="{{ active_tab }}" data-page="{{ active_page }}">

<!-- 상단 네비게이션 바 -->
<nav class="navbar">
  <div class="nav-brand">
    <span class="brand-icon">F</span>
    <span class="brand-text">MLFoundry</span>
  </div>
  <div class="nav-tabs">
    <a href="/data/query"  class="nav-tab {% if active_tab=='data'  %}active{% endif %}">Data</a>
    <a href="/aiml/jupyter" class="nav-tab {% if active_tab=='aiml'  %}active{% endif %}">AI ML</a>
    <a href="/board"        class="nav-tab {% if active_tab=='board' %}active{% endif %}">게시판</a>
    <a href="/files"        class="nav-tab {% if active_tab=='files' %}active{% endif %}">파일 관리</a>
  </div>
  <div class="nav-user">
    <span id="nav-username">로딩 중...</span>
    <button class="btn-logout" onclick="logout()">로그아웃</button>
  </div>
</nav>

<!-- 좌측 사이드바 (탭별 분기) -->
<aside class="sidebar">
  {% if active_tab == 'data' %}
    <div class="sidebar-section-title">DATA</div>
    <a href="/data/query"    class="sidebar-item {% if active_page=='query'    %}active{% endif %}">
      <span class="icon">📊</span> EDA Query
    </a>
    <a href="/data/datasets" class="sidebar-item {% if active_page=='datasets' %}active{% endif %}">
      <span class="icon">📋</span> 데이터셋
    </a>
  {% elif active_tab == 'aiml' %}
    <div class="sidebar-section-title">AI ML</div>
    <a href="/aiml/jupyter" class="sidebar-item {% if active_page=='jupyter' %}active{% endif %}">
      <span class="icon">📓</span> ML Analysis
    </a>
    <a href="/aiml/mlflow"  class="sidebar-item {% if active_page=='mlflow'  %}active{% endif %}">
      <span class="icon">📈</span> MLflow 실험
    </a>
  {% elif active_tab == 'board' %}
    <div class="sidebar-section-title">게시판</div>
    <a href="/board"        class="sidebar-item {% if active_page=='board'   %}active{% endif %}">
      <span class="icon">📢</span> 공지사항/자료실
    </a>
  {% elif active_tab == 'files' %}
    <div class="sidebar-section-title">파일 관리</div>
    <a href="/files"        class="sidebar-item {% if active_page=='files'   %}active{% endif %}">
      <span class="icon">📁</span> 업로드/다운로드
    </a>
  {% endif %}
</aside>

<!-- 메인 콘텐츠 -->
<main class="main-content">
  <!-- 브레드크럼 -->
  <div class="breadcrumb">
    {% block breadcrumb %}{% endblock %}
  </div>

  <!-- 페이지 콘텐츠 -->
  <div class="page-content">
    {% block content %}{% endblock %}
  </div>
</main>

<script src="/static/js/app.js"></script>
{% block scripts %}{% endblock %}
</body>
</html>
```

### 3.2 `login.html` — 독립 로그인 페이지

레이아웃 쉘 없이 중앙 정렬 카드 형태.

```
┌────────────────────────────────┐
│                                │
│   [F] MLFoundry                │
│                                │
│   ┌────────────────────────┐   │
│   │  아이디                 │   │
│   ├────────────────────────┤   │
│   │  비밀번호               │   │
│   └────────────────────────┘   │
│   [로그인] ← teal 버튼          │
│   오류 메시지 (숨김)             │
│                                │
└────────────────────────────────┘
```

- `POST /api/auth/login` (form-data: username, password)
- 응답 `access_token` → `localStorage.setItem('token', ...)`
- 성공 시 `window.location = '/data/query'`

### 3.3 `pages/query.html`

```
브레드크럼: Data › EDA Query

┌─ SQL 쿼리 입력 (textarea, 8줄) ──────────────────┐
│  SELECT * FROM ...                               │
└──────────────────────────────────────────────────┘
[실행] ← teal 버튼

┌─ 결과 테이블 ────────────────────────────────────┐
│  컬럼1 │ 컬럼2 │ 컬럼3 ...                       │
│  ...                                             │
└──────────────────────────────────────────────────┘
행 수: N  │  실행 시간: Xms
```

API: `POST /api/query/execute` `{sql: "...", limit: 500}`

### 3.4 `pages/datasets.html`

```
브레드크럼: Data › 데이터셋

[+ 데이터셋 등록]

┌─ 데이터셋 목록 ───────────────────────────────────┐
│ 이름      │ 설명    │ 소유자  │ 등록일    │ 액션   │
│ ds_train  │ ...     │ admin  │ 2026-04  │ [다운] │
└───────────────────────────────────────────────────┘
```

API: `GET /api/datasets/` → 목록 | `POST /api/datasets/` → 등록

### 3.5 `pages/jupyter.html`

```
브레드크럼: AI ML › JupyterLab

┌─ JupyterLab 접속 ──────────────────────────────┐
│                                                 │
│  [새 탭에서 JupyterLab 열기 →]  teal 버튼       │
│                                                 │
│  JupyterLab URL: http://<host>:6888/...         │
│                                                 │
│  ┌─ iframe (높이 600px) ───────────────────┐    │
│  │  http://<host>:6888                    │    │
│  └────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

API: `GET /api/jupyter/url` → `{url, token}`  
iframe src = 동적 주입 (JS에서 API 응답 후 설정)

### 3.6 `pages/mlflow.html`

```
브레드크럼: AI ML › MLflow 실험

[새 탭에서 MLflow 열기 →]

┌─ iframe (높이 600px) ──────────────────────────┐
│  http://<host>:6000                            │
└────────────────────────────────────────────────┘
```

API: `GET /api/mlflow/url` → `{url}`

### 3.7 `pages/board.html`

```
브레드크럼: 게시판

[글 작성]   [검색: _______]

┌─ 글 목록 ─────────────────────────────────────┐
│ # │ 제목          │ 작성자  │ 날짜      │ 조회  │
│ 5 │ 공지사항      │ admin  │ 2026-04  │ 12   │
└───────────────────────────────────────────────┘

← 이전  1  다음 →
```

API: `GET /api/board/posts?skip=0&limit=10&search=...`

### 3.8 `pages/files.html`

```
브레드크럼: 파일 관리

[파일 업로드 선택] [업로드]

┌─ 파일 목록 ─────────────────────────────────────┐
│ 파일명         │ 크기   │ 업로드일   │ 액션      │
│ data.csv      │ 1.2MB │ 2026-04  │ [다운로드] │
└─────────────────────────────────────────────────┘
```

API: `POST /api/files/upload` | `GET /api/files/list` | `GET /api/files/download/{name}`

---

## 4. JavaScript 설계 (`app.js`)

### 4.1 인증 모듈

```javascript
// 토큰 관리
const Auth = {
  getToken() { return localStorage.getItem('token'); },
  setToken(t) { localStorage.setItem('token', t); },
  clear()    { localStorage.removeItem('token'); localStorage.removeItem('user'); },
  isLoggedIn() { return !!this.getToken(); },
  getUser()  { return JSON.parse(localStorage.getItem('user') || 'null'); },
  setUser(u) { localStorage.setItem('user', JSON.stringify(u)); },
};

// API 호출 헬퍼 (항상 Bearer 헤더 첨부)
async function apiFetch(path, options = {}) {
  const token = Auth.getToken();
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) { logout(); return null; }
  return res;
}

// 로그아웃
function logout() {
  Auth.clear();
  window.location.href = '/login';
}
```

### 4.2 페이지 초기화 흐름

```
DOMContentLoaded
  │
  ├── Auth.isLoggedIn() == false → window.location = '/login'
  │
  └── Auth.isLoggedIn() == true
        ├── nav-username textContent = Auth.getUser().username
        └── initPage()  ← 각 페이지별 함수 (query, board, ...)
```

### 4.3 로그인 처리 (`login.html` 인라인 스크립트)

```javascript
async function handleLogin(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  const res = await fetch('/api/auth/login', { method: 'POST', body: form });
  if (!res.ok) {
    document.getElementById('error-msg').textContent = '아이디 또는 비밀번호가 올바르지 않습니다.';
    return;
  }
  const data = await res.json();
  Auth.setToken(data.access_token);
  // 사용자 정보 조회
  const me = await apiFetch('/api/auth/me');
  if (me) Auth.setUser(await me.json());
  window.location.href = '/data/query';
}
```

### 4.4 Query 페이지 (`query.html` 인라인)

```javascript
async function runQuery() {
  const sql = document.getElementById('sql-input').value.trim();
  if (!sql) return;
  const res = await apiFetch('/api/query/execute', {
    method: 'POST',
    body: JSON.stringify({ sql, limit: 500 }),
  });
  const data = await res.json();
  renderTable(data.columns, data.rows);
  document.getElementById('row-count').textContent = `행 수: ${data.row_count}`;
}

function renderTable(columns, rows) {
  // thead + tbody 동적 생성
}
```

---

## 5. FastAPI 웹 라우트 (`app/api/routes/web.py`)

### 5.1 라우트 목록

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")

# 루트 → Data Query로 리다이렉트
@router.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/data/query")

# 로그인
@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Data 탭
@router.get("/data/query", response_class=HTMLResponse, include_in_schema=False)
async def query_page(request: Request):
    return templates.TemplateResponse("pages/query.html",
        {"request": request, "active_tab": "data", "active_page": "query"})

@router.get("/data/datasets", response_class=HTMLResponse, include_in_schema=False)
async def datasets_page(request: Request):
    return templates.TemplateResponse("pages/datasets.html",
        {"request": request, "active_tab": "data", "active_page": "datasets"})

# AI ML 탭
@router.get("/aiml/jupyter", response_class=HTMLResponse, include_in_schema=False)
async def jupyter_page(request: Request):
    return templates.TemplateResponse("pages/jupyter.html",
        {"request": request, "active_tab": "aiml", "active_page": "jupyter"})

@router.get("/aiml/mlflow", response_class=HTMLResponse, include_in_schema=False)
async def mlflow_page(request: Request):
    return templates.TemplateResponse("pages/mlflow.html",
        {"request": request, "active_tab": "aiml", "active_page": "mlflow"})

# 게시판 탭
@router.get("/board", response_class=HTMLResponse, include_in_schema=False)
async def board_page(request: Request):
    return templates.TemplateResponse("pages/board.html",
        {"request": request, "active_tab": "board", "active_page": "board"})

# 파일 관리 탭
@router.get("/files", response_class=HTMLResponse, include_in_schema=False)
async def files_page(request: Request):
    return templates.TemplateResponse("pages/files.html",
        {"request": request, "active_tab": "files", "active_page": "files"})
```

### 5.2 `main.py` 변경 사항

```python
# app/main.py 추가할 내용
from fastapi.staticfiles import StaticFiles
from app.api.routes import web  # 신규

# create_app() 내부
application.mount("/static", StaticFiles(directory="app/static"), name="static")
application.include_router(web.router)  # /api prefix 없이
# 기존 root redirect 제거 (web.router의 "/" 핸들러가 대체)
```

---

## 6. 브레드크럼 컴포넌트

```css
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.breadcrumb .sep { color: var(--text-muted); }
.breadcrumb .current { color: var(--text-primary); font-weight: 500; }
```

예시:
```html
<!-- query.html breadcrumb block -->
{% block breadcrumb %}
  <span>Data</span>
  <span class="sep">›</span>
  <span class="current">EDA Query</span>
{% endblock %}
```

---

## 7. 공통 컴포넌트 CSS

### 7.1 버튼

```css
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: background 0.15s;
}
.btn-primary {
  background: var(--primary);
  color: #fff;
}
.btn-primary:hover { background: var(--primary-hover); }
.btn-secondary {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
}
.btn-secondary:hover { background: var(--bg-sidebar); }
```

### 7.2 테이블

```css
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.data-table th {
  background: var(--bg-sidebar);
  color: var(--text-secondary);
  font-weight: 600;
  padding: 10px 12px;
  border-bottom: 2px solid var(--border);
  text-align: left;
}
.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
}
.data-table tr:hover td { background: var(--bg-sidebar); }
```

### 7.3 카드

```css
.card {
  background: var(--bg-content);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}
```

---

## 8. 인증 가드 (미인증 리다이렉트)

HTML 페이지 라우트는 서버사이드 토큰 검증 없이 제공되며, **클라이언트 JS**가 초기화 시점에 검사.

```javascript
// app.js 최상단 — 모든 페이지에 적용
document.addEventListener('DOMContentLoaded', () => {
  // 로그인 페이지는 제외
  if (window.location.pathname === '/login') return;

  if (!Auth.isLoggedIn()) {
    window.location.href = '/login';
    return;
  }

  // 사용자 이름 표시
  const user = Auth.getUser();
  const el = document.getElementById('nav-username');
  if (el && user) el.textContent = `${user.username} (${user.role || ''})`;
});
```

> 서버사이드 가드는 v2에서 추가 (FastAPI Depends + Cookie/Header 검증). 현재는 JS 가드로 충분.

---

## 9. 구현 순서 (Phase 계획)

| Phase | 내용 | 산출물 |
|-------|------|--------|
| **1** | 기반 구조 생성 | `app/templates/`, `app/static/`, `app/api/routes/web.py` |
| **1** | base.html + main.css | 상단바 + 사이드바 레이아웃 렌더링 확인 |
| **1** | login.html + app.js Auth | 로그인 → `/data/query` 리다이렉트 동작 |
| **2** | query.html | SQL 실행 + 결과 테이블 |
| **2** | jupyter.html + mlflow.html | iframe 임베드 |
| **2** | board.html | 글 목록 + 작성 |
| **3** | datasets.html + files.html | 파일 업로드/다운로드 |
| **4** | 통합 테스트 | 전 페이지 인증 흐름, 탭 전환, iframe |

---

## 10. 삭제 대상

| 대상 | 시점 |
|------|------|
| `ui/` 폴더 전체 (streamlit_app.py, views/) | Phase 1 완료 후 |
| `start_ui.bat` | Phase 1 완료 후 |
| `requirements.txt` streamlit, pandas | Phase 1 완료 후 |
| `main.py` root redirect (RedirectResponse) | web.py 라우터로 대체 |

---

## 11. 접속 URL (변경 후)

| 서비스 | URL |
|--------|-----|
| 포털 | http://\<host\>:6080 → /data/query |
| 로그인 | http://\<host\>:6080/login |
| API 문서 | http://\<host\>:6080/docs |
| JupyterLab | http://\<host\>:6888 (iframe) |
| MLflow | http://\<host\>:6000 (iframe) |
