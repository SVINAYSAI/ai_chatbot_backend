from pydantic import BaseModel
from typing import Optional


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    session_token: Optional[str] = None  # None = new session
    message: str


class ChatResponse(BaseModel):
    session_token: str
    reply: str
    action_taken: Optional[str] = None  # "booked" | "cancelled" | "availability_shown"
    booking_ref: Optional[str] = None
