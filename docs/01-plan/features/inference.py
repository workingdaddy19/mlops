# ============================================================
# INVEST 부동산담보대출 투자적격 심사 - 추론 API 서버
# FastAPI + MLFlow Registry 기반
# 배포: EKS Pod (독립 애플리케이션)
# ============================================================

import os
import gc
import json
import logging
import traceback
from datetime import datetime

import boto3
import joblib
import numpy as np
import pandas as pd
import pytz
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

import mlflow
import mlflow.pyfunc
from sklearn.preprocessing import LabelEncoder

# ── 환경 설정
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

KST = pytz.timezone('Asia/Seoul')

MLFLOW_URI     = os.environ["MLFLOW_TRACKING_URI"]
MLFLOW_USER    = os.environ["MLFLOW_TRACKING_USERNAME"]
MLFLOW_PASS    = os.environ["MLFLOW_TRACKING_PASSWORD"]
AWS_REGION     = os.getenv("AWS_REGION", "ap-northeast-2")
S3_BUCKET      = os.getenv("S3_BUCKET", "s3-an2-mlops")
MODEL_CLS_NAME = os.getenv("MODEL_CLS_NAME", "invest-crel-classification")
MODEL_REG_NAME = os.getenv("MODEL_REG_NAME", "invest-crel-regression")
MODEL_ALIAS    = os.getenv("MODEL_ALIAS", "champion")

os.environ["MLFLOW_TRACKING_USERNAME"] = MLFLOW_USER
os.environ["MLFLOW_TRACKING_PASSWORD"] = MLFLOW_PASS
mlflow.set_tracking_uri(MLFLOW_URI)

# ── 피처 정의 (invest_crel_model.ipynb 학습과 동일)
NUMERIC_COLS = [
    "gpt_ivt_trc_pi_rk", "gpt_ivt_dlb_rqt_amt", "ln_pd",
    "ltv_rte", "gpt_ivt_cpt_ern_rte", "gpt_ivt_cpt_ern_pd",
    "gpt_ivt_all_pcm_amt", "gpt_ivt_bdg_scl_txt", "gpt_ivt_nwk_ot_scl_txt",
    "gpt_ivt_cmpi_yr", "dbt_rpy_coef_rte", "gpt_ivt_rmd_lsg_ycn",
    "gpt_ivt_etrm_rte", "gpt_ivt_mkt_avg_etrm_rt",
    "gpt_ivt_ppo_re_amt", "gpt_ivt_mkt_ppo_re_amt",
    "gpt_ivt_mkt_avg_cpt_rte", "gpt_ivt_mkt_avg_dln_amt",
    "gpt_ivt_ln_pfat_txt", "gpt_ivt_te_ppo_amt",
    "gpt_ivt_cpt_reim", "gpt_ivt_appr_evl_ppo_amt",
    "gpt_ivt_rpy_rte", "bs_itt",
]
CAT_COLS = [
    "gpt_ivt_mth_cd", "gpt_ivt_ser_dv_cd", "gpt_ivt_tp_cd",
    "gpt_ivt_str_dv_cd", "gpt_ivt_kd_cd", "gpt_ivt_ara_dv_cd",
    "gpt_ivt_crd_rinf_txt", "gpt_ivt_ecfr_gd_txt",
]
FEATURE_COLS = NUMERIC_COLS + CAT_COLS


# ============================================================
# 모델 스토어 (앱 시작 시 1회 로드 → 메모리 캐싱)
# ============================================================
class ModelStore:
    def __init__(self):
        self.clf = self.reg = self.le_target = None
        self.le_dict = {}
        self.loaded_at = None

    def _uri(self, name):
        return f"models:/{name}@{MODEL_ALIAS}"

    def load(self):
        logger.info("MLFlow 모델 로딩 시작...")
        self.clf = mlflow.pyfunc.load_model(self._uri(MODEL_CLS_NAME))
        self.reg = mlflow.pyfunc.load_model(self._uri(MODEL_REG_NAME))
        self._load_encoders()
        self.loaded_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"모델 로드 완료 ({self.loaded_at})")

    def _load_encoders(self):
        """MLFlow Artifact에 encoders/le_dict.pkl, le_target.pkl이 있으면 로드"""
        try:
            client = mlflow.tracking.MlflowClient()
            ver = client.get_model_version_by_alias(MODEL_CLS_NAME, MODEL_ALIAS)
            path = mlflow.artifacts.download_artifacts(run_id=ver.run_id, artifact_path="encoders")
            self.le_dict   = joblib.load(f"{path}/le_dict.pkl")
            self.le_target = joblib.load(f"{path}/le_target.pkl")
            logger.info("LabelEncoder 로드 완료")
        except Exception:
            logger.warning("LabelEncoder artifact 없음 → 해시 기반 정수 변환 사용")
            self.le_dict = {}
            self.le_target = None

    def reload(self):
        logger.info("핫 리로드 시작...")
        self.load()


model_store = ModelStore()


# ============================================================
# FastAPI 앱
# ============================================================
app = FastAPI(
    title="INVEST 투자적격 심사 추론 API",
    description="부동산담보대출 투자적격판단 + 적정금리평가 모델 서빙",
    version="1.0.0",
)


# ── 요청/응답 스키마
class InferenceRequest(BaseModel):
    gpt_ivt_jg_seq:           str
    gpt_fl_nm:                Optional[str]   = None
    gpt_ivt_mth_cd:           Optional[str]   = None
    gpt_ivt_ser_dv_cd:        Optional[str]   = None
    gpt_ivt_tp_cd:            Optional[str]   = None
    gpt_ivt_str_dv_cd:        Optional[str]   = None
    gpt_ivt_kd_cd:            Optional[str]   = None
    gpt_ivt_ara_dv_cd:        Optional[str]   = None
    gpt_ivt_crd_rinf_txt:     Optional[str]   = None
    gpt_ivt_ecfr_gd_txt:      Optional[str]   = None
    gpt_ivt_trc_pi_rk:        Optional[float] = None
    gpt_ivt_dlb_rqt_amt:      Optional[float] = None
    ln_pd:                    Optional[float] = None
    ltv_rte:                  Optional[float] = None
    gpt_ivt_cpt_ern_rte:      Optional[float] = None
    gpt_ivt_cpt_ern_pd:       Optional[float] = None
    gpt_ivt_all_pcm_amt:      Optional[float] = None
    gpt_ivt_bdg_scl_txt:      Optional[float] = None
    gpt_ivt_nwk_ot_scl_txt:   Optional[float] = None
    gpt_ivt_cmpi_yr:          Optional[float] = None
    dbt_rpy_coef_rte:         Optional[float] = None
    gpt_ivt_rmd_lsg_ycn:      Optional[float] = None
    gpt_ivt_etrm_rte:         Optional[float] = None
    gpt_ivt_mkt_avg_etrm_rt:  Optional[float] = None
    gpt_ivt_ppo_re_amt:       Optional[float] = None
    gpt_ivt_mkt_ppo_re_amt:   Optional[float] = None
    gpt_ivt_mkt_avg_cpt_rte:  Optional[float] = None
    gpt_ivt_mkt_avg_dln_amt:  Optional[float] = None
    gpt_ivt_ln_pfat_txt:      Optional[float] = None
    gpt_ivt_te_ppo_amt:       Optional[float] = None
    gpt_ivt_cpt_reim:         Optional[float] = None
    gpt_ivt_appr_evl_ppo_amt: Optional[float] = None
    gpt_ivt_rpy_rte:          Optional[float] = None
    bs_itt:                   Optional[float] = None


class InferenceResponse(BaseModel):
    request_id:      str
    gpt_ivt_jg_seq:  str
    invest_yn:       str    # Y / N
    invest_prob:     float  # 승인 확률 (0~1)
    fair_rate:       float  # 적정 금리 (%)
    cls_model:       str
    reg_model:       str
    inferred_at:     str


# ── 전처리
def preprocess(data: dict) -> pd.DataFrame:
    df = pd.DataFrame([data])

    # 누락 컬럼 0으로 초기화 (요청에 없는 피처 안전 처리)
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0

    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df[NUMERIC_COLS] = df[NUMERIC_COLS].fillna(0)  # 실운영: 학습셋 중앙값 주입 권장

    for col in CAT_COLS:
        raw = df[col].iloc[0]
        val = str(raw) if raw is not None else "UNKNOWN"
        if col in model_store.le_dict:
            le = model_store.le_dict[col]
            val = val if val in le.classes_ else le.classes_[0]
            df[col] = le.transform([val])
        else:
            df[col] = hash(val) % 100

    return df[FEATURE_COLS]


def _s3_log(request_id: str, stage: str, status: str, data: dict):
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        yyyymmdd = datetime.now(KST).strftime("%Y%m%d")
        key = f"invest-model-result/LOG/{yyyymmdd}/{request_id}_{stage}_{status}.json".upper()
        body = json.dumps({"request_id": request_id, "stage": stage, "status": status,
                           "timestamp": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"), **data},
                          ensure_ascii=False, indent=2)
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=body)
    except Exception as e:
        logger.warning(f"S3 로그 실패: {e}")


# ── 엔드포인트

@app.on_event("startup")
async def startup():
    model_store.load()


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model_store.clf is not None, "loaded_at": model_store.loaded_at}


@app.get("/model/info")
def model_info():
    return {"mlflow_uri": MLFLOW_URI, "cls_model": MODEL_CLS_NAME,
            "reg_model": MODEL_REG_NAME, "alias": MODEL_ALIAS, "loaded_at": model_store.loaded_at}


@app.post("/model/reload")
def model_reload():
    """champion alias 변경 후 재배포 없이 새 버전 로드"""
    try:
        model_store.reload()
        return {"status": "reloaded", "loaded_at": model_store.loaded_at}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict", response_model=InferenceResponse)
def predict(req: InferenceRequest):
    request_id = datetime.now(KST).strftime("%Y%m%d%H%M%S%f")
    logger.info(f"[{request_id}] 추론 요청: {req.gpt_ivt_jg_seq}")
    _s3_log(request_id, "inference", "start", {"gpt_ivt_jg_seq": req.gpt_ivt_jg_seq})

    try:
        if model_store.clf is None:
            raise HTTPException(status_code=503, detail="모델 미로드 상태")

        X = preprocess(req.dict())

        cls_pred  = model_store.clf.predict(X)
        try:
            invest_prob = float(model_store.clf._model_impl.predict_proba(X)[0][1])
        except Exception:
            invest_prob = 0.0

        invest_yn = (model_store.le_target.inverse_transform(cls_pred)[0]
                     if model_store.le_target else ("Y" if invest_prob >= 0.5 else "N"))

        fair_rate = float(model_store.reg.predict(X)[0])

        result = {
            "request_id":     request_id,
            "gpt_ivt_jg_seq": req.gpt_ivt_jg_seq,
            "invest_yn":      invest_yn,
            "invest_prob":    round(invest_prob, 4),
            "fair_rate":      round(fair_rate, 4),
            "cls_model":      f"{MODEL_CLS_NAME}@{MODEL_ALIAS}",
            "reg_model":      f"{MODEL_REG_NAME}@{MODEL_ALIAS}",
            "inferred_at":    datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        }
        _s3_log(request_id, "inference", "success", result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        _s3_log(request_id, "inference", "error",
                {"error_message": str(e), "stack_trace": traceback.format_exc()})
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("inference:app", host="0.0.0.0", port=8080, reload=False)
