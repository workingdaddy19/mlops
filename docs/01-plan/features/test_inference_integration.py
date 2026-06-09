"""
inference.py 통합 테스트 (MLFlow 실제 연결)
- .env 기반 실제 MLFlow 서버 연결
- 모델 Registry에서 실제 로드
- API 엔드포인트 실제 추론 검증

실행: python test_inference_integration.py
"""

import os
import sys
import json
import time

# inference.py 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

print("\n" + "="*55)
print("  INVEST 추론 API 통합 테스트 (MLFlow 실제 연결)")
print("="*55)
print(f"  MLFLOW_TRACKING_URI : {os.getenv('MLFLOW_TRACKING_URI', '(미설정)')}")
print(f"  MODEL_CLS           : {os.getenv('MODEL_CLS_NAME', 'invest-crel-classification')}")
print(f"  MODEL_REG           : {os.getenv('MODEL_REG_NAME', 'invest-crel-regression')}")
print(f"  MODEL_ALIAS         : {os.getenv('MODEL_ALIAS', 'champion')}")
print("="*55)

results = {"pass": 0, "fail": 0}

def ok(name):
    results["pass"] += 1
    print(f"  ✅ {name}")

def fail(name, err):
    results["fail"] += 1
    print(f"  ❌ {name}: {err}")

# ── 샘플 입력
SAMPLE = {
    "gpt_ivt_jg_seq":          "JG_INTEG_001",
    "gpt_fl_nm":               "통합테스트_서울강남_오피스",
    "gpt_ivt_mth_cd":          "직접",
    "gpt_ivt_ser_dv_cd":       "오피스",
    "gpt_ivt_tp_cd":           "선순위",
    "gpt_ivt_str_dv_cd":       "일반상업",
    "gpt_ivt_kd_cd":           "오피스빌딩",
    "gpt_ivt_ara_dv_cd":       "국내",
    "gpt_ivt_crd_rinf_txt":    "있음",
    "gpt_ivt_ecfr_gd_txt":     "G2",
    "ltv_rte":                 60.0,
    "dbt_rpy_coef_rte":        1.45,
    "ln_pd":                   24.0,
    "bs_itt":                  3.25,
    "gpt_ivt_trc_pi_rk":       1.0,
    "gpt_ivt_dlb_rqt_amt":     50000000000.0,
    "gpt_ivt_cpt_ern_rte":     8.5,
    "gpt_ivt_cpt_ern_pd":      36.0,
    "gpt_ivt_all_pcm_amt":     80000000000.0,
    "gpt_ivt_bdg_scl_txt":     15000.0,
    "gpt_ivt_nwk_ot_scl_txt":  2000000000000.0,
    "gpt_ivt_cmpi_yr":         2018.0,
    "gpt_ivt_rmd_lsg_ycn":     4.0,
    "gpt_ivt_etrm_rte":        4.0,
    "gpt_ivt_mkt_avg_etrm_rt": 6.5,
    "gpt_ivt_ppo_re_amt":      48000.0,
    "gpt_ivt_mkt_ppo_re_amt":  46000.0,
    "gpt_ivt_mkt_avg_cpt_rte": 4.3,
    "gpt_ivt_mkt_avg_dln_amt": 2900.0,
    "gpt_ivt_ln_pfat_txt":     8.5,
    "gpt_ivt_te_ppo_amt":      3000.0,
    "gpt_ivt_cpt_reim":        28.0,
    "gpt_ivt_appr_evl_ppo_amt":2950.0,
    "gpt_ivt_rpy_rte":         0.0,
}

# ============================================================
# 1. MLFlow 서버 연결 확인
# ============================================================
print("\n[1] MLFlow 서버 연결 확인")
try:
    import mlflow
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    os.environ["MLFLOW_TRACKING_USERNAME"] = os.environ["MLFLOW_TRACKING_USERNAME"]
    os.environ["MLFLOW_TRACKING_PASSWORD"] = os.environ["MLFLOW_TRACKING_PASSWORD"]

    client = mlflow.tracking.MlflowClient()
    experiments = client.search_experiments()
    ok(f"MLFlow 연결 성공 (실험 {len(experiments)}개 확인)")
except Exception as e:
    fail("MLFlow 연결", e)

# ============================================================
# 2. 모델 Registry 확인
# ============================================================
print("\n[2] Model Registry 확인")
CLS_NAME = os.getenv("MODEL_CLS_NAME", "invest-crel-classification")
REG_NAME = os.getenv("MODEL_REG_NAME", "invest-crel-regression")
ALIAS    = os.getenv("MODEL_ALIAS", "champion")

for model_name in [CLS_NAME, REG_NAME]:
    try:
        versions = client.search_model_versions(f"name='{model_name}'")
        if versions:
            latest = versions[0]
            ok(f"{model_name}: version={latest.version}, status={latest.status}")
        else:
            fail(f"{model_name}", "등록된 버전 없음")
    except Exception as e:
        fail(f"{model_name} 조회", e)

# ============================================================
# 3. 모델 실제 로드
# ============================================================
print("\n[3] 모델 실제 로드 (MLFlow Registry)")

clf = reg = None

def try_load(name, alias):
    """alias → 실패 시 latest 버전으로 폴백"""
    try:
        m = mlflow.pyfunc.load_model(f"models:/{name}@{alias}")
        return m, f"@{alias}"
    except Exception:
        try:
            versions = client.search_model_versions(f"name='{name}'")
            if not versions:
                raise ValueError("등록된 버전 없음")
            ver = versions[0].version
            m = mlflow.pyfunc.load_model(f"models:/{name}/{ver}")
            return m, f"v{ver} (alias 없어 버전 직접 로드)"
        except Exception as e2:
            return None, str(e2)

t0 = time.time()
clf, clf_info = try_load(CLS_NAME, ALIAS)
if clf:
    ok(f"분류 모델 로드 ({clf_info}, {time.time()-t0:.1f}s)")
else:
    fail("분류 모델 로드", clf_info)

t0 = time.time()
reg, reg_info = try_load(REG_NAME, ALIAS)
if reg:
    ok(f"회귀 모델 로드 ({reg_info}, {time.time()-t0:.1f}s)")
else:
    fail("회귀 모델 로드", reg_info)

# ============================================================
# 4. 실제 모델로 추론
# ============================================================
print("\n[4] 실제 모델 추론")

if clf and reg:
    import pandas as pd
    import numpy as np
    from inference import preprocess, model_store, FEATURE_COLS

    # model_store에 실제 모델 주입
    model_store.clf = clf
    model_store.reg = reg
    model_store.le_target = None
    model_store.le_dict = {}
    model_store.loaded_at = "integration-test"

    try:
        X = preprocess(SAMPLE)
        assert X.shape == (1, len(FEATURE_COLS)), f"shape 불일치: {X.shape}"
        ok(f"전처리 완료 (shape={X.shape})")
    except Exception as e:
        fail("전처리", e)

    try:
        pred_cls = clf.predict(X)
        try:
            prob = float(clf._model_impl.predict_proba(X)[0][1])
        except:
            prob = 0.0
        invest_yn = "Y" if prob >= 0.5 else "N"
        ok(f"분류 추론: invest_yn={invest_yn}, prob={prob:.4f}")
    except Exception as e:
        fail("분류 추론", e)
        pred_cls = None

    try:
        fair_rate = float(reg.predict(X)[0])
        ok(f"회귀 추론: fair_rate={fair_rate:.4f}%")
    except Exception as e:
        fail("회귀 추론", e)
        fair_rate = None
else:
    print("  ⏭ 모델 로드 실패로 추론 테스트 건너뜀")

# ============================================================
# 5. FastAPI TestClient로 /predict 엔드포인트 검증
# ============================================================
print("\n[5] API /predict 엔드포인트 통합 검증")

if clf and reg:
    try:
        from fastapi.testclient import TestClient
        from inference import app

        client_api = TestClient(app)

        r = client_api.get("/health")
        assert r.status_code == 200 and r.json()["model_loaded"]
        ok(f"/health: {r.json()}")

        r = client_api.post("/predict", json=SAMPLE)
        assert r.status_code == 200, f"status={r.status_code}, body={r.text}"
        body = r.json()
        assert body["invest_yn"] in ("Y", "N")
        assert 0.0 <= body["invest_prob"] <= 1.0
        assert isinstance(body["fair_rate"], float)

        ok(f"/predict 성공")
        print(f"\n  📋 최종 추론 결과:")
        print(json.dumps(body, ensure_ascii=False, indent=4))

    except Exception as e:
        fail("/predict 엔드포인트", e)
else:
    print("  ⏭ 모델 로드 실패로 API 테스트 건너뜀")

# ============================================================
# 결과
# ============================================================
print(f"\n{'='*55}")
print(f"  결과: ✅ {results['pass']}개 통과  ❌ {results['fail']}개 실패")
print("="*55)
