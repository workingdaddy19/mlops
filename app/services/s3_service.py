import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from sqlalchemy.orm import Session
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self, db: Session | None = None):
        settings = get_settings()
        if db is not None:
            from app.services.settings_service import SettingsService
            svc = SettingsService(db)
            s3_region = svc.get("S3_REGION", settings.s3_region)
            self.bucket = svc.get("S3_BUCKET_NAME", settings.s3_bucket_name)
        else:
            s3_region = settings.s3_region
            self.bucket = settings.s3_bucket_name
        self.s3 = boto3.client("s3", region_name=s3_region)

    def browse(self, prefix: str = "") -> dict:
        """
        S3 버켓 탐색 — 현재 prefix의 폴더와 파일 목록 반환
        Returns: {"bucket": str, "prefix": str, "folders": [...], "files": [...]}
        """
        # prefix 정규화: 빈 문자열이 아닌 경우 '/'로 끝나도록
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        try:
            resp = self.s3.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                Delimiter="/",
                MaxKeys=1000,
            )
        except (BotoCoreError, ClientError) as e:
            logger.error(f"S3 browse error: {e}")
            raise ConnectionError(f"AWS S3 연결 오류: {e}") from e

        folders = []
        for cp in resp.get("CommonPrefixes", []):
            folder_key = cp["Prefix"]
            # 폴더 이름: prefix를 제거하고 끝의 '/' 제거
            folder_name = folder_key[len(prefix):].rstrip("/")
            if folder_name:
                folders.append({
                    "name": folder_name,
                    "prefix": folder_key,
                    "type": "folder",
                })

        files = []
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key == prefix:  # prefix 자체(디렉토리 마커)는 제외
                continue
            name = key[len(prefix):]
            if not name or "/" in name:  # 하위 폴더 내부 항목 제외
                continue
            files.append({
                "name": name,
                "key": key,
                "size": obj["Size"],
                "size_display": self._format_size(obj["Size"]),
                "last_modified": obj["LastModified"].strftime("%Y-%m-%d %H:%M"),
                "type": "file",
            })

        return {
            "bucket": self.bucket,
            "prefix": prefix,
            "folders": folders,
            "files": files,
        }

    def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """파일 다운로드용 Presigned URL 생성 (기본 1시간)"""
        try:
            url = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except (BotoCoreError, ClientError) as e:
            logger.error(f"S3 presigned URL error: {e}")
            raise ConnectionError(f"AWS S3 URL 생성 오류: {e}") from e

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
