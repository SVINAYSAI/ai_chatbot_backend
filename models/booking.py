from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, datetime


class GuestInfo(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None


class BookingCreate(BaseModel):
    guest_info: GuestInfo
    party_size: int
    booking_date: str  # "YYYY-MM-DD"
    booking_time: str  # "HH:MM"
    special_requests: Optional[str] = None
    source: str = "chatbot"


class BookingResponse(BaseModel):
    id: str
    booking_ref: str
    table_number: str
    status: str
    booking_datetime: datetime
    guest_info: GuestInfo
    party_size: int
    special_requests: Optional[str]


class BookingCancelRequest(BaseModel):
    reason: Optional[str] = None


class AvailabilityRequest(BaseModel):
    date: str  # "YYYY-MM-DD"
    time: Optional[str] = None  # "HH:MM" - optional for checking all slots
    party_size: int
