from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime
from bson import ObjectId

from models.booking import BookingCreate, BookingCancelRequest
from services.booking_service import (
    create_booking_direct, 
    cancel_by_ref, 
    get_booking_by_ref,
    get_user_bookings,
    update_booking_status
)
from services.table_service import check_availability
from db.connection import get_db
from config import settings
from middleware.auth_middleware import get_current_user, get_current_admin

router = APIRouter()


async def get_restaurant():
    """Get the default restaurant"""
    db = get_db()
    restaurant = await db.restaurants.find_one({"_id": ObjectId(settings.RESTAURANT_ID)})
    if not restaurant:
        restaurant = await db.restaurants.find_one()
    return restaurant


@router.post("")
async def create_booking(
    data: BookingCreate,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Create a new booking directly"""
    restaurant = await get_restaurant()
    if not restaurant:
        raise HTTPException(status_code=500, detail="Restaurant not configured")
    
    user_id = current_user.get("sub") if current_user else None
    
    # Convert to dict format expected by service
    booking_data = {
        "name": data.guest_info.name,
        "email": data.guest_info.email,
        "phone": data.guest_info.phone,
        "party_size": data.party_size,
        "date": data.booking_date,
        "time": data.booking_time,
        "special_requests": data.special_requests
    }
    
    result = await create_booking_direct(booking_data, str(restaurant["_id"]), user_id)
    
    if not result.get("success"):
        reason = result.get("reason", "unknown")
        status_code = 400
        if reason == "no_tables_available":
            status_code = 409
        raise HTTPException(status_code=status_code, detail=result)
    
    return result


@router.get("/{booking_ref}")
async def get_booking(booking_ref: str):
    """Get a booking by reference number"""
    booking = await get_booking_by_ref(booking_ref)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Convert ObjectIds to strings
    booking["_id"] = str(booking["_id"])
    if booking.get("restaurant_id"):
        booking["restaurant_id"] = str(booking["restaurant_id"])
    if booking.get("table_id"):
        booking["table_id"] = str(booking["table_id"])
    if booking.get("user_id"):
        booking["user_id"] = str(booking["user_id"])
    if booking.get("chat_session_id"):
        booking["chat_session_id"] = str(booking["chat_session_id"])
    
    return booking


@router.get("/user/me")
async def get_my_bookings(current_user: dict = Depends(get_current_user)):
    """Get all bookings for the logged-in user"""
    user_id = current_user.get("sub")
    bookings = await get_user_bookings(user_id)
    
    # Convert ObjectIds to strings
    for booking in bookings:
        booking["_id"] = str(booking["_id"])
        if booking.get("restaurant_id"):
            booking["restaurant_id"] = str(booking["restaurant_id"])
        if booking.get("table_id"):
            booking["table_id"] = str(booking["table_id"])
        if booking.get("user_id"):
            booking["user_id"] = str(booking["user_id"])
        if booking.get("chat_session_id"):
            booking["chat_session_id"] = str(booking["chat_session_id"])
    
    return {"bookings": bookings}


@router.patch("/{booking_ref}/cancel")
async def cancel_booking(
    booking_ref: str,
    data: BookingCancelRequest
):
    """Cancel a booking by reference number"""
    result = await cancel_by_ref(booking_ref, data.reason, "user")
    
    if not result.get("success"):
        reason = result.get("reason", "unknown")
        status_code = 400
        if reason == "not_found":
            status_code = 404
        elif reason == "already_cancelled":
            status_code = 409
        raise HTTPException(status_code=status_code, detail=result)
    
    return result


@router.get("/availability")
async def check_booking_availability(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    time: Optional[str] = Query(None, description="Time in HH:MM format"),
    party_size: int = Query(..., ge=1, le=50, description="Number of guests")
):
    """Check table availability for a given date/time/party size"""
    restaurant = await get_restaurant()
    if not restaurant:
        raise HTTPException(status_code=500, detail="Restaurant not configured")
    
    # If time not provided, check for all available slots
    if not time:
        # Return available time slots for the date
        db = get_db()
        rules = restaurant.get("booking_rules", {})
        slot_duration = rules.get("slot_duration_minutes", 90)
        
        # Get operating hours for the day
        weekday = datetime.strptime(date, "%Y-%m-%d").strftime("%A").lower()
        operating_hours = restaurant.get("operating_hours", [])
        day_hours = next((h for h in operating_hours if h["day"].lower() == weekday), None)
        
        if not day_hours or not day_hours.get("is_open", False):
            return {"available": False, "reason": "closed", "slots": []}
        
        # Generate time slots
        open_time = day_hours["open_time"]
        close_time = day_hours["last_booking_time"]
        
        # For simplicity, return hourly slots
        slots = []
        current_hour = int(open_time.split(":")[0])
        end_hour = int(close_time.split(":")[0])
        
        for hour in range(current_hour, end_hour + 1):
            time_str = f"{hour:02d}:00"
            result = await check_availability(str(restaurant["_id"]), date, time_str, party_size)
            slots.append({
                "time": time_str,
                "available": result.get("available", False)
            })
        
        return {
            "date": date,
            "party_size": party_size,
            "slots": slots
        }
    
    # Check specific time
    result = await check_availability(str(restaurant["_id"]), date, time, party_size)
    return result
