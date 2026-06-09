# 서버 배포 단계별 가이드

> 소스코드가 이미 `/home/mlops_user/mlops` 에 압축 해제된 상태에서 실행합니다.

---

## 사전 확인사항

```bash
# 소스 위치 확인
ls /home/mlops_user/mlops
# app/  k8s/  Dockerfile  requirements.txt  ...

# kubectl 작동 확인
kubectl get nodes

# aws cli 작동 확인
aws sts get-caller-identity
```

---

## STEP 0 — DB 마이그레이션 (신규 테이블, 최초 1회만)

> `system_settings` 테이블이 없으면 설정 저장/조회가 실패합니다.

```bash
# RDS에 system_settings 테이블 생성
psql \
  -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
  -U mlops \
  -d mlops \
  -f /home/mlops_user/mlops/k8s/rds/03-system-settings.sql

# 비밀번호: kyobo11!

# 확인 (테이블 & 시드 데이터)
psql -h rds-an2-avb-poc-mlops.cza602u202u8.ap-northeast-2.rds.amazonaws.com \
  -U mlops -d mlops \
  -c "SELECT key, label, \"group\" FROM system_settings ORDER BY \"group\";"
```

---

## STEP 1 — ECR 로그인

```bash
AWS_ACCOUNT="891376975666"
AWS_REGION="ap-northeast-2"
ECR_REPO="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/mlops/app"

aws ecr get-login-password --region ${AWS_REGION} \
  | docker login --username AWS --password-stdin ${ECR_REPO}
# Login Succeeded
```

---

## STEP 2 — Docker 이미지 빌드

```bash
cd /home/mlops_user/mlops

docker build -t ${ECR_REPO}:latest .

# 빌드 확인
docker images | grep mlops
```

---

## STEP 3 — ECR 푸시

```bash
docker push ${ECR_REPO}:latest
```

---

## STEP 4 — Namespace 확인 (최초 1회)

```bash
# namespace가 없으면 생성
kubectl get namespace mlops 2>/dev/null \
  || kubectl create namespace mlops
```

---

## STEP 5 — K8s 리소스 적용

```bash
cd /home/mlops_user/mlops

# ① Secret 먼저 (env 값 적용)
kubectl apply -f k8s/backend-secret.yaml

# ② Deployment
kubectl apply -f k8s/backend-deployment.yaml

# ③ Service
kubectl apply -f k8s/backend-service.yaml

# ④ Ingress (ALB)
kubectl apply -f k8s/backend-ingress.yaml
```

---

## STEP 6 — 롤링 재시작

> 이미 Deployment가 떠 있고 이미지만 새로 올렸을 경우 재시작이 필요합니다.

```bash
kubectl rollout restart deployment/mlops -n mlops

# 배포 완료 대기 (최대 3분)
kubectl rollout status deployment/mlops -n mlops --timeout=180s
```

---

## STEP 7 — 상태 확인

```bash
# Pod 상태
kubectl get pods -n mlops -l app=mlops

# Pod 로그 (최근 50줄)
kubectl logs -n mlops -l app=mlops --tail=50

# Ingress 주소 확인 (ALB DNS)
kubectl get ingress -n mlops

# 헬스체크
ALB_DNS=$(kubectl get ingress -n mlops mlops-external-ingress \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
curl http://${ALB_DNS}/health
```

---

## 자주 쓰는 운영 명령

```bash
# Pod 내부 접속
kubectl exec -n mlops -it \
  $(kubectl get pod -n mlops -l app=mlops -o jsonpath='{.items[0].metadata.name}') \
  -- bash

# 사용자 추가
kubectl exec -n mlops -it \
  $(kubectl get pod -n mlops -l app=mlops -o jsonpath='{.items[0].metadata.name}') \
  -- python scripts/add_users.py <사용자ID> <비밀번호>

# Secret 업데이트 후 재시작
kubectl apply -f k8s/backend-secret.yaml
kubectl rollout restart deployment/mlops -n mlops

# Pod 강제 재시작 (단일)
kubectl delete pod -n mlops -l app=mlops

# 이전 버전으로 롤백
kubectl rollout undo deployment/mlops -n mlops
```

---

## 원클릭 배포 (스크립트)

```bash
cd /home/mlops_user/mlops
chmod +x docs/03-guide/server-deploy.sh
./docs/03-guide/server-deploy.sh
```

---

## 문제 해결

### Pod가 CrashLoopBackOff 상태

```bash
# 상세 로그 확인
kubectl logs -n mlops <pod-name> --previous

# 자주 발생하는 원인:
# 1. DB 연결 실패 → backend-secret.yaml의 DB_HOST/DB_PASSWORD 확인
# 2. system_settings 테이블 없음 → STEP 0 실행
# 3. 이미지 Pull 실패 → ECR 권한 확인 (IRSA 또는 imagePullSecrets)
```

### Ingress에 ADDRESS가 없을 때 (ALB 생성 안됨)

```bash
# AWS Load Balancer Controller 확인
kubectl get pods -n kube-system | grep aws-load-balancer

# Ingress 이벤트 확인
kubectl describe ingress mlops-external-ingress -n mlops
```

### 설정값 변경 (재배포 불필요)

```
1. 포털 admin 계정으로 로그인
2. Management > Settings 이동
3. 값 수정 후 저장 → 즉시 반영
```
