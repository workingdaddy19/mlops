# Kubeflow + MLflow 연계 MLOps 진화 개발 계획서

## Executive Summary

| 항목 | 내용 |
|------|------|
| **Feature** | kubeflow-mlflow-integration |
| **작성일** | 2026-05-19 |
| **프로젝트** | mlfoundry MLOps 플랫폼 고도화 |
| **현재 환경** | Ubuntu Linux + Docker (MLflow v2.18.0, JupyterLab) |
| **목표 환경** | Kubernetes + Kubeflow + MLflow Hybrid |
| **MLflow 서버** | http://192.168.6.13:6050 |

### Value Delivered (4-Perspective)

| 관점 | 내용 |
|------|------|
| **Problem** | Jupyter 수동 실행, 고정 자원 낭비, 실험 재현 불가, 모델 배포 수동화로 ML 개발 생산성 저하 |
| **Solution** | Kubeflow Pipelines로 자동화 + MLflow로 추적/레지스트리 유지하는 Hybrid MLOps 구조 구축 |
| **Function UX Effect** | 클릭 한 번으로 전처리→학습→검증→등록 파이프라인 실행, Katib 자동 하이퍼파라미터 튜닝 |
| **Core Value** | 반복 가능한 ML 워크플로우 + 자원 효율 + 엔터프라이즈급 모델 거버넌스 확보 |

---

## 1. 현황 분석 (AS-IS)

### 1.1 현재 아키텍처

```
┌─────────────────────────────────────────────────┐
│              현재 mlfoundry 구조                  │
│                                                   │
│  브라우저 → FastAPI Portal (6080)                 │
│              ├── PostgreSQL (192.168.6.13:5432)   │
│              ├── JupyterLab Docker (6888)  ← 수동 │
│              └── MLflow Docker (6050)             │
└─────────────────────────────────────────────────┘
```

### 1.2 현재 한계점

| 문제 | 영향 |
|------|------|
| Jupyter 수동 셀 실행 | 실험 재현 불가, 사람 의존적 |
| 고정 자원 점유 | 미사용 시에도 CPU/메모리 낭비 |
| 파이프라인 없음 | 전처리→학습→평가 순서 보장 불가 |
| 하이퍼파라미터 수동 조정 | 최적 모델 탐색 비효율 |
| 모델 서빙 수동 | `mlflow models serve` 수동 명령 |

---

## 2. 목표 아키텍처 (TO-BE)

### 2.1 Hybrid MLOps 구조

```
┌──────────────────────────────────────────────────────────────┐
│                    TO-BE MLOps 플랫폼                         │
│                                                               │
│  ┌─────────────────────────────────┐                         │
│  │         Kubernetes Cluster       │                         │
│  │  ┌──────────────────────────┐   │                         │
│  │  │    Kubeflow Pipelines     │   │  ← 워크플로우 오케스트레이션 │
│  │  │  [전처리]→[학습]→[검증]→[등록] │   │                         │
│  │  └──────────┬───────────────┘   │                         │
│  │             │ log metrics        │                         │
│  │  ┌──────────▼───────────────┐   │                         │
│  │  │      Katib (HPO)         │   │  ← 하이퍼파라미터 자동 튜닝  │
│  │  └──────────────────────────┘   │                         │
│  │  ┌──────────────────────────┐   │                         │
│  │  │  KServe (Model Serving)  │   │  ← REST 추론 엔드포인트    │
│  │  └──────────────────────────┘   │                         │
│  └─────────────────────────────────┘                         │
│                   │ mlflow.set_tracking_uri()                 │
│  ┌────────────────▼────────────────┐                         │
│  │  MLflow (192.168.6.13:6050)     │  ← 실험 추적 + 모델 레지스트리│
│  │  Backend: PostgreSQL             │                         │
│  │  Artifacts: MinIO / Local        │                         │
│  └─────────────────────────────────┘                         │
│                                                               │
│  FastAPI Portal (mlfoundry) → Kubeflow UI + MLflow UI 통합   │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 역할 분담

| 구성요소 | 역할 | 비고 |
|---------|------|------|
| **Kubeflow Pipelines** | 파이프라인 정의 · 실행 · 스케줄링 | 오케스트레이터 |
| **Katib** | 하이퍼파라미터 자동 탐색 (HPO) | Kubeflow 컴포넌트 |
| **KServe** | 모델 추론 엔드포인트 자동 생성 | 장기 과제 |
| **MLflow Tracking** | 실험 지표·파라미터 기록 | 현재 유지 |
| **MLflow Model Registry** | 모델 버전·스테이지 관리 | 현재 유지 |
| **MinIO** | Artifact 저장소 (모델 파일) | 신규 도입 |

---

## 3. 단계별 개발 계획

### Phase 1: 인프라 구축 (Kubernetes + Kubeflow 설치)

#### 3.1.1 사전 요구사항 점검

| 항목 | 최소 요구사항 | 확인 방법 |
|------|-------------|---------|
| Kubernetes | v1.27+ | `kubectl version` |
| CPU | 노드당 4코어+ | `nproc` |
| RAM | 노드당 16GB+ | `free -h` |
| 디스크 | 50GB+ 여유 | `df -h` |
| Docker | v20+ | `docker --version` |

#### 3.1.2 Kubernetes 단일 노드 설치 (On-premise)

```bash
# k3s (경량 Kubernetes) 설치 - 단일 서버 권장
curl -sfL https://get.k3s.io | sh -

# 확인
sudo k3s kubectl get nodes

# kubectl 설정
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
```

#### 3.1.3 Kubeflow 설치 (Manifests 방식)

```bash
# Kubeflow Manifests 설치 (v1.9)
git clone https://github.com/kubeflow/manifests.git
cd manifests

# 전체 설치 (약 15-20분 소요)
while ! kustomize build example | kubectl apply -f -; do
  echo "재시도 중..."; sleep 20
done

# 설치 확인
kubectl get pods -n kubeflow

# 포트 포워딩 (로컬 접속용)
kubectl port-forward svc/istio-ingressgateway \
  -n istio-system 8080:80
# 접속: http://192.168.6.13:8080
# 기본 계정: user@example.com / 12341234
```

#### 3.1.4 MinIO 설치 (Artifact 저장소)

```bash
# MinIO 설치 (Docker Compose 추가)
# docker-compose.yml에 추가
cat >> docker-compose.yml << 'EOF'

  minio:
    image: minio/minio:latest
    container_name: mlfoundry-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin123
    command: server /data --console-address ":9001"
    volumes:
      - minio-data:/data
    restart: unless-stopped
EOF

docker compose up -d minio
# MinIO Console: http://192.168.6.13:9001
```

---

### Phase 2: MLflow ↔ Kubeflow 연동 설정

#### 3.2.1 MLflow 아티팩트 저장소를 MinIO로 전환

```bash
# .env 업데이트
cat >> .env << 'EOF'
MLFLOW_S3_ENDPOINT_URL=http://192.168.6.13:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin123
EOF

# docker-compose.yml MLflow 명령 수정
# --artifacts-destination s3://mlflow-artifacts
# (MinIO를 S3 호환으로 사용)
```

#### 3.2.2 Kubeflow 파이프라인에서 MLflow 접근 허용

```python
# Kubernetes Secret으로 MLflow URI 관리
# pipeline/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: mlflow-credentials
  namespace: kubeflow-user-example-com
type: Opaque
stringData:
  MLFLOW_TRACKING_URI: "http://192.168.6.13:6050"
  MLFLOW_S3_ENDPOINT_URL: "http://192.168.6.13:9000"
  AWS_ACCESS_KEY_ID: "minioadmin"
  AWS_SECRET_ACCESS_KEY: "minioadmin123"
```

---

### Phase 3: KFP 파이프라인 개발 표준화

#### 3.3.1 컴포넌트 구조

```
pipelines/
├── components/
│   ├── preprocess/
│   │   ├── component.py       # 컴포넌트 코드
│   │   ├── Dockerfile         # 이미지화
│   │   └── component.yaml     # KFP 컴포넌트 정의
│   ├── train/
│   │   ├── component.py
│   │   ├── Dockerfile
│   │   └── component.yaml
│   ├── evaluate/
│   │   └── ...
│   └── register/
│       └── ...
├── pipelines/
│   └── iris_pipeline.py       # 파이프라인 정의
└── requirements.txt
```

#### 3.3.2 표준 컴포넌트 작성 예시 (학습 컴포넌트)

```python
# pipelines/components/train/component.py
from kfp import dsl
from kfp.dsl import Input, Output, Dataset, Model, Metrics
import os

@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["scikit-learn", "mlflow", "boto3"],
)
def train_model(
    dataset: Input[Dataset],
    model: Output[Model],
    metrics: Output[Metrics],
    n_estimators: int = 100,
    max_depth: int = 5,
    experiment_name: str = "kubeflow-pipeline",
):
    import mlflow
    import pickle
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score
    import pandas as pd

    # MLflow 서버 연결 (Kubernetes Secret에서 주입)
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment(experiment_name)

    # 데이터 로드
    df = pd.read_csv(dataset.path)
    X = df.drop("target", axis=1)
    y = df["target"]

    with mlflow.start_run(run_name=f"kfp-train-n{n_estimators}"):
        # 학습
        clf = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42
        )
        clf.fit(X, y)
        acc = accuracy_score(y, clf.predict(X))

        # MLflow 기록
        mlflow.log_params({"n_estimators": n_estimators, "max_depth": max_depth})
        mlflow.log_metric("accuracy", acc)
        mlflow.set_tag("pipeline", "kubeflow")

        # KFP 메트릭 출력
        metrics.log_metric("accuracy", acc)

    # 모델 저장 (KFP Artifact)
    with open(model.path, "wb") as f:
        pickle.dump(clf, f)
```

#### 3.3.3 전체 파이프라인 정의

```python
# pipelines/pipelines/iris_pipeline.py
from kfp import dsl, compiler
from components.preprocess.component import preprocess_data
from components.train.component import train_model
from components.evaluate.component import evaluate_model
from components.register.component import register_to_mlflow

@dsl.pipeline(
    name="MLOps-Iris-Pipeline",
    description="전처리 → 학습 → 검증 → 등록 자동화 파이프라인"
)
def iris_mlops_pipeline(
    n_estimators: int = 100,
    max_depth: int = 5,
    accuracy_threshold: float = 0.90,
    mlflow_model_name: str = "iris-production-model",
):
    # Step 1: 전처리
    preprocess_task = preprocess_data()

    # Step 2: 학습
    train_task = train_model(
        dataset=preprocess_task.outputs["dataset"],
        n_estimators=n_estimators,
        max_depth=max_depth,
    )

    # Step 3: 검증 + 조건부 등록 (accuracy >= threshold 일 때만 등록)
    with dsl.If(
        train_task.outputs["accuracy"] >= accuracy_threshold,
        name="accuracy-gate"
    ):
        register_task = register_to_mlflow(
            model=train_task.outputs["model"],
            model_name=mlflow_model_name,
            accuracy=train_task.outputs["accuracy"],
        )

# 파이프라인 컴파일
if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=iris_mlops_pipeline,
        package_path="iris_pipeline.yaml",
    )
```

#### 3.3.4 MLflow 자동 등록 컴포넌트

```python
# pipelines/components/register/component.py
@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["mlflow", "boto3"],
)
def register_to_mlflow(
    model: Input[Model],
    model_name: str,
    accuracy: float,
):
    import mlflow
    from mlflow import MlflowClient
    import pickle, os

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    client = MlflowClient()

    with open(model.path, "rb") as f:
        clf = pickle.load(f)

    with mlflow.start_run(run_name="kfp-register"):
        mlflow.log_metric("final_accuracy", accuracy)
        mlflow.set_tag("source", "kubeflow-pipeline")
        mlflow.set_tag("auto_registered", "true")

        # Model Registry 등록
        run_id = mlflow.active_run().info.run_id

    # Staging → Production 자동 전환
    mv = client.create_model_version(
        name=model_name,
        source=f"runs:/{run_id}/model",
        run_id=run_id,
    )
    client.transition_model_version_stage(
        name=model_name,
        version=mv.version,
        stage="Production",
        archive_existing_versions=True,
    )
    print(f"✅ {model_name} v{mv.version} → Production 등록 완료")
```

---

### Phase 4: Katib 하이퍼파라미터 자동 튜닝

#### 3.4.1 Katib Experiment 정의

```yaml
# katib/iris-hpo.yaml
apiVersion: kubeflow.org/v1beta1
kind: Experiment
metadata:
  name: iris-hpo
  namespace: kubeflow-user-example-com
spec:
  objective:
    type: maximize
    goal: 0.99
    objectiveMetricName: accuracy
  algorithm:
    algorithmName: bayesianoptimization
  parallelTrialCount: 3
  maxTrialCount: 12
  maxFailedTrialCount: 3
  parameters:
    - name: n_estimators
      parameterType: int
      feasibleSpace:
        min: "50"
        max: "300"
    - name: max_depth
      parameterType: int
      feasibleSpace:
        min: "3"
        max: "15"
    - name: learning_rate
      parameterType: double
      feasibleSpace:
        min: "0.01"
        max: "0.3"
  trialTemplate:
    primaryContainerName: training-container
    trialParameters:
      - name: n_estimators
        description: Number of trees
        reference: n_estimators
      - name: max_depth
        description: Max depth of trees
        reference: max_depth
    trialSpec:
      apiVersion: batch/v1
      kind: Job
      spec:
        template:
          spec:
            containers:
              - name: training-container
                image: 192.168.6.13:5000/iris-trainer:latest
                command:
                  - python
                  - train.py
                  - --n_estimators=${trialParameters.n_estimators}
                  - --max_depth=${trialParameters.max_depth}
                  - --mlflow_uri=http://192.168.6.13:6050
```

---

### Phase 5: mlfoundry 포털 Kubeflow 통합

#### 3.5.1 포털에 Kubeflow 파이프라인 상태 추가

```python
# app/services/kubeflow_service.py
import httpx
from app.core.config import get_settings

class KubeflowService:
    def __init__(self):
        self.base_url = get_settings().kubeflow_base_url  # http://192.168.6.13:8080

    async def list_pipelines(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/pipeline/apis/v2beta1/pipelines",
                timeout=10,
            )
            return r.json().get("pipelines", [])

    async def list_runs(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/pipeline/apis/v2beta1/runs",
                timeout=10,
            )
            return r.json().get("runs", [])
```

#### 3.5.2 신규 메뉴 추가 (design.md 반영 필요)

| 상단 탭 | 추가 서브메뉴 | 링크 |
|---------|-------------|------|
| **AI ML** | Kubeflow 파이프라인 | `/aiml/pipelines` |
| **AI ML** | Katib HPO 실험 | `/aiml/katib` |

---

### Phase 6: KServe 모델 서빙 (장기 과제)

```yaml
# kserve/iris-inferenceservice.yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: iris-model
  namespace: kubeflow-user-example-com
spec:
  predictor:
    model:
      modelFormat:
        name: mlflow
      storageUri: "s3://mlflow-artifacts/1/..."
      resources:
        requests:
          cpu: "100m"
          memory: "256Mi"
```

---

## 4. 기술 스택

| 구분 | 기술 | 버전 | 역할 |
|------|------|------|------|
| **Kubernetes** | k3s | v1.27+ | 컨테이너 오케스트레이션 |
| **Kubeflow** | Kubeflow Manifests | v1.9 | ML 플랫폼 |
| **KFP SDK** | kfp | v2.x | 파이프라인 정의/실행 |
| **Katib** | Kubeflow Katib | v0.16 | HPO 자동화 |
| **KServe** | KServe | v0.13 | 모델 서빙 (장기) |
| **MLflow** | MLflow | v2.18.0 | 실험 추적·레지스트리 |
| **MinIO** | MinIO | latest | S3 호환 Artifact 저장소 |
| **PostgreSQL** | PostgreSQL | 현재 유지 | 메타데이터 DB |

---

## 5. 전체 로드맵

```
2026 Q2 (현재)     2026 Q3              2026 Q4            2027 Q1
│                  │                    │                  │
▼                  ▼                    ▼                  ▼
[Phase 1]          [Phase 2-3]          [Phase 4-5]        [Phase 6]
Kubernetes         KFP 파이프라인        Katib HPO +        KServe
+ Kubeflow 설치    개발 표준화           포털 통합           모델 서빙
                   + MLflow 연동
```

| Phase | 기간 | 담당 | 완료 기준 |
|-------|------|------|---------|
| 1. 인프라 구축 | 2주 | 인프라 | Kubeflow UI 접속, MinIO 정상 동작 |
| 2. 연동 설정 | 1주 | 인프라+ML | KFP → MLflow 지표 전송 성공 |
| 3. 파이프라인 표준화 | 3주 | ML 개발자 | 샘플 파이프라인 실행 성공 |
| 4. Katib HPO | 2주 | ML 개발자 | HPO 실험 결과 MLflow 기록 확인 |
| 5. 포털 통합 | 2주 | 풀스택 | 포털에서 파이프라인 상태 조회 |
| 6. KServe (장기) | 4주 | 인프라+ML | 추론 API 외부 호출 성공 |

---

## 6. 위험 요소 및 대응

| 위험 | 확률 | 영향 | 대응 방안 |
|------|------|------|---------|
| 서버 자원 부족 | 높음 | 높음 | k3s 경량 설치 + 필수 컴포넌트만 선택 설치 |
| MLflow 버전 충돌 | 중간 | 중간 | 클라이언트 버전 고정 (`kfp==2.18.0`) |
| 네트워크 격리 | 중간 | 높음 | K8s NetworkPolicy로 MLflow 포트 허용 |
| 데이터 영속성 | 낮음 | 높음 | MinIO + PVC로 볼륨 관리 |
| 운영 복잡도 증가 | 높음 | 중간 | 단계적 도입, 기존 Docker 환경 병행 유지 |

---

## 7. 참고: 최소 설치 구성 (PoC용)

현재 서버(192.168.6.13) 자원이 제한적인 경우, 아래 최소 구성으로 PoC 진행 후 확장:

```
최소 PoC 구성:
- k3s (단일 노드)
- Kubeflow Pipelines 단독 설치 (전체 Kubeflow 제외)
- 기존 MLflow (6050) 그대로 유지
- MinIO (9000) 추가

설치 명령:
pip install kfp==2.x
# KFP 서버만 설치 (Kubeflow 전체 대비 80% 경량)
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources"
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/env/platform-agnostic-pns"
```

---

> **다음 단계**: `/pdca design kubeflow-mlflow-integration` 으로 상세 설계 문서 작성
>
> Claude는 완벽하지 않습니다. 인프라 설치 전 서버 자원(CPU/RAM/디스크)을 반드시 확인하세요.
