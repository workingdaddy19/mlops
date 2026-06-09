from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# 시스템 설정 초기값 (DB seed)
SETTINGS_SEED = [
    {
        "key": "MLFLOW_BASE_URL",
        "value": "http://mlflow.mlops.click",
        "label": "MLFlow 접속 URL",
        "group": "mlflow",
    },
    {
        "key": "JUPYTER_BASE_URL",
        "value": "http://jupyterhub.mlops.click",
        "label": "JupyterHub 접속 URL",
        "group": "jupyter",
    },
    {
        "key": "JUPYTER_ENVS",
        "value": '[{"name":"CPU 환경","server":""},{"name":"GPU 환경","server":"gpu"}]',
        "label": "Jupyter 환경 목록 (JSON)",
        "group": "jupyter",
    },
    {
        "key": "ATHENA_DATABASE",
        "value": "mlops",
        "label": "Athena 기본 데이터베이스",
        "group": "athena",
    },
    {
        "key": "ATHENA_S3_OUTPUT",
        "value": "s3://s3-an2-mlops/edwown/",
        "label": "Athena 쿼리 결과 S3 경로",
        "group": "athena",
    },
    {
        "key": "S3_BUCKET_NAME",
        "value": "s3-an2-mlops",
        "label": "S3 버킷명",
        "group": "s3",
    },
    {
        "key": "JUPYTERHUB_ADMIN_TOKEN",
        "value": "",
        "label": "JupyterHub Admin API 토큰",
        "group": "jupyter",
    },
    {
        "key": "ATHENA_REGION",
        "value": "ap-northeast-2",
        "label": "Athena AWS 리전",
        "group": "athena",
    },
    {
        "key": "S3_REGION",
        "value": "ap-northeast-2",
        "label": "S3 AWS 리전",
        "group": "s3",
    },
    {
        "key": "AIRFLOW_BASE_URL",
        "value": "http://airflow.mlops.click",
        "label": "Airflow 접속 URL",
        "group": "airflow",
    },
    {
        "key": "AIRFLOW_USERNAME",
        "value": "admin",
        "label": "Airflow 로그인 계정",
        "group": "airflow",
    },
    {
        "key": "AIRFLOW_PASSWORD",
        "value": "",
        "label": "Airflow 로그인 비밀번호",
        "group": "airflow",
    },
]


class SystemSetting(Base):
    """비민감 시스템 설정 — UI에서 수정 가능, 재배포 불필요."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    group: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
