# AWS Platform Integration Planning Document

> **Summary**: 불필요 코드 정리 + AWS Athena/S3/JupyterHub 통합으로 플랫폼 완성도 향상
>
> **Project**: MLFoundry (AI 데이터 분석 플랫폼)
> **Version**: 2.0
> **Author**: Claude Code
> **Date**: 2026-05-27
> **Status**: Draft

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | 로컬 파일 시스템 기반의 임시 구현이 남아있고, EDA Query가 PostgreSQL만 지원하며, JupyterHub 접속이 iframe 방식으로 불안정함 |
| **Solution** | AWS Athena로 EDA Query 교체, AWS S3로 파일 관리 전환, JupyterHub Admin API로 개인별 토큰 기반 접속 개선, 불필요 코드 삭제 |
| **Function/UX Effect** | 데이터 레이크 쿼리 지원, S3 탐색기 UI, 개인별 Jupyter 환경(CPU/GPU) 리스트 제공으로 사용성 대폭 향상 |
| **Core Value** | MLOps 플랫폼의 AWS 네이티브 통합 완성 — 데이터 분석부터 모델 학습까지 일관된 AWS 기반 워크플로우 |

---

## 1. Overview

### 1.1 Purpose

현재 구현된 MLFoundry 포탈의 다음 문제를 해결한다:

1. **불필요 코드 잔존**: 로컬 파일 시스템 기반 `FileService`, 임시 파일 API, iframe 방식 jupyter 접속 코드
2. **Athena 미연동**: EDA Query가 PostgreSQL 직접 쿼리만 지원, 실제 데이터 레이크(S3 기반)는 쿼리 불가
3. **S3 미연동**: 파일 관리가 로컬 `/uploads` 디렉토리 기반, 실제 S3 버켓(`s3-an2-mlflow`) 탐색 불가
4. **JupyterHub 접속 불편**: iframe 미리보기 → CSP 정책으로 로드 불가, 개인별 pod 매칭 미지원

### 1.2 Background

- AWS EKS 배포 완료 (Pod Running 상태)
- JupyterHub → `jupyterhub.mlops.click` 외부 접속 가능
- MLflow → `mlflow.mlops.click` 외부 접속 가능
- S3 버켓 `s3-an2-mlflow` 운영 중
- Athena를 통한 S3 데이터 레이크 쿼리 환경 준비 예정

### 1.3 Related Documents

- [Service Token Management Plan](./service-token-management.plan.md)
- [Service Token Management Design](../02-design/features/service-token-management.design.md)
- [IMPLEMENTATION.md](../../IMPLEMENTATION.md)

---

## 2. Scope

### 2.1 In Scope

**[A] 코드 정리 (Code Cleanup)**
- [ ] `app/services/file_service.py` 삭제 (S3 서비스로 대체)
- [ ] `app/api/routes/files.py` 삭제 (S3 라우터로 대체)
- [ ] `app/services/jupyter_service.py` 리팩토링 (iframe URL 방식 → Admin API 방식)
- [ ] `app/schemas/service_token.py` 불필요 스키마 정리
- [ ] `service_token.py` 버그 수정 (84번 라인 `ㅢ` 제거, redirect URL 경로 수정)
- [ ] `k8s/backend-secret.yaml` 외부 URL 영구 반영

**[B] AWS Athena 쿼리 통합 (EDA Query)**
- [ ] `app/services/athena_service.py` 신규 생성 (AWS SDK boto3 기반)
- [ ] `app/api/routes/query.py` Athena 쿼리 엔드포인트 추가
- [ ] `app/schemas/query.py` Athena 스키마 추가 (데이터베이스/테이블 목록)
- [ ] `app/templates/pages/query.html` Athena 데이터베이스 선택 UI 추가
- [ ] `app/core/config.py` Athena 설정 추가 (`ATHENA_DATABASE`, `ATHENA_S3_OUTPUT`)
- [ ] `k8s/backend-secret.yaml` Athena 환경변수 추가

**[C] S3 스토리지 통합 (파일 관리 → S3 스토리지)**
- [ ] `app/services/s3_service.py` 신규 생성 (boto3 S3 탐색, 다운로드)
- [ ] `app/api/routes/s3_storage.py` 신규 생성 (기존 files.py 대체)
- [ ] `app/templates/pages/files.html` S3 탐색기 UI 전면 교체
  - 좌측: 폴더 트리 (윈도우 탐색기 스타일, +/- 접기/펼치기)
  - 우측: 파일 목록 (파일명, 사이즈, 최근 변경일자)
  - 업로드 기능 제거
- [ ] `app/templates/base.html` 메뉴명 변경 ("파일 관리" → "S3 스토리지", "업로드/다운로드" → "파일 탐색")
- [ ] `app/api/router.py` s3_storage 라우터 등록 (files 라우터 교체)

**[D] JupyterHub 개인별 접속 개선 (ML Analysis)**
- [ ] `app/services/jupyter_service.py` JupyterHub Admin API 토큰 발급 구현
- [ ] `app/api/routes/jupyter.py` 개인별 접속 정보 API 추가
- [ ] `app/templates/pages/jupyter.html` iframe 제거 → 리스트 뷰 교체
  - 환경 목록: CPU 환경, GPU 환경 (행 형태)
  - 각 행: 환경명, 접속 URL, 토큰 상태, "새 탭에서 열기" 버튼
  - URL 형식: `http://jupyterhub.mlops.click/user/{username}/lab/`
- [ ] `app/core/config.py` JupyterHub Admin API Token 설정 추가
- [ ] `k8s/backend-secret.yaml` `JUPYTERHUB_ADMIN_TOKEN` 추가

### 2.2 Out of Scope

- Athena DDL/DML 쿼리 (SELECT만 허용, 기존 방침 유지)
- S3 파일 업로드 기능 (읽기 전용 탐색만)
- JupyterHub Pod 직접 생성/삭제 (별도 운영 작업)
- MLflow UI 변경 (현재 외부 URL 리다이렉트 방식 유지)
- 게시판/데이터셋 기능 변경

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | 요구사항 | 우선순위 | 상태 |
|----|----------|----------|------|
| FR-01 | `service_token.py` 구문 오류(`ㅢ`) 수정 및 redirect URL 경로 수정 | High | Pending |
| FR-02 | `k8s/backend-secret.yaml` 외부 URL (`jupyterhub.mlops.click`, `mlflow.mlops.click`) 영구 반영 | High | Pending |
| FR-03 | `k8s/backend-ingress.yaml` 서비스명 `mlops`로 통일 | High | Pending |
| FR-04 | AWS Athena 쿼리 실행 API (`POST /api/query/athena/execute`) 구현 | High | Pending |
| FR-05 | Athena 데이터베이스/테이블 목록 조회 API (`GET /api/query/athena/databases`) 구현 | High | Pending |
| FR-06 | EDA Query 페이지에 Athena DB 선택 드롭다운 추가 | Medium | Pending |
| FR-07 | AWS S3 버켓 탐색 API (`GET /api/s3/browse`) 구현 - 경로별 파일/폴더 목록 | High | Pending |
| FR-08 | S3 파일 다운로드 Presigned URL API (`GET /api/s3/download`) 구현 | Medium | Pending |
| FR-09 | 파일 관리 페이지 S3 탐색기 UI 교체 (트리 + 목록 2-panel) | High | Pending |
| FR-10 | 사이드바 "파일 관리" → "S3 스토리지" 명칭 변경 | Low | Pending |
| FR-11 | JupyterHub Admin API로 사용자별 토큰 발급 (`GET /api/jupyter/token/{username}`) | High | Pending |
| FR-12 | ML Analysis 페이지 iframe 제거, 환경 리스트 뷰 표시 | High | Pending |
| FR-13 | CPU/GPU 환경 각각 접속 링크 제공 (서버 이름 기반) | Medium | Pending |
| FR-14 | 불필요 소스 삭제: `file_service.py`, `files.py` (로컬 파일 시스템) | Medium | Pending |

### 3.2 Non-Functional Requirements

| 범주 | 기준 | 측정 방법 |
|------|------|-----------|
| Performance | Athena 쿼리 응답 < 30초 (Athena 특성상 장시간 허용) | 실제 쿼리 실행 측정 |
| Performance | S3 파일 목록 조회 < 3초 (1000개 기준) | API 응답 시간 측정 |
| Security | AWS IAM Role (IRSA) 기반 인증, 하드코딩 자격증명 금지 | 코드 리뷰 |
| Security | S3 다운로드는 Presigned URL (유효기간 1시간) | API 응답 검증 |
| UX | S3 폴더 트리 즉시 로드, 하위 탐색 < 1초 | 브라우저 측정 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] FR-01~FR-03 버그 수정 완료 (Pod CrashLoopBackOff 없음)
- [ ] Athena SELECT 쿼리 실행 후 결과 테이블 표시
- [ ] S3 버켓 탐색 - 폴더 클릭 시 하위 목록 표시
- [ ] ML Analysis 페이지 - CPU/GPU 접속 링크 각각 표시
- [ ] 불필요 코드 삭제 후 테스트 통과

### 4.2 Quality Criteria

- [ ] Pod 재시작 후 정상 기동 (CrashLoopBackOff 없음)
- [ ] 신규 AWS SDK 코드에 에러 핸들링 포함
- [ ] 삭제된 파일 참조 없음 (import 오류 없음)

---

## 5. Risks and Mitigation

| 위험 | 영향도 | 발생 가능성 | 대응 방안 |
|------|--------|-------------|-----------|
| IRSA 미설정으로 Athena/S3 접근 실패 | High | Medium | boto3 fallback: 환경변수 `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` 지원 |
| JupyterHub Admin API 토큰 미설정 | High | Medium | config 기본값 처리, 미설정 시 graceful 에러 메시지 표시 |
| Athena 쿼리 비용 (스캔 과금) | Medium | Medium | 쿼리 결과 캐싱, 최대 스캔 사이즈 제한 설정 |
| S3 폴더 트리 대용량 (파일 수천 개) | Medium | Low | 페이지네이션 적용, 한 번에 최대 1000개 표시 |
| CPU/GPU pod 이름 규칙 미확정 | Medium | High | 설정 파일로 환경 목록 관리 (`JUPYTER_ENVS` 설정 추가) |

---

## 6. Architecture Considerations

### 6.1 Project Level

**Enterprise** (FastAPI + AWS SDK + Kubernetes 운영 중)

### 6.2 Key Architectural Decisions

| 결정 사항 | 옵션 | 선택 | 이유 |
|-----------|------|------|------|
| AWS SDK | boto3 / aws-sdk | boto3 (Python) | FastAPI Python 기반 |
| Athena 인증 | IAM Role (IRSA) / Access Key | IRSA 우선, AccessKey fallback | EKS 환경 IRSA 사용이 베스트 프랙티스 |
| S3 탐색 방식 | ListObjectsV2 / S3fs | boto3 ListObjectsV2 | 추가 의존성 없음 |
| JupyterHub 토큰 | Admin API / Pre-shared | Admin API | 동적 토큰 발급, 보안 우수 |
| Jupyter 환경 구분 | Named Server / 별도 JupyterHub | Named Server | 단일 JupyterHub에서 프로파일 기반 |

### 6.3 새로운 API 구조

```
신규/변경 엔드포인트:

[Athena]
GET  /api/query/athena/databases       - DB/테이블 목록
POST /api/query/athena/execute         - SELECT 쿼리 실행
GET  /api/query/athena/history         - 쿼리 히스토리

[S3 Storage]
GET  /api/s3/browse?prefix={path}      - 파일/폴더 목록
GET  /api/s3/download?key={key}        - Presigned URL 생성

[JupyterHub]
GET  /api/jupyter/envs                 - 사용자 환경 목록 (CPU/GPU)
GET  /api/jupyter/token/{env}          - 환경별 토큰 발급

[삭제]
/api/files (구 파일 관리 API 전체 삭제)
```

### 6.4 JupyterHub Admin API 토큰 발급 흐름

```
포탈 사용자(admin) → GET /api/jupyter/envs
  → JupyterService.get_user_envs(username="admin")
    → JupyterHub Admin API: POST /hub/api/users/admin/tokens
         Authorization: token {JUPYTERHUB_ADMIN_TOKEN}
      → Response: {"token": "xxx...", "expires_at": null}
    → 환경 목록 반환:
       [
         {
           "name": "CPU 환경",
           "server": "",  // default server
           "url": "http://jupyterhub.mlops.click/user/admin/lab/?token=xxx",
           "status": "running"
         },
         {
           "name": "GPU 환경",
           "server": "gpu",  // named server
           "url": "http://jupyterhub.mlops.click/user/admin/gpu/lab/?token=xxx",
           "status": "stopped"
         }
       ]
→ 프론트엔드: 리스트 카드 형태로 표시, "새 탭에서 열기" 버튼
```

### 6.5 S3 탐색기 UI 구조

```
┌──────────────────────────────────────────────────────────┐
│  S3 스토리지  (s3-an2-mlflow)                            │
├──────────────┬───────────────────────────────────────────┤
│ 폴더 트리    │  파일 목록                                │
│              │                                           │
│ 📁 /         │  이름           │ 크기    │ 수정일        │
│ ├ 📁 data/   │  📁 models/     │ -       │ 2026-05-20    │
│ │ ├📁models/ │  📄 config.json │ 1.2 KB  │ 2026-05-21    │
│ │ └📁logs/   │  📄 README.md   │ 3.5 KB  │ 2026-05-22    │
│ └ 📁 mlflow/ │                           │               │
│              │  [파일 업로드 버튼 없음]  │               │
└──────────────┴───────────────────────────────────────────┘
```

---

## 7. Environment Variables (추가 필요)

| 변수명 | 용도 | 범위 | 기본값 |
|--------|------|------|--------|
| `ATHENA_REGION` | Athena 리전 | Server | `ap-northeast-2` |
| `ATHENA_DATABASE` | 기본 Athena DB | Server | `mlops` |
| `ATHENA_S3_OUTPUT` | 쿼리 결과 저장 S3 경로 | Server | `s3://s3-an2-mlflow/athena-results/` |
| `S3_BUCKET_NAME` | S3 버켓명 | Server | `s3-an2-mlflow` |
| `S3_REGION` | S3 리전 | Server | `ap-northeast-2` |
| `JUPYTERHUB_ADMIN_TOKEN` | JupyterHub 관리자 API 토큰 | Server | (필수, 없으면 오류) |
| `JUPYTER_ENVS` | 제공할 Jupyter 환경 목록 (JSON) | Server | `[{"name":"CPU","server":""},{"name":"GPU","server":"gpu"}]` |

---

## 8. Implementation Order (4 Phases)

### Phase 1: 버그 수정 및 코드 정리 (즉시, 0.5일)

1. `app/api/routes/service_token.py` — `ㅢ` 제거, redirect URL 수정
2. `k8s/backend-secret.yaml` — 외부 URL 반영
3. `k8s/backend-ingress.yaml` — 서비스명 `mlops` 통일
4. EC2 동기화 및 Docker 재빌드

### Phase 2: Athena 쿼리 통합 (1일)

1. `requirements.txt`에 `boto3` 추가
2. `app/services/athena_service.py` 신규
3. `app/api/routes/query.py` Athena 엔드포인트 추가
4. `app/schemas/query.py` Athena 스키마 추가
5. `app/core/config.py` Athena 설정 추가
6. `k8s/backend-secret.yaml` 환경변수 추가
7. `app/templates/pages/query.html` UI 수정

### Phase 3: S3 스토리지 통합 (1일)

1. `app/services/s3_service.py` 신규
2. `app/api/routes/s3_storage.py` 신규
3. `app/api/router.py` 교체 (files → s3_storage)
4. `app/services/file_service.py` **삭제**
5. `app/api/routes/files.py` **삭제**
6. `app/templates/pages/files.html` 전면 교체
7. `app/templates/base.html` 메뉴명 변경
8. `app/core/config.py` S3 설정 추가

### Phase 4: JupyterHub 개선 (1일)

1. `app/services/jupyter_service.py` Admin API 방식으로 리팩토링
2. `app/api/routes/jupyter.py` 환경 목록/토큰 API 추가
3. `app/templates/pages/jupyter.html` 리스트 뷰 교체
4. `app/core/config.py` JupyterHub Admin Token 설정 추가
5. `k8s/backend-secret.yaml` `JUPYTERHUB_ADMIN_TOKEN` 추가
6. EC2 동기화 및 최종 Docker 배포

---

## 9. Next Steps

1. [ ] Design 문서 작성 (`/pdca design aws-platform-integration`)
2. [ ] Phase 1 버그 수정 즉시 진행 (Pod 안정성)
3. [ ] boto3 의존성 추가 및 AWS IAM 권한 확인

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-05-27 | Initial draft | Claude Code |
