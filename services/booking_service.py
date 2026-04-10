import random
import string
import re
import json
from db.connection import get_db
from services.table_service import find_available_tables
from services.email_service import send_booking_confirmation, send_cancellation_email, log_notification
from datetime import datetime, timedelta
from bson import ObjectId


def generate_booking_ref() -> str:
    """Generate a unique human-readable booking reference"""
    date_part = datetime.utcnow().strftime("%Y%m%d")
    rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"BK-{date_part}-{rand_part}"


def parse_json_from_response(text: str) -> dict:
    """Try to extract JSON block from AI response"""
    # Look for JSON in code blocks
    patterns = [
        r'```json\s*(.*?)\s*```',  # ```json ... ```
        r'```\s*(\{.*?\})\s*```',  # ``` { ... } ```
        r'(\{[\s\S]*?"action"[\s\S]*?\})'  # Raw JSON with action key
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    # Try parsing the whole text as JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    return None


async def create_booking_from_chat(data: dict, session_id: str, restaurant: dict) -> dict:
    """Create a booking from chat-collected data"""
    db = get_db()
    rules = restaurant.get("booking_rules", {})
    
    # 1. Parse date and time
    try:
        booking_dt = datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M")
    except (KeyError, ValueError) as e:
        return {"success": False, "reason": "invalid_datetime", "error": str(e)}
    
    end_dt = booking_dt + timedelta(minutes=rules.get("slot_duration_minutes", 90))
    
    # 2. Validate: not in the past
    if booking_dt < datetime.utcnow():
        return {"success": False, "reason": "past_datetime"}
    
    # 3. Validate: within advance booking window
    max_dt = datetime.utcnow() + timedelta(days=rules.get("advance_booking_days", 30))
    if booking_dt > max_dt:
        return {"success": False, "reason": "too_far_ahead"}
    
    # 4. Validate: operating hours
    weekday = booking_dt.strftime("%A").lower()
    operating_hours = restaurant.get("operating_hours", [])
    day_hours = next((h for h in operating_hours if h["day"].lower() == weekday), None)
    
    if not day_hours or not day_hours.get("is_open", False):
        return {"success": False, "reason": "closed"}
    
    last_booking_time = day_hours.get("last_booking_time", day_hours.get("close_time", "23:59"))
    if data['time'] > last_booking_time:
        return {"success": False, "reason": "after_last_booking_time"}
    
    # 5. Validate: party size
    party_size = data.get("party_size", 1)
    if party_size < rules.get("min_party_size", 1) or party_size > rules.get("max_party_size", 20):
        return {"success": False, "reason": "invalid_party_size"}
    
    # 6. Find available tables
    available = await find_available_tables(
        db, restaurant["_id"], party_size, booking_dt, rules.get("slot_duration_minutes", 90)
    )
    if not available:
        return {"success": False, "reason": "no_tables_available"}
    
    # 7. Pick best-fit table (smallest capacity that fits party)
    table = min(available, key=lambda t: t["capacity"])
    
    # 8. Generate unique booking ref
    booking_ref = generate_booking_ref()
    
    # Ensure uniqueness
    existing = await db.bookings.find_one({"booking_ref": booking_ref})
    while existing:
        booking_ref = generate_booking_ref()
        existing = await db.bookings.find_one({"booking_ref": booking_ref})
    
    # 9. Insert booking
    booking_doc = {
        "booking_ref": booking_ref,
        "restaurant_id": restaurant["_id"],
        "table_id": table["_id"],
        "table_number": table["table_number"],
        "user_id": None,
        "guest_info": {
            "name": data["name"],
            "email": data["email"],
            "phone": data.get("phone")
        },
        "party_size": party_size,
        "booking_date": booking_dt.date().isoformat(),
        "booking_time": data["time"],
        "booking_datetime": booking_dt,
        "end_datetime": end_dt,
        "status": "confirmed",
        "status_history": [{"status": "confirmed", "changed_at": datetime.utcnow(), "changed_by": "system"}],
        "special_requests": data.get("special_requests", ""),
        "source": "chatbot",
        "chat_session_id": ObjectId(session_id) if session_id else None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.bookings.insert_one(booking_doc)
    booking_id = str(result.inserted_id)
    
    # Update chat session with booking_id
    if session_id:
        await db.chat_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"booking_id": result.inserted_id, "status": "completed"}}
        )
    
    # 10. Send confirmation email (fire and forget)
    try:
        email_sent = await send_booking_confirmation(
            to_email=data["email"],
            name=data["name"],
            booking_ref=booking_ref,
            date=data["date"],
            time=data["time"],
            party_size=party_size,
            table_number=table["table_number"],
            restaurant_name=restaurant["name"]
        )
        await log_notification(
            booking_id=booking_id,
            recipient_email=data["email"],
            notif_type="booking_confirmation",
            status="sent" if email_sent else "failed"
        )
    except Exception as e:
        print(f"[Booking] Failed to send confirmation email: {e}")
        await log_notification(
            booking_id=booking_id,
            recipient_email=data["email"],
            notif_type="booking_confirmation",
            status="failed",
            error_message=str(e)
        )
    
    return {
        "success": True,
        "booking_ref": booking_ref,
        "table_number": table["table_number"],
        "booking_id": booking_id
    }


async def create_booking_direct(data: dict, restaurant_id: str, user_id: str = None) -> dict:
    """Create a booking directly (from API, not chat)"""
    db = get_db()
    
    restaurant = await db.restaurants.find_one({"_id": ObjectId(restaurant_id)})
    if not restaurant:
        return {"success": False, "reason": "restaurant_not_found"}
    
    # Add source
    data["source"] = "api" if user_id else "website"
    
    # Create a temporary session for tracking
    session_doc = {
        "restaurant_id": ObjectId(restaurant_id),
        "session_token": generate_booking_ref(),  # Use as temp token
        "user_id": ObjectId(user_id) if user_id else None,
        "status": "completed",
        "intent": "book",
        "collected_data": data,
        "messages": [],
        "started_at": datetime.utcnow(),
        "last_message_at": datetime.utcnow(),
        "completed_at": datetime.utcnow()
    }
    
    session_result = await db.chat_sessions.insert_one(session_doc)
    
    result = await create_booking_from_chat(data, str(session_result.inserted_id), restaurant)
    
    # Update user_id if provided
    if user_id and result.get("success"):
        await db.bookings.update_one(
            {"booking_ref": result["booking_ref"]},
            {"$set": {"user_id": ObjectId(user_id)}}
        )
    
    return result


async def cancel_by_ref(booking_ref: str, reason: str = None, cancelled_by: str = "user") -> dict:
    """Cancel a booking by reference number"""
    db = get_db()
    booking = await db.bookings.find_one({"booking_ref": booking_ref})
    
    if not booking:
        return {"success": False, "reason": "not_found"}
    
    if booking["status"] == "cancelled":
        return {"success": False, "reason": "already_cancelled"}
    
    if booking["status"] == "completed":
        return {"success": False, "reason": "already_completed"}
    
    # Check cancellation cutoff
    restaurant = await db.restaurants.find_one({"_id": booking["restaurant_id"]})
    rules = restaurant.get("booking_rules", {}) if restaurant else {}
    cutoff_hours = rules.get("cancellation_cutoff_hours", 2)
    
    booking_dt = booking["booking_datetime"]
    cutoff_time = booking_dt - timedelta(hours=cutoff_hours)
    
    if datetime.utcnow() > cutoff_time and booking["status"] == "confirmed":
        return {"success": False, "reason": "past_cancellation_cutoff"}
    
    # Update booking
    await db.bookings.update_one(
        {"booking_ref": booking_ref},
        {"$set": {
            "status": "cancelled",
            "cancellation_reason": reason,
            "cancelled_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        "$push": {
            "status_history": {"status": "cancelled", "changed_at": datetime.utcnow(), "changed_by": cancelled_by}
        }}
    )
    
    # Send cancellation email
    try:
        await send_cancellation_email(
            to_email=booking["guest_info"]["email"],
            name=booking["guest_info"]["name"],
            booking_ref=booking_ref,
            restaurant_name=restaurant["name"] if restaurant else "The Restaurant"
        )
        await log_notification(
            booking_id=str(booking["_id"]),
            recipient_email=booking["guest_info"]["email"],
            notif_type="booking_cancellation",
            status="sent"
        )
    except Exception as e:
        print(f"[Booking] Failed to send cancellation email: {e}")
        await log_notification(
            booking_id=str(booking["_id"]),
            recipient_email=booking["guest_info"]["email"],
            notif_type="booking_cancellation",
            status="failed",
            error_message=str(e)
        )
    
    return {"success": True}


async def cancel_by_email(email: str, booking_datetime_str: str, reason: str = None) -> dict:
    """Cancel a booking by email and datetime"""
    db = get_db()
    
    try:
        booking_dt = datetime.strptime(booking_datetime_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return {"success": False, "reason": "invalid_datetime_format"}
    
    # Find booking by email and datetime
    booking = await db.bookings.find_one({
        "guest_info.email": email,
        "booking_datetime": booking_dt,
        "status": {"$in": ["confirmed", "pending"]}
    })
    
    if not booking:
        return {"success": False, "reason": "not_found"}
    
    return await cancel_by_ref(booking["booking_ref"], reason)


async def update_booking_status(booking_ref: str, new_status: str, changed_by: str = "admin") -> dict:
    """Update booking status (admin only)"""
    db = get_db()
    
    booking = await db.bookings.find_one({"booking_ref": booking_ref})
    if not booking:
        return {"success": False, "reason": "not_found"}
    
    valid_statuses = ["pending", "confirmed", "cancelled", "completed", "no_show"]
    if new_status not in valid_statuses:
        return {"success": False, "reason": "invalid_status"}
    
    await db.bookings.update_one(
        {"booking_ref": booking_ref},
        {"$set": {
            "status": new_status,
            "updated_at": datetime.utcnow()
        },
        "$push": {
            "status_history": {"status": new_status, "changed_at": datetime.utcnow(), "changed_by": changed_by}
        }}
    )
    
    return {"success": True}


async def get_booking_by_ref(booking_ref: str) -> dict:
    """Get booking by reference"""
    db = get_db()
    booking = await db.bookings.find_one({"booking_ref": booking_ref})
    return booking


async def get_user_bookings(user_id: str) -> list:
    """Get all bookings for a user"""
    db = get_db()
    bookings = await db.bookings.find({
        "user_id": ObjectId(user_id)
    }).sort("booking_datetime", -1).to_list(length=100)
    return bookings
