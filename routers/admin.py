from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime, timedelta
from bson import ObjectId

from models.admin import AdminCreate, AdminUpdate
from services.auth_service import hash_password, get_role_permissions
from services.booking_service import update_booking_status, cancel_by_ref
from db.connection import get_db
from config import settings
from middleware.auth_middleware import (
    get_current_admin,
    require_view_bookings,
    require_edit_bookings,
    require_cancel_bookings,
    require_view_reports,
    require_manage_admins,
    require_view_chat_sessions
)

router = APIRouter()


async def get_restaurant():
    """Get the default restaurant"""
    db = get_db()
    restaurant = await db.restaurants.find_one({"_id": ObjectId(settings.RESTAURANT_ID)})
    if not restaurant:
        restaurant = await db.restaurants.find_one()
    return restaurant


# ===== Bookings Management =====

@router.get("/bookings", dependencies=[Depends(require_view_bookings)])
async def list_bookings(
    status: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """List all bookings with filters"""
    db = get_db()
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=500, detail="Restaurant not configured")
    
    # Build query
    query = {"restaurant_id": restaurant["_id"]}
    
    if status:
        query["status"] = status
    
    if date:
        query["booking_date"] = date
    
    # Get total count
    total = await db.bookings.count_documents(query)
    
    # Get bookings
    skip = (page - 1) * limit
    bookings = await db.bookings.find(query)\
        .sort("booking_datetime", -1)\
        .skip(skip)\
        .limit(limit)\
        .to_list(length=limit)
    
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
    
    return {
        "bookings": bookings,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }


@router.get("/bookings/{ref}", dependencies=[Depends(require_view_bookings)])
async def get_booking_by_ref_admin(ref: str):
    """Get a single booking by reference"""
    db = get_db()
    
    booking = await db.bookings.find_one({"booking_ref": ref})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
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


@router.patch("/bookings/{ref}/status", dependencies=[Depends(require_edit_bookings)])
async def update_booking_status_admin(ref: str, data: dict):
    """Update booking status"""
    new_status = data.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required")
    
    result = await update_booking_status(ref, new_status, "admin")
    
    if not result.get("success"):
        reason = result.get("reason", "unknown")
        if reason == "not_found":
            raise HTTPException(status_code=404, detail="Booking not found")
        raise HTTPException(status_code=400, detail=result)
    
    return {"message": "Status updated successfully"}


@router.delete("/bookings/{ref}", dependencies=[Depends(require_cancel_bookings)])
async def delete_booking_admin(ref: str, data: Optional[dict] = None):
    """Cancel/delete a booking"""
    reason = data.get("reason", "Cancelled by admin") if data else "Cancelled by admin"
    
    result = await cancel_by_ref(ref, reason, "admin")
    
    if not result.get("success"):
        reason = result.get("reason", "unknown")
        if reason == "not_found":
            raise HTTPException(status_code=404, detail="Booking not found")
        raise HTTPException(status_code=400, detail=result)
    
    return {"message": "Booking cancelled successfully"}


# ===== Dashboard Stats =====

@router.get("/dashboard/stats", dependencies=[Depends(require_view_reports)])
async def get_dashboard_stats():
    """Get dashboard statistics"""
    db = get_db()
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=500, detail="Restaurant not configured")
    
    today = datetime.utcnow().date().isoformat()
    week_start = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
    month_start = (datetime.utcnow() - timedelta(days=30)).date().isoformat()
    
    # Today's stats
    today_query = {"restaurant_id": restaurant["_id"], "booking_date": today}
    today_bookings = await db.bookings.find(today_query).to_list(length=1000)
    
    today_stats = {
        "total_bookings": len(today_bookings),
        "confirmed": len([b for b in today_bookings if b["status"] == "confirmed"]),
        "cancelled": len([b for b in today_bookings if b["status"] == "cancelled"]),
        "completed": len([b for b in today_bookings if b["status"] == "completed"]),
        "covers": sum(b["party_size"] for b in today_bookings if b["status"] == "confirmed")
    }
    
    # This week's stats
    week_query = {
        "restaurant_id": restaurant["_id"],
        "booking_date": {"$gte": week_start}
    }
    week_bookings = await db.bookings.find(week_query).to_list(length=1000)
    
    week_stats = {
        "total_bookings": len(week_bookings),
        "confirmed": len([b for b in week_bookings if b["status"] == "confirmed"]),
        "cancelled": len([b for b in week_bookings if b["status"] == "cancelled"]),
        "completed": len([b for b in week_bookings if b["status"] == "completed"]),
        "covers": sum(b["party_size"] for b in week_bookings if b["status"] == "confirmed")
    }
    
    # This month's stats
    month_query = {
        "restaurant_id": restaurant["_id"],
        "booking_date": {"$gte": month_start}
    }
    month_bookings = await db.bookings.find(month_query).to_list(length=1000)
    
    month_stats = {
        "total_bookings": len(month_bookings),
        "confirmed": len([b for b in month_bookings if b["status"] == "confirmed"]),
        "cancelled": len([b for b in month_bookings if b["status"] == "cancelled"]),
        "completed": len([b for b in month_bookings if b["status"] == "completed"]),
        "covers": sum(b["party_size"] for b in month_bookings if b["status"] == "confirmed")
    }
    
    # Popular times (group by hour)
    hour_counts = {}
    for booking in month_bookings:
        if booking["status"] == "confirmed":
            hour = booking["booking_time"].split(":")[0]
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
    
    popular_times = [
        {"hour": f"{int(h):02d}:00", "bookings": c}
        for h, c in sorted(hour_counts.items(), key=lambda x: -x[1])[:5]
    ]
    
    # Table utilization
    tables = await db.tables.find({
        "restaurant_id": restaurant["_id"],
        "is_active": True
    }).to_list(length=100)
    
    table_utilization = []
    for table in tables:
        table_bookings = len([b for b in month_bookings 
                            if b.get("table_id") == table["_id"] 
                            and b["status"] in ["confirmed", "completed"]])
        table_utilization.append({
            "table_number": table["table_number"],
            "bookings": table_bookings
        })
    
    return {
        "today": today_stats,
        "this_week": week_stats,
        "this_month": month_stats,
        "popular_times": popular_times,
        "table_utilization": table_utilization
    }


# ===== Chat Sessions =====

@router.get("/chat-sessions", dependencies=[Depends(require_view_chat_sessions)])
async def list_chat_sessions(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """List chat sessions"""
    db = get_db()
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=500, detail="Restaurant not configured")
    
    query = {"restaurant_id": restaurant["_id"]}
    if status:
        query["status"] = status
    
    total = await db.chat_sessions.count_documents(query)
    
    skip = (page - 1) * limit
    sessions = await db.chat_sessions.find(query)\
        .sort("last_message_at", -1)\
        .skip(skip)\
        .limit(limit)\
        .to_list(length=limit)
    
    # Convert ObjectIds to strings
    for session in sessions:
        session["_id"] = str(session["_id"])
        if session.get("restaurant_id"):
            session["restaurant_id"] = str(session["restaurant_id"])
        if session.get("user_id"):
            session["user_id"] = str(session["user_id"])
        if session.get("booking_id"):
            session["booking_id"] = str(session["booking_id"])
    
    return {
        "sessions": sessions,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }


# ===== Users =====

@router.get("/users", dependencies=[Depends(require_manage_admins)])
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """List all registered users"""
    db = get_db()
    
    total = await db.users.count_documents({})
    
    skip = (page - 1) * limit
    users = await db.users.find()\
        .sort("created_at", -1)\
        .skip(skip)\
        .limit(limit)\
        .to_list(length=limit)
    
    # Convert ObjectIds to strings and remove password hash
    for user in users:
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        if user.get("restaurant_id"):
            user["restaurant_id"] = str(user["restaurant_id"])
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }


# ===== Admin Management =====

@router.post("/admins", dependencies=[Depends(require_manage_admins)])
async def create_admin(data: AdminCreate):
    """Create a new admin user"""
    db = get_db()
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=500, detail="Restaurant not configured")
    
    # Check if email already exists
    existing = await db.admins.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    
    # Validate role
    valid_roles = ["super_admin", "manager", "staff"]
    if data.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")
    
    # Get permissions for role
    permissions = get_role_permissions(data.role)
    
    admin_doc = {
        "restaurant_id": restaurant["_id"],
        "name": data.name,
        "email": data.email,
        "password_hash": hash_password(data.password),
        "role": data.role,
        "permissions": data.permissions or permissions,
        "last_login": None,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.admins.insert_one(admin_doc)
    
    return {
        "id": str(result.inserted_id),
        "message": "Admin created successfully"
    }


@router.put("/admins/{admin_id}", dependencies=[Depends(require_manage_admins)])
async def update_admin(admin_id: str, data: AdminUpdate):
    """Update an admin user"""
    db = get_db()
    
    try:
        admin = await db.admins.find_one({"_id": ObjectId(admin_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid admin ID")
    
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    # Build update document
    update_data = {}
    
    if data.name is not None:
        update_data["name"] = data.name
    if data.email is not None:
        # Check if email is already taken
        existing = await db.admins.find_one({"email": data.email, "_id": {"$ne": ObjectId(admin_id)}})
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
        update_data["email"] = data.email
    if data.role is not None:
        valid_roles = ["super_admin", "manager", "staff"]
        if data.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role")
        update_data["role"] = data.role
        update_data["permissions"] = get_role_permissions(data.role)
    if data.permissions is not None:
        update_data["permissions"] = data.permissions
    if data.is_active is not None:
        update_data["is_active"] = data.is_active
    
    update_data["updated_at"] = datetime.utcnow()
    
    await db.admins.update_one(
        {"_id": ObjectId(admin_id)},
        {"$set": update_data}
    )
    
    return {"message": "Admin updated successfully"}
