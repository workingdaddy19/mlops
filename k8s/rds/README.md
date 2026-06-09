# RDS PostgreSQL 초기화 가이드

## 📋 개요

이 디렉토리는 AWS RDS PostgreSQL의 테이블을 초기화하는 스크립트를 포함합니다.
**주의**: mlops 사용자는 역할 생성 권한(CREATEROLE)이 없으므로, 추가 사용자 생성은 불가능합니다.

### RDS 연결 정보

```
Host:     xxxxxx
Port:     5432
Database: mlops
User:     mlops (현재 사용자)

```

---

## 🚀 실행 방법

### 방법 A: EC2에서 직접 실행

#### 1단계: EC2에 접속
```bash
ssh -i mlfoundry.pem ec2-user@192.168.6.13
```

#### 2단계: psql 설치 (필요시)
```bash
# Amazon Linux 2
sudo yum install postgresql15-client -y

# Ubuntu/Debian
sudo apt-get install postgresql-client -y
```

#### 3단계: 스크립트 파일을 EC2에 복사
```bash
# 로컬 Windows/Mac에서 EC2로 복사
scp -i mlfoundry.pem k8s/rds/*.sql ec2-user@192.168.6.13:/tmp/
```

#### 4단계: RDS 스크립트 실행 (mlops 사용자로)

**Step 1: 현재 권한 및 테이블 확인**
```bash
psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
     -U mlops \
     -d mlops \
     -f /tmp/01-init-users.sql
```

**Step 2: 추가 테이블 생성 (schema_context)**
```bash
psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
     -U mlops \
     -d mlops \
     -f /tmp/02-create-additional-tables.sql
```

---

### 방법 B: Kubernetes Pod에서 실행

#### 1단계: mlfoundry-backend Pod 확인
```bash
kubectl get pod -n mlops -l app=mlfoundry-backend
```

#### 2단계: Pod에서 권한 확인
```bash
kubectl exec -it <POD_NAME> -n mlops -- \
  psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
       -U mlops \
       -d mlops \
       -f /app/k8s/rds/01-init-users.sql
```

#### 3단계: Pod에서 테이블 생성
```bash
kubectl exec -it <POD_NAME> -n mlops -- \
  psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
       -U mlops \
       -d mlops \
       -f /app/k8s/rds/02-create-additional-tables.sql
```

---

## ✅ 검증

### 1. 생성된 사용자 확인
```bash
psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
     -U mlops \
     -d mlops \
     -c "\du"
```

**예상 결과:**
```
                           List of roles
 Role name       | Attributes | Member of
-----------------+------------+-----------
 mlops           | ...        | {}
 mlops_admin     | ...        | {}
 mlops_readonly  | ...        | {}
 postgres        | ...        | {}
```

### 2. 권한 확인 (mlops_readonly가 SELECT만 가능)
```bash
# mlops_readonly로 접속하여 SELECT 테스트
psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
     -U mlops_readonly \
     -d mlops \
     -c "SELECT COUNT(*) FROM users;"

# SELECT 성공 ✅
```

### 3. schema_context 테이블 확인
```bash
psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
     -U mlops \
     -d mlops \
     -c "SELECT * FROM schema_context;"
```

**예상 결과:**
```
 id | db_name | table_name        | ddl_text | description | is_active | created_at
----+---------+-------------------+----------+-------------+-----------+----------
  1 | mlops   | users             | ...      | 사용자 정보 테이블 | t | ...
  2 | mlops   | datasets          | ...      | 데이터셋 메타정보 | t | ...
  3 | mlops   | dataset_features  | ...      | 데이터셋 컬럼 정의 | t | ...
  4 | mlops   | board             | ...      | 게시판     | t | ...
  5 | mlops   | data_query_history| ...     | SQL 쿼리 이력 | t | ...
```

### 4. 모든 테이블 확인
```bash
psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
     -U mlops \
     -d mlops \
     -c "\dt"
```

---

## 🔐 사용자별 권한 요약

| 사용자 | `` | 권한 | 용도 |
|--------|------|------|------|
| `mlops` | `` | 전체 (CREATE, INSERT, UPDATE, DELETE) | FastAPI 앱 |
| `mlops_readonly` | `` | SELECT only | BI 도구, 분석 |
| `mlops_admin` | `` | CREATE, DROP, ALTER, 사용자 관리 | DBA 작업 |

---

## 🐛 트러블슈팅

### 에러: "password authentication failed"
- RDS 보안그룹에서 EC2의 보안그룹이 5432 포트를 허용하는지 확인
- RDS 엔드포인트가 공개 접근 가능한지 확인

### 에러: "role already exists"
- 스크립트에서 `CREATE USER IF NOT EXISTS`를 사용하므로 안전
- 재실행해도 문제없음

### 에러: "table already exists"
- `CREATE TABLE IF NOT EXISTS`를 사용하므로 안전
- `ON CONFLICT DO NOTHING`으로 데이터 충돌 방지

---

## 📚 참고 문서

- 배포 가이드: `docs/03-guide/deployment-guide.md`
