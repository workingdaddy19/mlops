"""
MLOps 4단계 시연 스크립트 (아티팩트 업로드 없는 버전)
대상 서버: http://192.168.6.13:6050

실행: JupyterLab 터미널 또는 노트북에서
    python /home/kyobo/mlops-poc/mlfoundry/demo/mlops_demo.py
"""

import time
import mlflow
from mlflow import MlflowClient
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC

TRACKING_URI = "http://192.168.6.13:6050"
EXPERIMENT_NAME = "MLOps-Demo-Iris-Classification"
MODEL_NAME = "iris-best-model"

mlflow.set_tracking_uri(TRACKING_URI)
client = MlflowClient(tracking_uri=TRACKING_URI)

print("=" * 60)
print("  MLOps 4단계 시연 시작")
print(f"  MLflow 서버  : {TRACKING_URI}")
print(f"  클라이언트 v : {mlflow.__version__}")
print("=" * 60)

iris = load_iris()
X_train, X_test, y_train, y_test = train_test_split(
    iris.data, iris.target, test_size=0.2, random_state=42
)

# ─────────────────────────────────────────────────────────────
# Phase 1: 실험 및 추적 (Tracking)
# ─────────────────────────────────────────────────────────────
print("\n[Phase 1] 실험 및 추적 (Tracking)")
print("-" * 40)

mlflow.set_experiment(EXPERIMENT_NAME)

candidates = [
    {
        "name": "LogisticRegression",
        "model": LogisticRegression(max_iter=200, C=1.0, random_state=42),
        "params": {"algorithm": "LogisticRegression", "max_iter": 200, "C": 1.0, "solver": "lbfgs"},
    },
    {
        "name": "LogisticRegression-High-C",
        "model": LogisticRegression(max_iter=200, C=10.0, random_state=42),
        "params": {"algorithm": "LogisticRegression", "max_iter": 200, "C": 10.0, "solver": "lbfgs"},
    },
    {
        "name": "RandomForest-100",
        "model": RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42),
        "params": {"algorithm": "RandomForest", "n_estimators": 100, "max_depth": 5},
    },
    {
        "name": "RandomForest-200",
        "model": RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42),
        "params": {"algorithm": "RandomForest", "n_estimators": 200, "max_depth": 10},
    },
    {
        "name": "SVM-RBF",
        "model": SVC(kernel="rbf", C=1.0, probability=True, random_state=42),
        "params": {"algorithm": "SVM", "kernel": "rbf", "C": 1.0},
    },
]

run_results = []

for c in candidates:
    with mlflow.start_run(run_name=c["name"]) as run:
        start = time.time()
        c["model"].fit(X_train, y_train)
        duration = round(time.time() - start, 4)

        y_pred = c["model"].predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average="weighted")

        mlflow.log_params(c["params"])
        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("f1_score", f1)
        mlflow.log_metric("training_sec", duration)
        mlflow.log_metric("train_samples", len(X_train))
        mlflow.log_metric("test_samples", len(X_test))
        mlflow.set_tag("dataset", "iris")
        mlflow.set_tag("phase", "1-tracking")

        run_results.append({
            "name": c["name"],
            "run_id": run.info.run_id,
            "accuracy": acc,
            "f1": f1,
            "model": c["model"],
        })
        print(f"  ✅ {c['name']:25s} accuracy={acc:.4f}  f1={f1:.4f}")

print(f"\n  → UI 확인: {TRACKING_URI}/#/experiments")

# ─────────────────────────────────────────────────────────────
# Phase 2: 패키징 및 환경 표준화 (Projects)
# ─────────────────────────────────────────────────────────────
print("\n[Phase 2] 패키징 및 환경 표준화 (Projects)")
print("-" * 40)

best = max(run_results, key=lambda x: x["accuracy"])
print(f"  Best Model : {best['name']}  (accuracy={best['accuracy']:.4f})")

with mlflow.start_run(run_name="Packaged-BestModel") as pkg_run:
    mlflow.log_params({
        "selected_algorithm": best["name"],
        "selection_criteria": "highest_accuracy",
        "source_run_id": best["run_id"],
        "python_version": "3.11",
        "mlflow_version": "2.18.0",
        "environment": "conda",
    })
    mlflow.log_metric("final_accuracy", best["accuracy"])
    mlflow.log_metric("final_f1", best["f1"])
    mlflow.set_tag("phase", "2-packaging")
    mlflow.set_tag("reproducible", "true")
    mlflow.set_tag("mlproject_entry", "train")
    pkg_run_id = pkg_run.info.run_id

print(f"  ✅ 패키징 런 기록 완료  run_id={pkg_run_id[:8]}...")

# ─────────────────────────────────────────────────────────────
# Phase 3: 모델 등록 및 버전 관리 (Model Registry)
# ─────────────────────────────────────────────────────────────
print("\n[Phase 3] 모델 등록 및 버전 관리 (Model Registry)")
print("-" * 40)

# 모델 이름 등록 (없으면 새로 생성)
try:
    client.create_registered_model(
        name=MODEL_NAME,
        description=f"Iris 분류 모델 | 알고리즘: {best['name']}",
        tags={"team": "data-science", "project": "mlops-demo"},
    )
    print(f"  ✅ 모델 등록: {MODEL_NAME}")
except Exception:
    print(f"  ℹ️  모델 '{MODEL_NAME}' 이미 존재 → 새 버전 추가")

# 버전 생성 (run의 아티팩트 경로 참조)
source_uri = f"runs:/{pkg_run_id}/packaged_model"
mv = client.create_model_version(
    name=MODEL_NAME,
    source=source_uri,
    run_id=pkg_run_id,
    description=f"Best: {best['name']} | accuracy={best['accuracy']:.4f} | f1={best['f1']:.4f}",
    tags={"demo": "MLOps-4phase"},
)
version = mv.version
print(f"  ✅ 버전 생성 완료  version={version}  stage=None")

time.sleep(2)

client.transition_model_version_stage(
    name=MODEL_NAME,
    version=version,
    stage="Staging",
    archive_existing_versions=False,
)
print(f"  ✅ None → Staging")

time.sleep(1)

client.transition_model_version_stage(
    name=MODEL_NAME,
    version=version,
    stage="Production",
    archive_existing_versions=True,
)
print(f"  ✅ Staging → Production")
print(f"\n  → UI 확인: {TRACKING_URI}/#/models/{MODEL_NAME}")

# ─────────────────────────────────────────────────────────────
# Phase 4: 모델 서빙 (Serving)
# ─────────────────────────────────────────────────────────────
print("\n[Phase 4] 모델 배포 및 서빙 (Model Serving)")
print("-" * 40)

# Production 버전 정보 조회
prod_versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
pv = prod_versions[0]
print(f"  Production 모델 정보:")
print(f"    이름    : {pv.name}")
print(f"    버전    : v{pv.version}")
print(f"    스테이지: {pv.current_stage}")
print(f"    run_id  : {pv.run_id[:8]}...")

# 메모리 내 best 모델로 실시간 예측 (서빙 동작 시연)
predictions = best["model"].predict(X_test[:5])
class_names = iris.target_names

print("\n  ✅ 실시간 예측 결과 (샘플 5건):")
for pred, actual in zip(predictions, y_test[:5]):
    mark = "✓" if pred == actual else "✗"
    print(f"    [{mark}] 예측={class_names[pred]:12s} | 실제={class_names[actual]}")

print(f"""
  → 실제 서빙 명령 (서버 터미널):
    source /home/kyobo/mlops-poc/mlfoundry/.venv/bin/activate
    mlflow models serve \\
      -m 'models:/{MODEL_NAME}/Production' \\
      --host 0.0.0.0 --port 7000 --no-conda

  → REST API 호출:
    curl -X POST http://192.168.6.13:7000/invocations \\
      -H 'Content-Type: application/json' \\
      -d '{{"inputs": [[5.1, 3.5, 1.4, 0.2]]}}'
    # 응답 → {{"predictions": [0]}}  (0=setosa)
""")

# ─────────────────────────────────────────────────────────────
# 완료 요약
# ─────────────────────────────────────────────────────────────
print("=" * 60)
print("  MLOps 4단계 시연 완료")
print("=" * 60)
print(f"""
  [Phase 1] Tracking  ✅  실험 {len(candidates)}개, 메트릭·파라미터 기록
  [Phase 2] Projects  ✅  Best Model 패키징, 재현 환경 메타데이터
  [Phase 3] Registry  ✅  v{version} 등록 → Staging → Production 전환
  [Phase 4] Serving   ✅  Production 모델 실시간 예측 확인

  MLflow UI : {TRACKING_URI}
  실험명    : {EXPERIMENT_NAME}
  등록 모델 : {MODEL_NAME}  v{version} (Production)
""")
