# EKS Deployment Design Document

> Version: 1.0.0 | Created: 2026-05-20 | Status: Completed

## 1. Overview (개요)
MLFoundry 백엔드를 AWS EKS 클러스터의 제한된 `mlops` 네임스페이스에 배포하기 위한 설계입니다.

## 2. Architecture (아키텍처)
### Components
- **Dockerfile**: `python:3.12-slim` 기반, 포트 6080 노출.
- **ECR Script**: `aws ecr get-login-password`, `docker build`, `tag`, `push`.
- **K8s Manifests**:
  - `Secret`: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.
  - `Deployment`: `replicas: 1`, `envFrom: secretRef`, Liveness/Readiness Probes.
  - `Service`: `type: ClusterIP`, `port: 6080`.

## 3. Data Model
Environment variables sourced from Secret `backend-secret`.

## 4. API Specification
- Health Check: `/docs` (Readiness/Liveness probes).

## 5. Test Plan
| Test Case | Expected Result |
|-----------|-----------------|
| ECR Push | Image exists in ECR |
| K8s Apply | Resources created in `mlops` namespace |
| Pod Status | Running/Ready |
| Connectivity | Accessible via port-forward |
