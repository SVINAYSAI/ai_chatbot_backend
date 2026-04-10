from db.connection import get_db
from datetime import datetime, timedelta
from bson import ObjectId


async def find_available_tables(
    db, restaurant_id, party_size, requested_dt, slot_duration_minutes
):
    """
    Find available tables for a given time slot.
    A table is unavailable if any confirmed/pending booking overlaps with it.
    """
    requested_end = requested_dt + timedelta(minutes=slot_duration_minutes)
    
    # Convert restaurant_id to ObjectId if string
    if isinstance(restaurant_id, str):
        restaurant_id = ObjectId(restaurant_id)

    # Find all tables that have a conflicting booking
    conflicting = await db.bookings.distinct(
        "table_id",
        {
            "restaurant_id": restaurant_id,
            "status": {"$in": ["confirmed", "pending"]},
            "booking_datetime": {"$lt": requested_end},
            "end_datetime": {"$gt": requested_dt}
        }
    )

    # Find tables that fit party size and are not in conflicted list
    available = await db.tables.find({
        "restaurant_id": restaurant_id,
        "is_active": True,
        "status": {"$ne": "maintenance"},
        "capacity": {"$gte": party_size},
        "_id": {"$nin": conflicting}
    }).to_list(length=100)

    return available


async def check_availability(
    restaurant_id: str,
    date_str: str,  # "YYYY-MM-DD"
    time_str: str,  # "HH:MM"
    party_size: int
):
    """Check availability for a specific date/time/party size"""
    db = get_db()
    
    # Get restaurant for booking rules
    restaurant = await db.restaurants.find_one({"_id": ObjectId(restaurant_id)})
    if not restaurant:
        return {"available": False, "reason": "restaurant_not_found"}
    
    rules = restaurant.get("booking_rules", {})
    slot_duration = rules.get("slot_duration_minutes", 90)
    
    # Parse datetime
    try:
        booking_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return {"available": False, "reason": "invalid_datetime"}
    
    # Check if in the past
    if booking_dt < datetime.utcnow():
        return {"available": False, "reason": "past_datetime"}
    
    # Check advance booking window
    max_dt = datetime.utcnow() + timedelta(days=rules.get("advance_booking_days", 30))
    if booking_dt > max_dt:
        return {"available": False, "reason": "too_far_ahead"}
    
    # Check operating hours
    weekday = booking_dt.strftime("%A").lower()
    operating_hours = restaurant.get("operating_hours", [])
    day_hours = next((h for h in operating_hours if h["day"].lower() == weekday), None)
    
    if not day_hours or not day_hours.get("is_open", False):
        return {"available": False, "reason": "closed"}
    
    # Check if within operating hours
    open_time = day_hours.get("open_time", "00:00")
    close_time = day_hours.get("close_time", "23:59")
    last_booking_time = day_hours.get("last_booking_time", close_time)
    
    time_str_compare = time_str
    if time_str_compare < open_time or time_str_compare > last_booking_time:
        return {"available": False, "reason": "outside_hours"}
    
    # Find available tables
    available_tables = await find_available_tables(
        db, restaurant_id, party_size, booking_dt, slot_duration
    )
    
    if not available_tables:
        return {"available": False, "reason": "no_tables_available"}
    
    # Return best-fit table (smallest capacity that fits)
    best_table = min(available_tables, key=lambda t: t["capacity"])
    
    return {
        "available": True,
        "tables_available": len(available_tables),
        "suggested_table": {
            "id": str(best_table["_id"]),
            "table_number": best_table["table_number"],
            "label": best_table.get("label", ""),
            "capacity": best_table["capacity"],
            "location": best_table.get("location", "indoor")
        }
    }


async def get_table_status(restaurant_id: str):
    """Get live status of all tables"""
    db = get_db()
    
    tables = await db.tables.find({
        "restaurant_id": ObjectId(restaurant_id),
        "is_active": True
    }).to_list(length=100)
    
    now = datetime.utcnow()
    
    # For each table, check if there's a current booking
    for table in tables:
        current_booking = await db.bookings.find_one({
            "table_id": table["_id"],
            "status": {"$in": ["confirmed", "pending"]},
            "booking_datetime": {"$lte": now},
            "end_datetime": {"$gte": now}
        })
        
        if current_booking:
            table["current_booking"] = {
                "booking_ref": current_booking["booking_ref"],
                "guest_name": current_booking["guest_info"]["name"],
                "party_size": current_booking["party_size"],
                "end_time": current_booking["end_datetime"].strftime("%H:%M")
            }
    
    return tables
