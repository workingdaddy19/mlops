import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.query_history import DataQueryHistory
from app.repositories.query_history_repo import QueryHistoryRepository
from app.schemas.query import QueryHistoryRead, QueryResult, SchemaInfo

_FORBIDDEN = re.compile(
    r"\b(DROP|TRUNCATE|DELETE\s+FROM|ALTER|CREATE|INSERT|UPDATE)\b",
    re.IGNORECASE,
)


class QueryService:
    def __init__(self, session: Session, history_repo: QueryHistoryRepository):
        self.session = session
        self.history_repo = history_repo

    def execute_query(self, sql: str, username: str, max_rows: int = 500) -> QueryResult:
        sql_stripped = sql.strip().rstrip(";")
        if _FORBIDDEN.search(sql_stripped):
            self._save_history(username, sql_stripped, status="error", error="DDL/DML 쿼리는 허용되지 않습니다.")
            raise ValueError("DDL/DML 쿼리는 허용되지 않습니다. SELECT만 사용 가능합니다.")

        try:
            result = self.session.execute(text(sql_stripped))
            columns = list(result.keys())
            all_rows = result.fetchmany(max_rows + 1)
            truncated = len(all_rows) > max_rows
            rows = [list(r) for r in all_rows[:max_rows]]
            self._save_history(username, sql_stripped, row_count=len(rows))
            return QueryResult(columns=columns, rows=rows, row_count=len(rows), truncated=truncated)
        except Exception as e:
            self._save_history(username, sql_stripped, status="error", error=str(e))
            raise

    def get_schemas(self) -> list[SchemaInfo]:
        result = self.session.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        schemas = []
        for (table_name,) in result:
            cols_result = self.session.execute(text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t "
                "ORDER BY ordinal_position"
            ), {"t": table_name})
            columns = [
                {"name": r[0], "type": r[1], "nullable": r[2]}
                for r in cols_result
            ]
            schemas.append(SchemaInfo(table_name=table_name, columns=columns))
        return schemas

    def get_history(self, username: str) -> list[QueryHistoryRead]:
        items = self.history_repo.list_by_user(username)
        return [QueryHistoryRead.model_validate(h) for h in items]

    def _save_history(self, username: str, sql: str, row_count: int | None = None,
                      status: str = "success", error: str | None = None) -> None:
        history = DataQueryHistory(
            username=username, sql_text=sql, row_count=row_count,
            status=status, error_message=error,
        )
        self.history_repo.create(history)
