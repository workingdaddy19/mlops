from app.models.dataset import Dataset, DatasetFeature
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.dataset import DatasetCreate, DatasetRead, DatasetUpdate


class DatasetService:
    def __init__(self, repo: DatasetRepository):
        self.repo = repo

    def list_datasets(self, page: int = 1, size: int = 50) -> tuple[list[DatasetRead], int]:
        offset = (page - 1) * size
        items, total = self.repo.list_all(offset, size)
        return [DatasetRead.model_validate(d) for d in items], total

    def get_dataset(self, dataset_id: int) -> DatasetRead:
        ds = self.repo.get_by_id(dataset_id)
        if ds is None:
            raise ValueError("데이터셋을 찾을 수 없습니다.")
        return DatasetRead.model_validate(ds)

    def create_dataset(self, data: DatasetCreate, owner: str) -> DatasetRead:
        ds = Dataset(
            name=data.name,
            description=data.description,
            source_type=data.source_type,
            source_name=data.source_name,
            record_count=data.record_count,
            owner=owner,
        )
        for f in data.features:
            ds.features.append(DatasetFeature(
                column_name=f.column_name,
                data_type=f.data_type,
                description=f.description,
                is_nullable=f.is_nullable,
            ))
        ds = self.repo.create(ds)
        return DatasetRead.model_validate(ds)

    def update_dataset(self, dataset_id: int, data: DatasetUpdate, requester: str) -> DatasetRead:
        ds = self.repo.get_by_id(dataset_id)
        if ds is None:
            raise ValueError("데이터셋을 찾을 수 없습니다.")
        if ds.owner != requester:
            raise PermissionError("수정 권한이 없습니다.")
        if data.name is not None:
            ds.name = data.name
        if data.description is not None:
            ds.description = data.description
        if data.record_count is not None:
            ds.record_count = data.record_count
        ds = self.repo.update(ds)
        return DatasetRead.model_validate(ds)

    def delete_dataset(self, dataset_id: int) -> None:
        ds = self.repo.get_by_id(dataset_id)
        if ds is None:
            raise ValueError("데이터셋을 찾을 수 없습니다.")
        self.repo.delete(ds)
