# mlfoundry Gap Analysis Report (v3 New UI)

> **Analysis Type**: Gap Analysis (PDCA Check Phase)
> **Feature**: mlfoundry - Local ML Data Platform Portal (UI Redesign)
> **Date**: 2026-04-28
> **Design Doc**: [mlfoundry.design.md](../02-design/features/mlfoundry.design.md)
> **Plan Doc**: [mlfoundry.plan.md](../01-plan/features/mlfoundry.plan.md)

---

## Overall Match Rate: **85%** ⚠️

> UI 전면 개편 (FastAPI+Jinja2) 적용 후 핵심 구조 일치.

| Category | 설계 기준 | 구현 상태 | Rate | Status |
|----------|:---------:|:---------:|:----:|:------:|
| UI Architecture | FastAPI + Jinja2 | 구현 완료 | 100% | ✅ |
| Web Routes | `/data/query`, `/aiml/*` 등 | 구현 완료 | 100% | ✅ |
| Layout (base.html) | 상단탭 + 사이드바 | 구현 완료 (CSS 적용됨) | 95% | ✅ |
| API Endpoints | REST API 전체 | 일부 누락/필드 불일치 유지 | 75% | ⚠️ |
| SQLAlchemy Models | 7개 테이블 | 필드 드리프트 존재 | 75% | ⚠️ |
| Client JS (app.js) | JWT 인증 + fetch | 구현 완료 | 95% | ✅ |
| Service Layer | 7개 서비스 | 전부 존재 | 95% | ✅ |

---

## Critical Gaps (Remaining)

### 1. DB 스키마 필드 드리프트 (HIGH)

디자인 문서 § 5에 정의된 필드명/타입과 실제 `app/models/` 구현 간의 차이가 여전히 존재함. (v2 Analysis와 동일)

### 2. 누락된 API 엔드포인트

- `GET /health` (통합 헬스체크) 미구현.
- `PUT /api/datasets/{id}` (수정 기능) 미구현.

### 3. 대시보드 페이지 미구현

신규 UI에서도 `dashboard.html` 및 관련 라우트가 아직 존재하지 않음.

---

## 권장 조치

1. **DB 모델 필드명 동기화**: `models/user.py` (username -> user_id) 등 설계와 일치하도록 수정.
2. **Alembic 마이그레이션**: 현재 `create_all()` 방식에서 Alembic 버전 관리로 전환.
3. **대시보드 구현**: 서비스 상태를 한눈에 볼 수 있는 메인 페이지 추가.
