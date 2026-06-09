# JupyterHub 관리자 요청 사항: True SSO (자동 로그인) 연동

MLFoundry 포털에서 JupyterLab 접속 시 사용자에게 다시 로그인 창이 뜨지 않도록(True SSO) JupyterHub 측에 JWT 기반 인증 연동을 요청합니다.

## 1. 개요
* **목적**: MLFoundry 포털 로그인 세션을 이용해 JupyterHub 로그인 창 없이 즉시 접속 (True SSO)
* **방식**: 포털에서 서명한 JWT를 JupyterHub의 JWT Authenticator가 검증하여 세션 발급

## 2. 작업 요청 사항

### 2.1 패키지 설치
JupyterHub 구동 환경(컨테이너/서버)에 아래 패키지 설치가 필요합니다.
```bash
pip install jupyterhub-jwtauthenticator
```

### 2.2 jupyterhub_config.py 설정 추가
`jupyterhub_config.py` 파일에 다음 설정을 추가해 주시기 바랍니다.

```python
# JWT Authenticator 활성화
c.JupyterHub.authenticator_class = 'jwtauthenticator.jwtauthenticator.JSONWebTokenAuthenticator'

# 포털과 공유할 강력한 비밀키 (임의 지정 가능, 변경 시 포털 측에 공유 필요)
# 주의: 이 비밀키는 외부에 노출되지 않도록 K8s Secret 등으로 관리하는 것을 권장합니다.
c.JSONWebTokenAuthenticator.secret = 'mlops-jupyterhub-jwt-secret-key'

# JWT에서 사용자 식별자로 사용할 필드명
c.JSONWebTokenAuthenticator.username_claim_field = 'username'

# URL Query Parameter로 JWT를 전달받을 수 있도록 허용
c.JSONWebTokenAuthenticator.param_name = 'token'

# (옵션) 사용자가 없으면 자동 생성하도록 허용 (필요 시)
c.JSONWebTokenAuthenticator.create_system_users = True
```

## 3. 검증 방법
설정이 반영되고 JupyterHub Pod가 재시작되면, MLFoundry 포털 내에서 `[JupyterLab 접속]` 버튼 클릭 시 로그인 창을 거치지 않고 바로 JupyterLab 환경으로 진입하게 됩니다.
