import uuid
import json
from datetime import datetime
from bson import ObjectId
from db.connection import get_db
from ai.system_prompt import build_system_prompt
from services.booking_service import create_booking_from_chat, cancel_by_ref, cancel_by_email, parse_json_from_response
from services.table_service import check_availability


async def get_or_create_session(session_token: str = None, restaurant_id: str = None) -> tuple:
    """Get existing session or create new one"""
    db = get_db()
    
    if session_token:
        session = await db.chat_sessions.find_one({"session_token": session_token})
        if session:
            return session, False
    
    # Create new session
    new_token = str(uuid.uuid4())
    session_doc = {
        "restaurant_id": ObjectId(restaurant_id) if restaurant_id else None,
        "session_token": new_token,
        "user_id": None,
        "booking_id": None,
        "status": "active",
        "intent": "unknown",
        "collected_data": {},
        "messages": [],
        "ai_provider": None,
        "started_at": datetime.utcnow(),
        "last_message_at": datetime.utcnow(),
        "completed_at": None
    }
    
    result = await db.chat_sessions.insert_one(session_doc)
    session_doc["_id"] = result.inserted_id
    return session_doc, True


async def add_message_to_session(session_id: str, role: str, content: str, provider_used: str = None):
    """Add a message to the session history"""
    db = get_db()
    
    message_doc = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow(),
        "provider_used": provider_used
    }
    
    await db.chat_sessions.update_one(
        {"_id": ObjectId(session_id)},
        {
            "$push": {"messages": message_doc},
            "$set": {"last_message_at": datetime.utcnow()}
        }
    )


async def process_chat_message(
    session_token: str,
    message: str,
    ai_provider,
    restaurant: dict
) -> dict:
    """Process a chat message and return response"""
    db = get_db()
    
    # Get or create session
    session, is_new = await get_or_create_session(
        session_token, 
        str(restaurant["_id"]) if restaurant else None
    )
    
    # Add user message
    await add_message_to_session(str(session["_id"]), "user", message)
    
    # Build system prompt
    rules = restaurant.get("booking_rules", {}) if restaurant else {}
    hours = restaurant.get("operating_hours", []) if restaurant else []
    
    # Format hours summary
    hours_summary = ""
    if hours:
        days_open = [h for h in hours if h.get("is_open")]
        if days_open:
            hours_summary = ", ".join([
                f"{h['day'][:3].title()}: {h['open_time']}-{h['close_time']}"
                for h in days_open
            ])
    
    rules["hours_summary"] = hours_summary
    
    prompt_override = restaurant.get("ai_system_prompt_override") if restaurant else None
    system_prompt = build_system_prompt(
        restaurant.get("name", "The Restaurant") if restaurant else "The Restaurant",
        rules,
        prompt_override
    )
    
    # Get message history
    messages = session.get("messages", [])
    
    # Call AI — only pass role+content; strip MongoDB datetime fields.
    # The session object was fetched before the user message was persisted,
    # so we must append the current message manually to avoid an empty list.
    try:
        ai_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        ai_messages.append({"role": "user", "content": message})
        ai_response = await ai_provider.chat(ai_messages, system_prompt)
        provider_name = ai_provider.provider_name
    except Exception as e:
        print(f"[Chat] AI provider error: {e}")
        ai_response = "I'm sorry, I'm having trouble processing your request right now. Please try again in a moment."
        provider_name = "error"
    
    # Parse AI response for JSON action
    action_result = None
    reply_text = ai_response
    action_taken = None
    booking_ref = None
    
    json_action = parse_json_from_response(ai_response)
    
    if json_action and "action" in json_action:
        action = json_action.get("action")
        
        if action == "book":
            # Validate required fields
            required = ["name", "email", "date", "time", "party_size"]
            if all(k in json_action for k in required):
                action_result = await create_booking_from_chat(
                    json_action,
                    str(session["_id"]),
                    restaurant
                )
                if action_result.get("success"):
                    action_taken = "booked"
                    booking_ref = action_result.get("booking_ref")
                    reply_text = f"Perfect! Your booking is confirmed. Reference: {booking_ref}. You'll receive a confirmation email shortly."
                else:
                    reason = action_result.get("reason", "unknown")
                    reason_messages = {
                        "past_datetime": "I can't book a table in the past. Please choose a future date and time.",
                        "too_far_ahead": f"Bookings can only be made up to {rules.get('advance_booking_days', 30)} days in advance.",
                        "closed": "Sorry, we're closed on that day or time. Please check our operating hours.",
                        "after_last_booking_time": "Sorry, that time is after our last booking time for the day.",
                        "invalid_party_size": f"Party size must be between {rules.get('min_party_size', 1)} and {rules.get('max_party_size', 20)}.",
                        "no_tables_available": "Sorry, no tables are available for that date and time. Would you like to try a different time?",
                        "invalid_datetime": "I didn't understand the date or time. Could you please provide it in a clearer format?"
                    }
                    reply_text = reason_messages.get(reason, f"Sorry, I couldn't complete the booking. Reason: {reason}")
            else:
                missing = [k for k in required if k not in json_action]
                reply_text = f"I need a bit more information to complete your booking. Could you please provide: {', '.join(missing)}?"
        
        elif action == "cancel":
            booking_ref = json_action.get("booking_ref")
            if booking_ref:
                action_result = await cancel_by_ref(booking_ref)
                if action_result.get("success"):
                    action_taken = "cancelled"
                    reply_text = f"Your booking {booking_ref} has been cancelled. You should receive a confirmation email shortly."
                else:
                    reason = action_result.get("reason", "unknown")
                    reason_messages = {
                        "not_found": "I couldn't find a booking with that reference number. Please double-check and try again.",
                        "already_cancelled": "That booking has already been cancelled.",
                        "already_completed": "That booking has already been completed.",
                        "past_cancellation_cutoff": "Sorry, it's too close to the booking time to cancel online. Please call the restaurant directly."
                    }
                    reply_text = reason_messages.get(reason, f"Sorry, I couldn't cancel the booking. Reason: {reason}")
            else:
                reply_text = "To cancel a booking, I'll need your booking reference number (starts with BK-)."
        
        elif action == "cancel_by_email":
            email = json_action.get("email")
            booking_datetime = json_action.get("booking_datetime")
            if email and booking_datetime:
                action_result = await cancel_by_email(email, booking_datetime)
                if action_result.get("success"):
                    action_taken = "cancelled"
                    reply_text = "Your booking has been cancelled. You should receive a confirmation email shortly."
                else:
                    reply_text = "I couldn't find a booking with that email and date/time. Please check your details and try again."
            else:
                reply_text = "To cancel by email, I'll need both your email address and the booking date/time."
        
        elif action == "check_availability":
            date = json_action.get("date")
            time = json_action.get("time")
            party_size = json_action.get("party_size")
            
            if date and party_size:
                if not time:
                    # Just check if date is generally available
                    reply_text = f"Let me check availability for {date} for {party_size} guests..."
                else:
                    result = await check_availability(
                        str(restaurant["_id"]),
                        date,
                        time,
                        party_size
                    )
                    if result.get("available"):
                        table = result.get("suggested_table", {})
                        reply_text = f"Great news! We have availability on {date} at {time} for {party_size} guests. I can reserve {table.get('label', 'a table')} ({table.get('capacity')} seats) for you. Would you like to proceed with the booking?"
                    else:
                        reason = result.get("reason", "")
                        if reason == "no_tables_available":
                            reply_text = f"Sorry, we don't have any tables available on {date} at {time} for {party_size} guests. Would you like to try a different time?"
                        elif reason == "closed":
                            reply_text = f"Sorry, we're closed on {date}. Please check our operating hours."
                        elif reason == "outside_hours":
                            reply_text = f"Sorry, that time is outside our operating hours. Please choose a different time."
                        else:
                            reply_text = f"Sorry, that time is not available. Would you like to try a different date or time?"
                action_taken = "availability_shown"
            else:
                reply_text = "To check availability, I'll need the date and party size at minimum."
    
    # Add assistant message
    await add_message_to_session(str(session["_id"]), "assistant", reply_text, provider_name)
    
    # Update session intent if detected
    if json_action and "action" in json_action:
        intent_map = {
            "book": "book",
            "cancel": "cancel",
            "cancel_by_email": "cancel",
            "check_availability": "enquiry"
        }
        intent = intent_map.get(json_action["action"], "unknown")
        await db.chat_sessions.update_one(
            {"_id": session["_id"]},
            {"$set": {"intent": intent}}
        )
    
    return {
        "session_token": session["session_token"],
        "reply": reply_text,
        "action_taken": action_taken,
        "booking_ref": booking_ref
    }


async def get_session_history(session_token: str) -> dict:
    """Get full chat session history"""
    db = get_db()
    session = await db.chat_sessions.find_one({"session_token": session_token})
    return session


async def clear_session(session_token: str) -> bool:
    """Clear/reset a chat session"""
    db = get_db()
    result = await db.chat_sessions.update_one(
        {"session_token": session_token},
        {
            "$set": {
                "messages": [],
                "status": "active",
                "intent": "unknown",
                "collected_data": {},
                "last_message_at": datetime.utcnow()
            }
        }
    )
    return result.modified_count > 0
