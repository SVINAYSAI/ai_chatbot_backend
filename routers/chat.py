from fastapi import APIRouter, HTTPException, Depends, Request
from models.chat import ChatRequest, ChatResponse
from services.chat_service import process_chat_message, get_session_history, clear_session
from db.connection import get_db
from config import settings
from bson import ObjectId

router = APIRouter()


async def get_restaurant():
    """Get the default restaurant"""
    db = get_db()
    restaurant = await db.restaurants.find_one({"_id": ObjectId(settings.RESTAURANT_ID)})
    if not restaurant:
        # Try to get any restaurant
        restaurant = await db.restaurants.find_one()
    return restaurant


@router.post("/message", response_model=ChatResponse)
async def send_message(
    data: ChatRequest,
    request: Request
):
    """Send a message to the chatbot and get a response"""
    # Get AI provider from app state
    ai_provider = request.app.state.ai_provider
    
    # Get restaurant
    restaurant = await get_restaurant()
    if not restaurant:
        raise HTTPException(status_code=500, detail="Restaurant not configured")
    
    # Process message
    result = await process_chat_message(
        session_token=data.session_token,
        message=data.message,
        ai_provider=ai_provider,
        restaurant=restaurant
    )
    
    return ChatResponse(**result)


@router.get("/session/{session_token}")
async def get_session(session_token: str):
    """Get full chat session history"""
    session = await get_session_history(session_token)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Convert ObjectIds to strings
    session["_id"] = str(session["_id"])
    if session.get("restaurant_id"):
        session["restaurant_id"] = str(session["restaurant_id"])
    if session.get("user_id"):
        session["user_id"] = str(session["user_id"])
    if session.get("booking_id"):
        session["booking_id"] = str(session["booking_id"])
    
    return session


@router.delete("/session/{session_token}")
async def delete_session(session_token: str):
    """Clear/reset a chat session"""
    success = await clear_session(session_token)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"message": "Session cleared"}
