from pydantic import BaseModel, EmailStr
from datetime import date
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    role: Optional[str] = "employee"

class User(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str

    class Config:
        from_attributes = True


class LeaveCreate(BaseModel):
    date_from: date
    date_to: date
    comment: Optional[str] = None

class Leave(BaseModel):
    id: int
    user_id: int
    date_from: date
    date_to: date
    comment: Optional[str]

    class Config:
        from_attributes = True

