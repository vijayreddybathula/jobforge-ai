from pydantic import BaseModel, EmailStr
from uuid import UUID, uuid4
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserRead(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: Optional[bool] = True

    class Config:
        orm_mode = True


class UserRead(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: Optional[str] = None

    class Config:
        orm_mode = True
