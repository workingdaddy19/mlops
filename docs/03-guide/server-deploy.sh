#!/bin/bash
# =============================================================
# MLFoundry 포털 — 서버 배포 스크립트
# 실행 위치: EC2 서버  /home/mlops_user/mlops
# 실행 전제: 소스코드가 이미 /home/mlops_user/mlops 에 압축 해제됨
# 실행 방법: chmod +x server-deploy.sh && ./server-deploy.sh
# =============================================================
set -euo pipefail

# ─── 변수 설정 ───────────────────────────────────────────────
AWS_ACCOUNT="891376975666"
AWS_REGION="ap-northeast-2"
ECR_REPO="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/mlops/app"
IMAGE_TAG="latest"
NAMESPACE="mlops"
DEPLOY_NAME="mlops"
SOURCE_DIR="/home/mlops_user/mlops"

echo "============================================="
echo "  MLFoundry 배포 시작 $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================="

# ─── STEP 1: ECR 로그인 ──────────────────────────────────────
echo ""
echo "[1/6] ECR 로그인 중..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REPO}"

# ─── STEP 2: Docker 이미지 빌드 ──────────────────────────────
echo ""
echo "[2/6] Docker 이미지 빌드 중..."
cd "${SOURCE_DIR}"
docker build -t "${ECR_REPO}:${IMAGE_TAG}" .

echo "  빌드 완료: ${ECR_REPO}:${IMAGE_TAG}"

# ─── STEP 3: ECR 푸시 ────────────────────────────────────────
echo ""
echo "[3/6] ECR 푸시 중..."
docker push "${ECR_REPO}:${IMAGE_TAG}"
echo "  푸시 완료"

# ─── STEP 4: Namespace 확인 / 생성 ───────────────────────────
echo ""
echo "[4/6] Namespace 확인..."
if ! kubectl get namespace "${NAMESPACE}" &>/dev/null; then
  echo "  Namespace '${NAMESPACE}' 없음 → 생성"
  kubectl create namespace "${NAMESPACE}"
else
  echo "  Namespace '${NAMESPACE}' 존재 확인"
fi

# ─── STEP 5: K8s 리소스 적용 ─────────────────────────────────
echo ""
echo "[5/6] K8s 리소스 적용..."
cd "${SOURCE_DIR}"

echo "  → Secret 적용"
kubectl apply -f k8s/backend-secret.yaml

echo "  → Deployment 적용"
kubectl apply -f k8s/backend-deployment.yaml

echo "  → Service 적용"
kubectl apply -f k8s/backend-service.yaml

echo "  → Ingress 적용"
kubectl apply -f k8s/backend-ingress.yaml

# ─── STEP 6: 롤링 재시작 & 상태 확인 ────────────────────────
echo ""
echo "[6/6] 롤링 재시작..."
kubectl rollout restart deployment/"${DEPLOY_NAME}" -n "${NAMESPACE}"

echo ""
echo "  배포 완료 대기 (최대 3분)..."
kubectl rollout status deployment/"${DEPLOY_NAME}" -n "${NAMESPACE}" --timeout=180s

echo ""
echo "============================================="
echo "  배포 완료! 상태 확인:"
echo "============================================="
kubectl get pods -n "${NAMESPACE}" -l app="${DEPLOY_NAME}"
echo ""
echo "  Ingress 주소:"
kubectl get ingress -n "${NAMESPACE}"
