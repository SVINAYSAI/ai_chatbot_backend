from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Address(BaseModel):
    street: str
    city: str
    state: str
    zip: str
    country: str


class Contact(BaseModel):
    phone: str
    email: str
    website: Optional[str] = None


class OperatingHours(BaseModel):
    day: str  # "monday", "tuesday", ... "sunday"
    is_open: bool
    open_time: str  # "11:00" (24h format)
    close_time: str  # "23:00"
    last_booking_time: str  # "22:00"


class BookingRules(BaseModel):
    min_party_size: int = 1
    max_party_size: int = 20
    slot_duration_minutes: int = 90
    advance_booking_days: int = 30
    cancellation_cutoff_hours: int = 2


class RestaurantCreate(BaseModel):
    name: str
    slug: str
    address: Address
    contact: Contact
    operating_hours: List[OperatingHours]
    booking_rules: BookingRules


class RestaurantUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[Address] = None
    contact: Optional[Contact] = None
    operating_hours: Optional[List[OperatingHours]] = None
    booking_rules: Optional[BookingRules] = None
    ai_system_prompt_override: Optional[str] = None


class RestaurantResponse(BaseModel):
    id: str
    name: str
    slug: str
    address: Address
    contact: Contact
    operating_hours: List[OperatingHours]
    booking_rules: BookingRules
    ai_system_prompt_override: Optional[str]
    created_at: datetime
    updated_at: datetime
