from datetime import datetime

from pydantic import BaseModel


class QueryRequest(BaseModel):
    sql: str
    max_rows: int = 500


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool = False


class QueryHistoryRead(BaseModel):
    id: int
    sql_text: str
    row_count: int | None
    status: str
    error_message: str | None
    executed_at: datetime

    class Config:
        from_attributes = True


class SchemaInfo(BaseModel):
    table_name: str
    columns: list[dict]


# Athena 전용 스키마
class AthenaQueryRequest(BaseModel):
    sql: str
    max_rows: int = 500
    database: str | None = None  # None이면 config 기본 DB 사용


class AthenaTableInfo(BaseModel):
    database: str
    tables: list[str]
    table_error: str | None = None  # glue:GetTables 실패 시 오류 메시지

