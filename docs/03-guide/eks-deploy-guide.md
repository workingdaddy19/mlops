# EKS mlops 네임스페이스 배포 가이드

> EC2(ip-10-1-0-86)에서 순서대로 실행하세요.
> AWS Account: 891376975666 | Region: ap-northeast-2 | Namespace: mlops

---

## 사전 작업 (Windows PC에서)

### Step 0-1. RDS 접속 정보를 secret 파일에 입력 (Windows에서)

`k8s/backend-secret.yaml` 파일을 열어 아래 항목을 실제 값으로 수정:

```
DB_HOST          → RDS 엔드포인트 주소
DB_PASSWORD      → RDS 비밀번호
MLFLOW_BASE_URL  → 클라우드팀에서 받은 MLflow 서비스 주소
JUPYTER_BASE_URL → 클라우드팀에서 받은 Jupyter 서비스 주소
```

> SECRET_KEY는 앱 내부 기본값을 사용하므로 별도 발급 불필요.

### Step 0-2. 소스코드를 EC2로 전송 (Windows PowerShell에서)

```powershell
# 프로젝트 폴더를 zip으로 압축
Compress-Archive -Path "D:\ADT\workspace\mlfoundry_260429\*" `
  -DestinationPath "D:\ADT\workspace\mlfoundry_260429.zip" `
  -CompressionLevel Optimal

# EC2로 전송 (pem 키 경로는 본인 것으로 수정)
scp -i "C:\path\to\your-key.pem" `
  "D:\ADT\workspace\mlfoundry_260429.zip" `
  mlops_user@10.1.0.86:~/
```

---

## EC2에서 실행 (아래부터 EC2 터미널에 복붙)

### Step 1. EC2 접속 후 소스 압축 해제

```bash
cd ~
unzip mlfoundry_260429.zip -d mlfoundry_260429
cd mlfoundry_260429
```

### Step 2. Docker 설치 여부 확인

```bash
docker --version
```

Docker가 없으면 설치:
```bash
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
newgrp docker
```

### Step 3. AWS CLI 확인 및 ECR 레포지토리 생성

```bash
# AWS 자격증명 확인
aws sts get-caller-identity

# ECR 레포지토리 생성 (없는 경우에만 실행)
aws ecr create-repository \
  --repository-name mlfoundry-backend \
  --region ap-northeast-2
```

레포지토리가 이미 있으면 아래 오류 무시:
`RepositoryAlreadyExistsException`

### Step 4. Docker 이미지 빌드 & ECR 푸시

```bash
cd ~/mlfoundry_260429
chmod +x build_and_push.sh
./build_and_push.sh
```

성공 시 출력:
```
>>> 1. ECR 로그인 중...
Login Succeeded
>>> 2. Docker 이미지 빌드 중...
>>> 3. ECR 태그 설정 중...
>>> 4. ECR에 이미지 푸시 중...
>>> 완료! 이제 k8s 매니페스트를 적용하세요.
```

### Step 5. Kubernetes Secret 적용

```bash
kubectl apply -f k8s/backend-secret.yaml -n mlops
```

확인:
```bash
kubectl get secret backend-secret -n mlops
```

### Step 6. Deployment & Service 적용

```bash
kubectl apply -f k8s/backend-deployment.yaml -n mlops
kubectl apply -f k8s/backend-service.yaml -n mlops
```

### Step 7. 배포 상태 확인

```bash
# Pod 상태 확인 (Running이 될 때까지 대기)
kubectl get pods -n mlops -w

# 상태가 Running이면 Ctrl+C로 종료 후 아래 명령 실행
kubectl describe pod -l app=mlfoundry-backend -n mlops
```

정상 상태:
```
NAME                                  READY   STATUS    RESTARTS
mlfoundry-backend-xxxxxxxxx-xxxxx     1/1     Running   0
```

### Step 8. API 동작 확인 (port-forward)

```bash
kubectl port-forward svc/mlfoundry-backend 6080:6080 -n mlops &

# 헬스체크
curl http://localhost:6080/health

# 예상 응답
# {"status":"ok","service":"MLFoundry"}

# API 문서 확인
curl -I http://localhost:6080/docs
```

---

## 문제 발생 시 디버깅

### Pod가 CrashLoopBackOff인 경우
```bash
kubectl logs -l app=mlfoundry-backend -n mlops --tail=50
```

### ErrImagePull인 경우 (ECR 인증 실패)
```bash
# IRSA 미사용 시: ECR 인증 시크릿 생성
aws ecr get-login-password --region ap-northeast-2 | \
  kubectl create secret docker-registry ecr-registry-secret \
  --docker-server=891376975666.dkr.ecr.ap-northeast-2.amazonaws.com \
  --docker-username=AWS \
  --docker-password=$(aws ecr get-login-password --region ap-northeast-2) \
  -n mlops

# deployment.yaml의 imagePullSecrets 주석 해제 후 재적용
kubectl apply -f k8s/backend-deployment.yaml -n mlops
```

### DB 연결 실패인 경우
```bash
# Secret 값 확인 (base64 디코딩)
kubectl get secret backend-secret -n mlops -o jsonpath='{.data.DB_HOST}' | base64 -d
kubectl get secret backend-secret -n mlops -o jsonpath='{.data.DB_HOST}' | base64 -d
```

### 리소스 초기화 (처음부터 다시)
```bash
kubectl delete -f k8s/ -n mlops
# 수정 후 다시 apply
kubectl apply -f k8s/ -n mlops
```

---

## 배포 완료 후 확인 체크리스트

- [ ] `kubectl get pods -n mlops` → STATUS = Running, READY = 1/1
- [ ] `curl http://localhost:6080/health` → `{"status":"ok"}`
- [ ] `curl http://localhost:6080/docs` → HTTP 200
- [ ] 로그에 DB 연결 오류 없음: `kubectl logs -l app=mlfoundry-backend -n mlops`
