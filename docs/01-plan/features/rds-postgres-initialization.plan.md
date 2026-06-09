# RDS PostgreSQL 초기화 및 사용자/스키마 설정 계획서

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | rds-postgres-initialization |
| **작성일** | 2026-05-22 |
| **목표** | AWS RDS PostgreSQL에 필요한 DB 사용자, 스키마, 테이블 생성 자동화 |
| **대상 환경** | RDS PostgreSQL (ap-northeast-2) |
| **현재 상태** | ✅ mlops DB/사용자 생성됨, 테이블 자동 생성됨 |

### Value Delivered (4-Perspective)

| 관점 | 내용 |
|------|------|
| **Problem** | RDS 초기 설정 수동 작업, 추가 사용자/역할/권한 관리 미비, 스크립트 자동화 부족 |
| **Solution** | RDS 초기화 스크립트 + 사용자/권한 자동 설정 + EC2/Kubernetes 배포 가이드 제공 |
| **Function UX Effect** | EC2 또는 Kubernetes에서 단일 명령어로 RDS 초기화 완료 |
| **Core Value** | RDS 운영 기준 수립 + 보안 역할 기반 접근제어 (RBAC) + 자동화 재사용성 |

---

## 1. 현황 분석 (AS-IS)

### 1.1 RDS PostgreSQL 현재 상태

```
Host:     rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com
Port:     5432
DB Name:  mlops
User:     mlops (기본 사용자)
SSL:      TLSv1.3 ✅
```

### 1.2 생성된 테이블 (SQLAlchemy ORM 자동 생성)

| 테이블 | 행 수 | 설명 |
|--------|-------|------|
| `users` | 2 | 기본 사용자 2명 (admin, user) ✅ |
| `datasets` | 0 | 데이터셋 메타정보 |
| `dataset_features` | 0 | 데이터셋 컬럼 정의 |
| `board` | 0 | 게시판 |
| `board_file` | 0 | 게시판 첨부파일 |
| `data_query_history` | 0 | SQL 쿼리 이력 |

### 1.3 미생성 테이블 (MySQL 스키마 기준 추가 필요)

| 테이블 | 설명 | 우선순위 |
|--------|------|---------|
| `s3_download_log` | S3 다운로드 로그 | ⏸️ 보류 (AWS S3 제거됨) |
| `schema_context` | Text2SQL 스키마 메타 | 🔴 필요 (LLM 연동용) |

---

## 2. 목표 아키텍처 (TO-BE)

### 2.1 RDS 사용자/역할 구조

```
RDS Cluster
├── Root User: postgres (AWS 자동 생성)
├── App User: mlops (현재 사용 중) ✅
│   └── DB: mlops (권한: 모든 스키마 액세스)
├── ReadOnly User: mlops_readonly (신규 추가)
│   └── 용도: 대시보드, 분석 도구 읽기 전용 접근
└── Admin User: mlops_admin (신규 추가)
    └── 용도: Schema 관리, 사용자 관리 권한
```

### 2.2 권한 할당 전략

| 사용자 | 권한 | 역할 | 사용처 |
|--------|------|------|--------|
| `mlops` | 전체 권한 (CREATE, INSERT, UPDATE, DELETE) | App | FastAPI 앱 |
| `mlops_readonly` | SELECT only | 읽기 전용 | BI 도구, 분석 |
| `mlops_admin` | CREATE/DROP/ALTER + 사용자 관리 | 관리자 | DBA 작업 |

---

## 3. 단계별 구현 계획

### Phase 1: PostgreSQL 초기화 스크립트 작성

#### 3.1.1 SQL 스크립트 생성

**파일**: `k8s/rds/01-init-users.sql`
```sql
-- 1. 읽기 전용 사용자 생성
CREATE USER IF NOT EXISTS mlops_readonly WITH PASSWORD 'kyobo_readonly123';

-- 2. 관리 사용자 생성
CREATE USER IF NOT EXISTS mlops_admin WITH PASSWORD 'kyobo_admin123';

-- 3. mlops 사용자가 없으면 생성 (이미 있을 가능성)
CREATE USER IF NOT EXISTS mlops WITH PASSWORD 'kyobo11!';

-- 4. 스키마 접근 권한 설정 (public schema)
GRANT USAGE ON SCHEMA public TO mlops, mlops_readonly, mlops_admin;

-- 5. mlops_readonly: SELECT only
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mlops_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mlops_readonly;

-- 6. mlops: 전체 권한
GRANT CREATE, CONNECT ON DATABASE mlops TO mlops;
GRANT ALL PRIVILEGES ON SCHEMA public TO mlops;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mlops;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mlops;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO mlops;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO mlops;

-- 7. mlops_admin: Schema 관리 권한
GRANT CREATE ON DATABASE mlops TO mlops_admin;
GRANT CREATE ON SCHEMA public TO mlops_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mlops_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mlops_admin;
```

#### 3.1.2 추가 테이블 스크립트

**파일**: `k8s/rds/02-create-additional-tables.sql`
```sql
-- schema_context 테이블 (Text2SQL 용)
CREATE TABLE IF NOT EXISTS schema_context (
    id SERIAL PRIMARY KEY,
    db_name VARCHAR(50) NOT NULL,
    table_name VARCHAR(200) NOT NULL,
    ddl_text TEXT,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(db_name, table_name)
);

-- 기본 스키마 메타정보 추가
INSERT INTO schema_context (db_name, table_name, ddl_text, description, is_active)
VALUES 
    ('mlops', 'users', 'SELECT * FROM users;', '사용자 정보 테이블', TRUE),
    ('mlops', 'datasets', 'SELECT * FROM datasets;', '데이터셋 메타정보', TRUE),
    ('mlops', 'dataset_features', 'SELECT * FROM dataset_features;', '데이터셋 컬럼 정의', TRUE),
    ('mlops', 'board', 'SELECT * FROM board;', '게시판', TRUE),
    ('mlops', 'data_query_history', 'SELECT * FROM data_query_history;', 'SQL 쿼리 이력', TRUE)
ON CONFLICT (db_name, table_name) DO NOTHING;
```

---

### Phase 2: EC2에서 RDS 초기화 실행

#### 3.2.1 EC2에서 스크립트 실행

**방법 A: 로컬 파일에서 실행**
```bash
# EC2에 스크립트 파일 업로드 후 실행
scp -i mlfoundry.pem k8s/rds/*.sql ec2-user@192.168.x.x:/tmp/

ssh -i mlfoundry.pem ec2-user@192.168.x.x

# RDS 접속 및 스크립트 실행
psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
     -U mlops -d mlops \
     -f /tmp/01-init-users.sql

psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
     -U mlops -d mlops \
     -f /tmp/02-create-additional-tables.sql
```

**방법 B: kubectl exec을 통해 Pod에서 실행 (Kubernetes)**
```bash
# Pod 내부에서 psql 실행
kubectl exec -it $(kubectl get pod -n mlops -l app=mlfoundry-backend \
  -o jsonpath='{.items[0].metadata.name}') -n mlops -- \
  psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
       -U mlops -d mlops < /app/k8s/rds/01-init-users.sql

kubectl exec -it ... -- \
  psql -h ... < /app/k8s/rds/02-create-additional-tables.sql
```

---

### Phase 3: 권한 검증 및 테스트

#### 3.3.1 각 사용자별 연결 테스트

```bash
# 1. mlops (전체 권한)
psql -h rds-an2-avb-poc-mlops... -U mlops -d mlops -c "\dt"

# 2. mlops_readonly (SELECT only)
psql -h rds-an2-avb-poc-mlops... -U mlops_readonly -d mlops -c "SELECT COUNT(*) FROM users;"

# 3. mlops_admin (관리 권한)
psql -h rds-an2-avb-poc-mlops... -U mlops_admin -d mlops -c "CREATE TABLE test (id INT); DROP TABLE test;"
```

#### 3.3.2 권한 확인 쿼리

```sql
-- 현재 사용자 권한 조회
SELECT table_name, string_agg(privilege_type, ', ' ORDER BY privilege_type)
FROM information_schema.role_table_grants
WHERE grantee = current_user
GROUP BY table_name;

-- 모든 사용자 조회
\du

-- 역할별 권한 상세 조회
GRANT USAGE ON SCHEMA public TO current_user;
SELECT grantee, privilege_type 
FROM information_schema.role_table_grants 
WHERE table_name IN ('users', 'datasets', 'board')
ORDER BY grantee, table_name;
```

---

## 4. 추가 설정 (선택사항)

### 4.1 Connection Pooling (선택)

FastAPI 앱이 자주 접속할 경우, RDS Proxy 또는 pgBouncer 사용 권장:

```
fastapi-app → pgBouncer (5432) → RDS (5433)
```

### 4.2 백업 전략

- **자동 백업**: RDS 기본 설정 (7일 보관) ✅
- **수동 스냅샷**: 중요 시점별 생성
  ```bash
  aws rds create-db-snapshot --db-instance-identifier mlops --db-snapshot-identifier mlops-backup-2026-05-22
  ```

### 4.3 모니터링

CloudWatch 메트릭:
- CPU Utilization
- Database Connections
- Query Performance Insights

---

## 5. 제공할 스크립트 리스트

| 파일 | 설명 | 대상 |
|------|------|------|
| `k8s/rds/01-init-users.sql` | 사용자 생성 + 권한 할당 | EC2/Pod |
| `k8s/rds/02-create-additional-tables.sql` | 추가 테이블 생성 | EC2/Pod |
| `k8s/rds/init-rds.sh` | 전체 초기화 자동 스크립트 | EC2 bash |
| `k8s/rds/README.md` | 설정 가이드 문서 | 개발자 |

---

## 6. 기술 스택 & 기준

| 항목 | 선택 | 이유 |
|------|------|------|
| **DB** | PostgreSQL 18.x (RDS) | ai-ready-poc 동일 기술 스택 |
| **Driver** | psycopg 3.x | SQLAlchemy 최적화 |
| **인증** | IAM DB Authentication (선택) | 보안 강화, 암호 불필요 |
| **SSL** | TLSv1.3 강제 | RDS 기본 설정 ✅ |

---

## 7. 위험 요소 & 대응

| 위험 | 확률 | 영향 | 대응 |
|------|------|------|------|
| 권한 설정 오류 | 중간 | 높음 | 검증 스크립트 + 수동 확인 |
| RDS 서브넷/SG 미설정 | 낮음 | 높음 | EKS VPC 보안그룹 재점검 |
| 비밀번호 하드코딩 | 높음 | 높음 | 환경변수 또는 AWS Secrets Manager 사용 |
| 데이터 마이그레이션 | 낮음 | 중간 | 추후 MySQL → PostgreSQL 마이그레이션 도구 준비 |

---

## 8. 일정

| Phase | 기간 | 담당 |
|-------|------|------|
| 1. 스크립트 작성 | 1일 | 개발팀 |
| 2. EC2 실행 + 검증 | 0.5일 | DevOps |
| 3. Kubernetes Pod 적용 | 1일 | DevOps |
| 4. 모니터링 설정 | 1일 | 인프라팀 |

**Total**: 3.5일

---

> **다음 단계**: `/pdca design rds-postgres-initialization` 으로 상세 설계 문서 작성
>
> Claude는 완벽하지 않습니다. 비밀번호와 보안 규칙은 조직의 기준에 맞게 조정하세요.
