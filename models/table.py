from pydantic import BaseModel
from typing import Optional, List


class TableCreate(BaseModel):
    table_number: str
    label: str
    capacity: int
    min_capacity: int = 1
    location: str  # "indoor" | "outdoor" | "bar" | "private"
    features: List[str] = []
    notes: Optional[str] = None


class TableUpdate(BaseModel):
    label: Optional[str] = None
    capacity: Optional[int] = None
    min_capacity: Optional[int] = None
    location: Optional[str] = None
    features: Optional[List[str]] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None
    notes: Optional[str] = None
