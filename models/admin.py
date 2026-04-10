from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str  # "super_admin" | "manager" | "staff"
    permissions: Optional[List[str]] = None


class AdminUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AdminResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    permissions: List[str]
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
