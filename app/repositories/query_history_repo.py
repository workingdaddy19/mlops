from sqlalchemy.orm import Session

from app.models.query_history import DataQueryHistory


class QueryHistoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, history: DataQueryHistory) -> DataQueryHistory:
        self.session.add(history)
        self.session.commit()
        self.session.refresh(history)
        return history

    def list_by_user(self, username: str, limit: int = 50) -> list[DataQueryHistory]:
        return (
            self.session.query(DataQueryHistory)
            .filter(DataQueryHistory.username == username)
            .order_by(DataQueryHistory.id.desc())
            .limit(limit)
            .all()
        )
