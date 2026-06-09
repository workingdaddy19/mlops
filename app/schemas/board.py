from datetime import datetime

from pydantic import BaseModel


class BoardCreate(BaseModel):
    board_type: str = "notice"
    title: str
    content: str


class BoardUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class BoardFileRead(BaseModel):
    id: int
    original_name: str
    stored_name: str
    file_size: int

    class Config:
        from_attributes = True


class BoardRead(BaseModel):
    id: int
    board_type: str
    title: str
    content: str
    author: str
    view_count: int
    created_at: datetime
    updated_at: datetime
    files: list[BoardFileRead] = []

    class Config:
        from_attributes = True


class BoardListItem(BaseModel):
    id: int
    board_type: str
    title: str
    author: str
    view_count: int
    created_at: datetime

    class Config:
        from_attributes = True
