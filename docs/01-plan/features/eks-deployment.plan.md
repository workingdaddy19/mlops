# EKS 배포 계획서 (Plan)

> Version: 1.1.0 | Created: 2026-05-20 | Status: Completed

## 1. Executive Summary (개요)
MLFoundry의 커스텀 FastAPI 백엔드를 AWS EKS의 `mlops` 네임스페이스에 배포합니다. 
엄격한 네임스페이스 기반 RBAC 정책을 준수하며, 백엔드는 외부 RDS 데이터베이스에 연결됩니다.

## 2. Goals and Objectives (목표)
- MLFoundry FastAPI 백엔드의 컨테이너화.
- 백엔드를 위한 Kubernetes 매니페스트(YAML) 생성.
- 환경 변수(RDS 접속 정보 등)를 안전하게 관리하고 Amazon ECR에 이미지 푸시.
- 제한된 `mlops` 네임스페이스에 성공적으로 리소스 배포.

## 3. Scope (범위)
### In Scope (포함)
- FastAPI 백엔드용 `Dockerfile` 작성.
- ECR 로그인, 빌드, 푸시를 자동화하는 `build_and_push.sh` 스크립트 작성.
- `mlops` 네임스페이스로 제한된 Kubernetes `Deployment`, `Service`, `Secret` 매니페스트 작성.
- FastAPI 백엔드 파드 배포.

### Out of Scope (제외)
- MLflow, Airflow, Jupyter 배포 (다른 네임스페이스/파드에서 처리).
- 데이터베이스 프로비저닝 (기존 RDS 사용).
- RBAC 제한으로 인한 클러스터 전역 리소스(Namespace, ClusterRole 등) 수정.

## 4. Success Criteria
| Criterion | Metric | Target |
|-----------|--------|--------|
| Pod Running | Status | Running & Ready |
| Connectivity | HTTP Status | 200 OK at /docs |
| Database | Connection | Successful RDS query |

## 5. Timeline
| Milestone | Date | Description |
|-----------|------|-------------|
| Plan | 2026-05-20 | Planning approved |
| Design | 2026-05-20 | Architecture designed |
| Do | 2026-05-20 | Code and YAML created |
| Check | 2026-05-20 | Gap analysis |
