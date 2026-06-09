from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserRead(BaseModel):
    id: int
    username: str
    name: str
    role: str

    class Config:
        from_attributes = True
