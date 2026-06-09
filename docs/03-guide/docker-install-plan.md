# MLFoundry Docker 설치계획서 (JupyterLab + MLflow)

> 작성일: 2026-04-29
> 대상 서버: Ubuntu Linux (로컬)
> 참조: docker-compose.yml, startup-guide.md, mlfoundry.design.md

---

## 1. 현재 환경 점검 결과

| 항목 | 상태 | 비고 |
|------|------|------|
| Docker Engine | v29.3.0 설치됨 | 정상 |
| Docker Compose | v5.1.0 (plugin) | `docker compose` 명령 사용 (`docker-compose` 미설치) |
| .env 파일 | 존재 (13개 변수) | DB_PASSWORD, SECRET_KEY 등 설정 완료 |
| 디스크 여유 | 36GB (62% 사용) | 충분 |
| PostgreSQL | 192.168.6.13:5432 | 외부 서버, 기 설치 |

---

## 2. Docker 서비스 구성

### 2.1 JupyterLab (jupyter/scipy-notebook)

| 항목 | 값 |
|------|-----|
| 이미지 | `jupyter/scipy-notebook:latest` |
| 컨테이너명 | `mlfoundry-jupyter` |
| 포트 매핑 | `6888:8888` |
| 인증 토큰 | `mlfoundry_token` (JUPYTER_TOKEN) |
| 볼륨 | `mlfoundry_jupyter-notebooks` -> `/home/jovyan/work` |
| 재시작 정책 | `unless-stopped` |

### 2.2 MLflow Server

| 항목 | 값 |
|------|-----|
| 이미지 | `ghcr.io/mlflow/mlflow:v2.18.0` |
| 컨테이너명 | `mlfoundry-mlflow` |
| 포트 매핑 | `6000:5000` |
| Backend Store | `postgresql://ai_ready:<password>@192.168.6.13:5432/mlfoundry_mlflow` |
| Artifact Root | `/mlflow/artifacts` (볼륨 마운트) |
| 볼륨 | `mlfoundry_mlflow-artifacts` -> `/mlflow/artifacts` |
| 추가 설치 | `psycopg2-binary` (컨테이너 시작 시 pip install) |
| 재시작 정책 | `unless-stopped` |

---

## 3. 사전 필요 조건

### 3.1 필수 (이미 충족됨)

- [x] Docker Engine 설치
- [x] Docker Compose (plugin) 설치
- [x] `.env` 파일 생성 및 `DB_PASSWORD` 설정

### 3.2 MLflow용 DB 생성 (1회)

MLflow backend store로 사용할 별도 DB `mlfoundry_mlflow`가 필요합니다.

```bash
PGPASSWORD=<비밀번호> psql -h 192.168.6.13 -p 5432 -U ai_ready -d postgres \
  -c "CREATE DATABASE mlfoundry_mlflow OWNER ai_ready;"
```

> MLflow가 이 DB에 실험/런 메타데이터를 자동으로 테이블 생성하여 저장합니다.

---

## 4. 실행 절차

### Step 1: MLflow용 DB 확인/생성
```bash
PGPASSWORD=<비밀번호> psql -h 192.168.6.13 -p 5432 -U ai_ready -d postgres \
  -c "SELECT datname FROM pg_database WHERE datname = 'mlfoundry_mlflow';"
```

### Step 2: Docker 컨테이너 실행
```bash
cd /home/kyobo/mlops-poc/mlfoundry
docker compose up -d
```

### Step 3: 상태 확인
```bash
docker ps --filter "name=mlfoundry"
```

### Step 4: 헬스체크
```bash
# JupyterLab (토큰 필요, 403은 정상 - 인증 필요 의미)
curl -s -o /dev/null -w "%{http_code}" http://localhost:6888/api/status

# MLflow (200 = 정상)
curl -s -o /dev/null -w "%{http_code}" http://localhost:6000/health
```

---

## 5. 접속 정보

| 서비스 | URL | 인증 |
|--------|-----|------|
| JupyterLab | http://localhost:6888 | 토큰: `mlfoundry_token` |
| MLflow | http://localhost:6000 | 없음 (오픈) |

---

## 6. 주의사항

1. **`docker compose` 사용**: 이 서버에는 `docker-compose` (standalone)가 없으므로 반드시 `docker compose` (plugin) 명령을 사용해야 합니다.
2. **MLflow DB**: `mlfoundry_mlflow` DB가 없으면 MLflow 서버가 시작 후 즉시 종료됩니다.
3. **볼륨 데이터 보존**: `docker compose down`으로 중지해도 볼륨 데이터(노트북, 아티팩트)는 유지됩니다. `docker compose down -v` 사용 시 데이터가 삭제되므로 주의.
4. **네트워크**: MLflow가 PostgreSQL(192.168.6.13)에 접근 가능해야 합니다.

---

## 7. 현재 실행 상태 (점검 결과)

| 컨테이너 | 상태 | 가동 시간 | 헬스체크 |
|----------|------|-----------|---------|
| mlfoundry-jupyter | Running (healthy) | 4일 | 403 (정상 - 토큰 인증 필요) |
| mlfoundry-mlflow | Running | 4일 | 200 (정상) |

> 두 서비스 모두 이미 정상 가동 중입니다.
