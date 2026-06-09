from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetFeature


class DatasetRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_all(self, offset: int = 0, limit: int = 50) -> tuple[list[Dataset], int]:
        query = self.session.query(Dataset)
        total = query.count()
        items = query.order_by(Dataset.id.desc()).offset(offset).limit(limit).all()
        return items, total

    def get_by_id(self, dataset_id: int) -> Dataset | None:
        return self.session.get(Dataset, dataset_id)

    def get_by_name(self, name: str) -> Dataset | None:
        return self.session.query(Dataset).filter(Dataset.name == name).first()

    def create(self, dataset: Dataset) -> Dataset:
        self.session.add(dataset)
        self.session.commit()
        self.session.refresh(dataset)
        return dataset

    def update(self, dataset: Dataset) -> Dataset:
        self.session.commit()
        self.session.refresh(dataset)
        return dataset

    def delete(self, dataset: Dataset) -> None:
        self.session.delete(dataset)
        self.session.commit()
