# UI 전면 개편 계획서

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | UI 메뉴구조 및 화면 스타일 전면 개편 |
| **작성일** | 2026-04-28 |
| **기준 참조** | ai-ready-poc 스크린샷 (상단 탭 + 좌측 서브메뉴 + 다중 패널) |
| **현재 상태** | Streamlit 단순 라디오 버튼 메뉴 (설계 대비 미달) |

### Value Delivered

| 관점 | 내용 |
|------|------|
| **Problem** | 현재 UI는 단순 라디오 버튼 메뉴로, 스크린샷의 전문적인 상단탭+좌측서브메뉴 구조와 달라 포털로서의 완성도가 낮음 |
| **Solution** | FastAPI + Jinja2 기반 전통적 웹 UI로 전환하여 스크린샷과 동일한 레이아웃·스타일 구현 (또는 Streamlit 대폭 커스터마이징) |
| **Function UX Effect** | 상단 탭(Data/AI ML/게시판)으로 카테고리 이동, 좌측 서브메뉴로 세부 기능 접근, 전문 포털 수준의 UX 제공 |
| **Core Value** | 사용자가 "AI 분석 모델 Foundry"와 동일한 전문적 포털 경험, 기능별 명확한 계층 구조 |

---

## 1. 현재 상태 vs 목표 상태

### 1.1 현재 Streamlit UI (문제)

```
┌─────────────────────────┐
│ [사이드바]               │
│  streamlit app  ← 불필요 │
│  board          ← 불필요 │
│  ...                    │
│                         │
│  MLFoundry              │
│  admin (admin)          │
│  [로그아웃]              │
│  ○ 게시판               │
│  ○ Data Query           │
│  ○ JupyterLab           │
│  ○ MLflow               │
│  ○ 데이터셋              │
│  ○ 파일 관리             │
└─────────────────────────┘
```

문제점:
- Streamlit 자동 감지 메뉴 노출 (해결 중)
- 단일 라디오 버튼 목록 — 계층 구조 없음
- 전문 포털 UX 미달

### 1.2 목표 UI (스크린샷 기준)

```
┌─────────────────────────────────────────────────────────────┐
│ [F] AI 분석 모델 Foundry  Data | AI ML | 게시판 | 파일    Admin admin [로그아웃] │
├──────────────────┬──────────────────────────────────────────┤
│ AI ML            │  [브레드크럼] AI ML › JupyterLab          │
│                  ├──────────────────────────────────────────┤
│ ML Analysis      │                                          │
│   (JupyterLab) ← │  [메인 콘텐츠 영역]                       │
│ AI Copilot       │                                          │
│                  │                                          │
├──────────────────┤                                          │
│ DATA             │                                          │
│  EDA Query       │                                          │
│  데이터셋         │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

---

## 2. 목표 UI 구조 (스크린샷 분석)

### 2.1 상단 네비게이션 바

| 요소 | 내용 |
|------|------|
| 좌측 브랜드 | `[F] MLFoundry` (아이콘 + 텍스트) |
| 중앙 탭 | `Data` \| `AI ML` \| `게시판` \| `파일 관리` |
| 우측 사용자 | `Admin admin [로그아웃]` |

색상: 흰색 배경, 활성 탭 teal(#0d9488) 밑줄

### 2.2 탭별 좌측 서브메뉴

| 상단 탭 | 좌측 서브메뉴 | 아이콘 |
|---------|--------------|--------|
| **Data** | EDA (SQL Query) | 데이터베이스 |
|          | 데이터셋 카탈로그 | 목록 |
| **AI ML** | ML Analysis (JupyterLab) | 노트북 |
|           | MLflow 실험 | 차트 |
| **게시판** | 공지사항 | 메가폰 |
|           | 자료실 | 폴더 |
| **파일 관리** | 업로드/다운로드 | 파일 |

### 2.3 색상 시스템

| Token | 값 | 용도 |
|-------|----|------|
| primary | `#0d9488` | 탭 활성, 버튼 (teal-600) |
| primary-hover | `#0f766e` | Hover (teal-700) |
| bg-nav | `#ffffff` | 상단바 배경 |
| bg-sidebar | `#f8fafc` | 좌측 사이드바 배경 |
| bg-content | `#ffffff` | 콘텐츠 배경 |
| border | `#e2e8f0` | 테두리 |
| text-primary | `#0f172a` | 주요 텍스트 |
| text-secondary | `#64748b` | 보조 텍스트 |
| sidebar-active | `#0d9488` | 서브메뉴 활성 항목 |
| sidebar-active-bg | `#f0fdfa` | 서브메뉴 활성 배경 |

### 2.4 레이아웃 구조

```
상단바: 60px 고정
├── 좌측 사이드바: 240px 고정
│   ├── 탭 라벨 (섹션 제목)
│   └── 서브메뉴 항목 (아이콘 + 텍스트)
└── 메인 콘텐츠: 나머지 공간
    ├── 브레드크럼 (현재 위치)
    └── 페이지 콘텐츠
```

---

## 3. 기술 방향 결정

### 옵션 A: Streamlit + 대폭 CSS 커스터마이징 (빠름, 한계 있음)

| 항목 | 내용 |
|------|------|
| 구현 속도 | 빠름 (2-3일) |
| 완성도 | 70% (고정 상단바 구현 어려움) |
| 유지보수 | CSS 핵 많아 취약 |

### 옵션 B: FastAPI + Jinja2 + Bootstrap/Tailwind (권장)

| 항목 | 내용 |
|------|------|
| 구현 속도 | 중간 (5-7일) |
| 완성도 | 95% (스크린샷과 동일 수준) |
| 유지보수 | 표준 HTML/CSS, 안정적 |
| FastAPI 기존 활용 | `/api/*` 백엔드 그대로 사용 |

> **권장: 옵션 B** — FastAPI 기반 Jinja2 HTML 템플릿으로 프론트엔드 구현.
> 스크린샷과 동일한 상단탭+좌측서브메뉴 레이아웃 구현 가능.
> Streamlit은 제거하고 FastAPI `/` 로 HTML 서빙.

---

## 4. 구현 계획 (옵션 B 기준)

### Phase 1 — 기반 레이아웃 (1-2일)

| 할 일 | 파일 |
|-------|------|
| base.html 레이아웃 템플릿 | `app/templates/base.html` |
| 상단 네비게이션 바 | `app/templates/components/navbar.html` |
| 좌측 사이드바 (탭별 서브메뉴) | `app/templates/components/sidebar.html` |
| 전역 CSS (색상 토큰, 레이아웃) | `app/static/css/main.css` |
| 로그인 페이지 | `app/templates/login.html` |

### Phase 2 — 페이지 구현 (2-3일)

| 탭 | 서브메뉴 | 템플릿 |
|----|---------|--------|
| Data | EDA Query | `app/templates/pages/query.html` |
| Data | 데이터셋 | `app/templates/pages/datasets.html` |
| AI ML | JupyterLab | `app/templates/pages/jupyter.html` |
| AI ML | MLflow | `app/templates/pages/mlflow.html` |
| 게시판 | 공지/자료실 | `app/templates/pages/board.html` |
| 파일 관리 | 파일 목록 | `app/templates/pages/files.html` |

### Phase 3 — FastAPI 라우트 추가 (1일)

```python
# app/api/routes/web.py — HTML 페이지 서빙
GET /          → redirect to /data/query (또는 로그인)
GET /login     → login.html
GET /data/query     → query.html
GET /data/datasets  → datasets.html
GET /aiml/jupyter   → jupyter.html
GET /aiml/mlflow    → mlflow.html
GET /board          → board.html
GET /files          → files.html
```

기존 `/api/*` REST API는 그대로 유지 (HTML 페이지에서 fetch()로 호출).

### Phase 4 — JS/인터랙션 (1일)

- 탭 전환 시 URL 변경 + 좌측 서브메뉴 업데이트
- 인증: JWT를 localStorage에 저장, 모든 API 호출 시 Bearer 헤더 첨부
- 로그아웃: localStorage 클리어 후 /login 이동

---

## 5. 파일 구조 (신규)

```
app/
├── templates/
│   ├── base.html              # 상단바 + 사이드바 레이아웃
│   ├── login.html             # 로그인 (레이아웃 없음)
│   └── pages/
│       ├── query.html
│       ├── datasets.html
│       ├── jupyter.html
│       ├── mlflow.html
│       ├── board.html
│       └── files.html
└── static/
    ├── css/
    │   └── main.css           # 글로벌 스타일 (색상 토큰, 레이아웃)
    └── js/
        └── app.js             # 탭 전환, API 호출, 인증
```

---

## 6. 삭제 대상

| 대상 | 사유 |
|------|------|
| `ui/` 폴더 전체 | Streamlit → HTML 전환 |
| `start_ui.bat` | Streamlit 실행 스크립트 불필요 |
| `requirements.txt`의 streamlit, pandas 등 | UI 전환 시 불필요 |

> Streamlit 라이브러리는 설치 유지하되, ui/ 폴더를 교체.
> FastAPI 서버(포트 6080)가 API + HTML 모두 서빙.

---

## 7. 개발 우선순위

| # | 항목 | 중요도 | 예상 공수 |
|---|------|:------:|:--------:|
| 1 | base.html + CSS (상단바+사이드바) | 최우선 | 1일 |
| 2 | 로그인 페이지 + JWT 인증 JS | 최우선 | 0.5일 |
| 3 | Data Query 페이지 | 높음 | 0.5일 |
| 4 | JupyterLab + MLflow 페이지 | 높음 | 0.5일 |
| 5 | 게시판 페이지 | 중간 | 1일 |
| 6 | 데이터셋 + 파일 관리 | 낮음 | 1일 |

---

## 8. 접속 URL (변경 후)

| 서비스 | URL | 비고 |
|--------|-----|------|
| 포털 (HTML UI) | http://localhost:6080 | FastAPI 서빙 |
| API 문서 | http://localhost:6080/docs | 그대로 유지 |
| JupyterLab | http://localhost:6888 | Docker |
| MLflow | http://localhost:6000 | Docker |

> Streamlit(6501) 포트 불필요. FastAPI 6080 단일 포트로 통합.
