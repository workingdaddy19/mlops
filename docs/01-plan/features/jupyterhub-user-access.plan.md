# JupyterHub 개인별 접속 환경 구축 Plan (v2)

> **Summary**: 사용자 동적 관리 + 버튼 클릭 시 on-demand 토큰 발급으로 개인별 JupyterLab 원클릭 접속
>
> **Project**: MLFoundry (AI 데이터 분석 플랫폼)
> **Version**: 2.0
> **Author**: Claude Code
> **Date**: 2026-05-27
> **Status**: Draft

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | 사용자를 코드에 하드코딩하면 매 배포 필요. 토큰을 페이지 로드 시 발급하면 클릭 전 만료 위험 |
| **Solution** | 사용자는 Admin API/스크립트로 동적 생성. 토큰은 "접속" 버튼 클릭 순간 on-demand 발급 후 새 탭 열기 |
| **Function/UX Effect** | 관리자가 UI에서 사용자 추가 가능. 사용자는 접속 버튼 클릭 → 즉시 발급된 토큰으로 Lab 열림 |
| **Core Value** | 배포 없이 사용자 관리 + 항상 신선한(fresh) 토큰으로 안정적 JupyterHub 접속 |

---

## 1. 설계 원칙 (개선 이유)

### ❌ 기존 방식의 문제

```
문제 1: 사용자 하드코딩
  auth_service.py ensure_default_users() 에 계정 추가
  → 사람 늘어날 때마다 코드 수정 + Docker 빌드 + ECR 푸시 + kubectl rollout

문제 2: 페이지 로드 시 토큰 발급
  GET /api/jupyter/envs → 토큰 발급 → URL에 포함 → 카드 표시
  → 사용자가 30분 후 클릭하면 토큰 만료(1시간이지만 UX 불안정)
  → 탭을 열어두기만 해도 토큰이 낭비됨
```

### ✅ 개선 방식

```
개선 1: 동적 사용자 관리
  방법 A (즉시): scripts/add_users.py 스크립트 → EC2 또는 kubectl exec으로 실행
  방법 B (장기): Admin 페이지에서 UI로 사용자 추가/삭제

개선 2: 클릭 시 on-demand 토큰 발급
  페이지 로드: GET /api/jupyter/envs → 환경 목록만 반환 (토큰 없음)
  버튼 클릭: GET /api/jupyter/token?server={server} → 토큰 발급 → URL 완성 → window.open()
```

---

## 2. 아키텍처

### 2.1 토큰 발급 흐름 (개선 후)

```
[페이지 로드]
  GET /api/jupyter/envs
  → Response: [{name:"CPU 환경", server:""}, {name:"GPU 환경", server:"gpu"}]
  → 카드 표시 (URL/토큰 없음, "접속" 버튼만)

[접속 버튼 클릭]
  → 버튼 비활성화 + "🔄 연결 중..." 표시
  → GET /api/jupyter/token?server=  (또는 server=gpu)
  → 백엔드: POST /hub/api/users/{username}/tokens  ← 이 순간 발급
  → Response: {url: "http://jupyterhub.mlops.click/user/{username}/lab/?token=xxx"}
  → window.open(url, '_blank')  ← 새 탭으로 즉시 열림
  → 버튼 복원
```

### 2.2 사용자 관리 흐름

```
[즉시 적용] scripts/add_users.py
  python scripts/add_users.py 09930269 09930269  # username password
  python scripts/add_users.py 09929689 09929689

  또는 kubectl exec으로 Pod 내에서 실행:
  kubectl exec -n mlops -it <pod> -- python scripts/add_users.py 09930269 09930269

[장기] Admin UI (별도 Phase)
  /admin/users 페이지 → 사용자 추가/삭제
```

---

## 3. 구현 범위

### Phase 1 — 사용자 추가 스크립트 (신규)

**`scripts/add_users.py`** 생성:
```python
# 실행 예: python scripts/add_users.py 09930269 09930269
# DB에 사용자를 동적으로 추가 (배포 없이)
```

- `ensure_default_users()`는 그대로 유지 (admin/user 기본 계정만)
- 추가 사용자는 스크립트로 관리

### Phase 2 — on-demand 토큰 API (신규 엔드포인트)

**`app/api/routes/jupyter.py`** — 엔드포인트 추가:
```
GET /api/jupyter/token?server={server_name}
  → 현재 로그인 사용자의 JupyterHub 토큰 즉시 발급
  → Response: {"url": "http://jupyterhub.../user/{username}/lab/?token=xxx"}
```

**`app/services/jupyter_service.py`** — 메서드 추가:
```python
async def get_token_url(self, username: str, server: str = "") -> str:
    """클릭 시 즉시 토큰 발급 후 URL 반환"""
    token = await self._get_user_token(username)
    if server:
        url = f"{self.base_url}/user/{username}/{server}/lab/"
    else:
        url = f"{self.base_url}/user/{username}/lab/"
    if token:
        url += f"?token={token}"
    return url
```

### Phase 3 — 프론트엔드 수정

**`app/templates/pages/jupyter.html`** — 카드 버튼 동작 변경:
```
기존: 카드 로드 시 URL에 토큰 포함 → href로 연결
변경: 버튼 클릭 시 API 호출 → 토큰 발급 → window.open()
```

```javascript
// 접속 버튼 클릭 핸들러
async function openLab(server, btn) {
  btn.disabled = true;
  btn.textContent = '🔄 연결 중...';
  try {
    const res = await apiFetch(`/api/jupyter/token?server=${encodeURIComponent(server)}`);
    const data = await res.json();
    window.open(data.url, '_blank');
  } catch (e) {
    alert('접속 URL 생성에 실패했습니다.');
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 접속';
  }
}
```

### Phase 4 — k8s Secret 업데이트 (운영)

```yaml
JUPYTERHUB_ADMIN_TOKEN: "admin_hub_token_발급_후_입력"
```

> `JUPYTERHUB_ADMIN_TOKEN`은 **사용자 토큰이 아니라 서버 서비스 계정 토큰**입니다.
> 사용자가 늘어나도 이 값은 변경 불필요. admin 한 번만 발급 → 영구 사용.

---

## 4. 파일 변경 목록

| 파일 | 변경 내용 | 유형 |
|------|-----------|------|
| `scripts/add_users.py` | 사용자 동적 추가 스크립트 | 신규 |
| `app/services/jupyter_service.py` | `get_token_url()` 메서드 추가 | 수정 |
| `app/api/routes/jupyter.py` | `GET /token` 엔드포인트 추가 | 수정 |
| `app/templates/pages/jupyter.html` | 버튼 클릭 시 on-demand 토큰 발급 | 수정 |
| `k8s/backend-secret.yaml` | `JUPYTERHUB_ADMIN_TOKEN` 값 입력 | 운영 |

> **변경 없는 파일**: `auth_service.py` (하드코딩 추가 안 함), `ensure_default_users()` 유지

---

## 5. 운영 절차 (배포 없이 사용자 추가)

### 최초 1회: JupyterHub Admin 토큰 발급

```bash
# 브라우저
http://jupyterhub.mlops.click/hub/token
→ admin/admin 로그인 → Request Token → 복사

# 검증 (admin 권한 확인)
curl -H "Authorization: token 복사한_토큰" \
  http://jupyterhub.mlops.click/hub/api/users
# → 사용자 목록 JSON 오면 성공

# k8s secret 업데이트
kubectl patch secret backend-secret -n mlops \
  --type=merge -p '{"stringData":{"JUPYTERHUB_ADMIN_TOKEN":"복사한_토큰"}}'
kubectl rollout restart deployment/mlops -n mlops
```

### 신규 사용자 추가 (배포 없이)

```bash
# EC2 서버에서
python scripts/add_users.py 09930269 09930269
python scripts/add_users.py 09929689 09929689

# 또는 kubectl exec으로 pod 내에서
kubectl exec -n mlops -it $(kubectl get pod -n mlops -l app=mlops -o jsonpath='{.items[0].metadata.name}') \
  -- python scripts/add_users.py 09930269 09930269
```

---

## 6. 완료 기준

- [ ] `09930269`으로 Portal 로그인 성공 (스크립트로 추가)
- [ ] `09929689`으로 Portal 로그인 성공
- [ ] ML Analysis 페이지 로드 시 카드만 표시 (토큰 없음, URL 없음)
- [ ] "접속" 클릭 → `🔄 연결 중...` → 새 탭으로 JupyterLab 열림
- [ ] 신규 사용자 추가 시 코드 수정/재배포 불필요

---

## 7. 토큰 종류 정리 (혼동 방지)

| 구분 | JUPYTERHUB_ADMIN_TOKEN | 사용자 접속 토큰 |
|------|------------------------|-----------------|
| 용도 | 백엔드가 JupyterHub API 호출 시 인증 | 사용자가 Lab에 로그인 없이 접속 |
| 만료 | **없음 (영구)** | 1시간 |
| 저장 위치 | k8s Secret (1회 설정) | 저장 안 함 (버튼 클릭 시 발급 후 URL에만 사용) |
| 갱신 필요 | 없음 | 사용자가 버튼 클릭할 때 자동 재발급 |
| 수동 작업 | 최초 1회 `/hub/token`에서 발급 | 불필요 (자동) |

> Secret에 저장하는 건 영구 admin 토큰 딱 하나. 1시간짜리 사용자 토큰은 코드가 API로 자동 발급.

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-05-27 | 초기 계획 (하드코딩 방식) | Claude Code |
| 2.0 | 2026-05-27 | 동적 사용자 관리 + on-demand 토큰 발급으로 개선 | Claude Code |
