#!/bin/bash
set -e

# ==========================================
# AWS ECR 설정 (본인의 환경에 맞게 수정하세요)
# ==========================================
AWS_REGION="ap-northeast-2"           # 예: ap-northeast-2
AWS_ACCOUNT_ID="891376975666"        # AWS 계정 ID
REPO_NAME="mlops/app"                    # ECR 레포지토리 이름
IMAGE_TAG="latest"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}"

echo ">>> 1. ECR 로그인 중..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

echo ">>> 2. Docker 이미지 빌드 중..."
docker build --no-cache -t ${REPO_NAME}:${IMAGE_TAG} .

echo ">>> 3. ECR 태그 설정 중..."
docker tag ${REPO_NAME}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}

echo ">>> 4. ECR에 이미지 푸시 중..."
docker push ${ECR_URI}:${IMAGE_TAG}

echo ">>> 완료! 이제 k8s 매니페스트를 적용하세요."
