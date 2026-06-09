import logging
import re
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from sqlalchemy.orm import Session
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_FORBIDDEN = re.compile(
    r"\b(DROP|TRUNCATE|DELETE\s+FROM|ALTER|CREATE|INSERT|UPDATE)\b",
    re.IGNORECASE,
)


class AthenaService:
    def __init__(self, db: Session | None = None):
        settings = get_settings()
        if db is not None:
            from app.services.settings_service import SettingsService
            svc = SettingsService(db)
            athena_region = svc.get("ATHENA_REGION", settings.athena_region)
            self.database = svc.get("ATHENA_DATABASE", settings.athena_database)
            self.output_location = svc.get("ATHENA_S3_OUTPUT", settings.athena_s3_output)
        else:
            athena_region = settings.athena_region
            self.database = settings.athena_database
            self.output_location = settings.athena_s3_output
        self.region = athena_region
        self.client = boto3.client("athena", region_name=athena_region)

    def execute_query(self, sql: str, max_rows: int = 500) -> dict:
        """Athena SELECT 쿼리 실행 (동기 방식, 최대 60초 대기)"""
        sql_stripped = sql.strip().rstrip(";")

        if _FORBIDDEN.search(sql_stripped):
            raise ValueError("DDL/DML 쿼리는 허용되지 않습니다. SELECT만 사용 가능합니다.")

        try:
            # 1. 쿼리 제출
            response = self.client.start_query_execution(
                QueryString=sql_stripped,
                QueryExecutionContext={"Database": self.database},
                ResultConfiguration={"OutputLocation": self.output_location},
            )
            query_id = response["QueryExecutionId"]
            logger.info(f"Athena query submitted: {query_id}")

            # 2. 완료 대기 (polling 0.5초 간격, 최대 60초)
            for attempt in range(120):
                status = self._get_status(query_id)
                if status["state"] == "SUCCEEDED":
                    break
                if status["state"] in ("FAILED", "CANCELLED"):
                    reason = status.get("reason", "알 수 없는 오류")
                    raise ValueError(f"Athena 쿼리 실패: {reason}")
                time.sleep(0.5)
            else:
                raise TimeoutError("Athena 쿼리 타임아웃 (60초 초과)")

            # 3. 결과 조회
            return self._fetch_results(query_id, max_rows)

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Athena boto3 error: {e}")
            raise ConnectionError(f"AWS Athena 연결 오류: {e}") from e

    def _get_status(self, query_id: str) -> dict:
        resp = self.client.get_query_execution(QueryExecutionId=query_id)
        status = resp["QueryExecution"]["Status"]
        return {
            "state": status["State"],
            "reason": status.get("StateChangeReason", ""),
        }

    def _fetch_results(self, query_id: str, max_rows: int) -> dict:
        paginator = self.client.get_paginator("get_query_results")
        pages = paginator.paginate(
            QueryExecutionId=query_id,
            PaginationConfig={"MaxItems": max_rows + 1},
        )
        columns: list[str] = []
        rows: list[list] = []
        first_page = True

        for page in pages:
            result_rows = page["ResultSet"]["Rows"]
            if first_page:
                columns = [c.get("VarCharValue", "") for c in result_rows[0]["Data"]]
                result_rows = result_rows[1:]  # 헤더 행 제거
                first_page = False
            for row in result_rows:
                rows.append([c.get("VarCharValue", None) for c in row["Data"]])

        truncated = len(rows) > max_rows
        trimmed = rows[:max_rows]
        return {
            "columns": columns,
            "rows": trimmed,
            "row_count": len(trimmed),
            "truncated": truncated,
        }

    def list_databases(self) -> list[dict]:
        """Athena 데이터베이스 및 테이블 목록 조회"""
        try:
            resp = self.client.list_databases(CatalogName="AwsDataCatalog")
            result = []
            for db in resp.get("DatabaseList", []):
                db_name = db["Name"]
                tables, error = self._list_tables(db_name)
                entry = {"database": db_name, "tables": tables}
                if error:
                    entry["table_error"] = error
                result.append(entry)
            return result
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Athena list_databases error: {e}")
            raise ConnectionError(f"AWS Athena 연결 오류: {e}") from e

    def _list_tables(self, database: str) -> tuple[list[str], str | None]:
        """Glue GetTables API로 테이블 목록 조회 (glue:GetTables 권한 필요)"""
        try:
            glue = boto3.client("glue", region_name=self.region)
            tables: list[str] = []
            paginator = glue.get_paginator("get_tables")
            for page in paginator.paginate(DatabaseName=database):
                tables.extend(t["Name"] for t in page.get("TableList", []))
            return tables, None
        except (BotoCoreError, ClientError) as e:
            error_msg = str(e)
            logger.warning(f"glue.get_tables({database}) failed: {error_msg}")
            return [], error_msg
        except Exception as e:
            logger.warning(f"Failed to list tables for {database}: {e}")
            return [], str(e)

