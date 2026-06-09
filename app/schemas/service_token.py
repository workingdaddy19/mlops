from datetime import datetime

from pydantic import BaseModel


class ServiceTokenResponse(BaseModel):
    id: int
    user_id: int
    service: str
    token: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
