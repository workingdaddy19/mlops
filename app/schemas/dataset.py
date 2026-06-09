from datetime import datetime

from pydantic import BaseModel


class DatasetFeatureCreate(BaseModel):
    column_name: str
    data_type: str
    description: str | None = None
    is_nullable: bool = True


class DatasetFeatureRead(BaseModel):
    id: int
    column_name: str
    data_type: str
    description: str | None
    is_nullable: bool

    class Config:
        from_attributes = True


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    source_type: str = "table"
    source_name: str
    record_count: int | None = None
    features: list[DatasetFeatureCreate] = []


class DatasetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    record_count: int | None = None


class DatasetRead(BaseModel):
    id: int
    name: str
    description: str | None
    source_type: str
    source_name: str
    record_count: int | None
    owner: str
    created_at: datetime
    updated_at: datetime
    features: list[DatasetFeatureRead] = []

    class Config:
        from_attributes = True
