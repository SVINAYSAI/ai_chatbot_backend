from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

from models.restaurant import RestaurantCreate, RestaurantUpdate, OperatingHours, BookingRules
from db.connection import get_db
from config import settings
from middleware.auth_middleware import get_current_admin, require_manage_settings

router = APIRouter()


async def get_restaurant():
    """Get the default restaurant"""
    db = get_db()
    restaurant = await db.restaurants.find_one({"_id": ObjectId(settings.RESTAURANT_ID)})
    if not restaurant:
        restaurant = await db.restaurants.find_one()
    return restaurant


@router.get("")
async def get_restaurant_info():
    """Get public restaurant information"""
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    # Convert ObjectId to string
    restaurant["_id"] = str(restaurant["_id"])
    
    # Remove sensitive/internal fields if any
    restaurant.pop("ai_system_prompt_override", None)
    
    return restaurant


@router.put("", dependencies=[Depends(require_manage_settings)])
async def update_restaurant(data: RestaurantUpdate):
    """Update restaurant settings"""
    db = get_db()
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    # Build update document
    update_data = {}
    
    if data.name is not None:
        update_data["name"] = data.name
    if data.address is not None:
        update_data["address"] = data.address.model_dump()
    if data.contact is not None:
        update_data["contact"] = data.contact.model_dump()
    if data.operating_hours is not None:
        update_data["operating_hours"] = [h.model_dump() for h in data.operating_hours]
    if data.booking_rules is not None:
        update_data["booking_rules"] = data.booking_rules.model_dump()
    if data.ai_system_prompt_override is not None:
        update_data["ai_system_prompt_override"] = data.ai_system_prompt_override
    
    update_data["updated_at"] = datetime.utcnow()
    
    await db.restaurants.update_one(
        {"_id": restaurant["_id"]},
        {"$set": update_data}
    )
    
    return {"message": "Restaurant updated successfully"}


@router.put("/operating-hours", dependencies=[Depends(require_manage_settings)])
async def update_operating_hours(hours: List[OperatingHours]):
    """Update operating hours"""
    db = get_db()
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    await db.restaurants.update_one(
        {"_id": restaurant["_id"]},
        {"$set": {
            "operating_hours": [h.model_dump() for h in hours],
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": "Operating hours updated successfully"}


@router.put("/booking-rules", dependencies=[Depends(require_manage_settings)])
async def update_booking_rules(rules: BookingRules):
    """Update booking rules"""
    db = get_db()
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    await db.restaurants.update_one(
        {"_id": restaurant["_id"]},
        {"$set": {
            "booking_rules": rules.model_dump(),
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": "Booking rules updated successfully"}


@router.put("/ai-prompt", dependencies=[Depends(require_manage_settings)])
async def update_ai_prompt(data: dict):
    """Update AI system prompt override"""
    db = get_db()
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    prompt = data.get("prompt")
    
    await db.restaurants.update_one(
        {"_id": restaurant["_id"]},
        {"$set": {
            "ai_system_prompt_override": prompt,
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": "AI prompt updated successfully"}


# ===== Setup endpoint (for initial restaurant creation) =====

@router.post("/setup")
async def setup_restaurant(data: RestaurantCreate):
    """Create initial restaurant (for setup only)"""
    db = get_db()
    
    # Check if any restaurant exists
    existing = await db.restaurants.find_one()
    if existing:
        raise HTTPException(status_code=403, detail="Restaurant already exists")
    
    # Check slug uniqueness
    slug_exists = await db.restaurants.find_one({"slug": data.slug})
    if slug_exists:
        raise HTTPException(status_code=409, detail="Slug already exists")
    
    restaurant_doc = {
        "name": data.name,
        "slug": data.slug,
        "address": data.address.model_dump(),
        "contact": data.contact.model_dump(),
        "operating_hours": [h.model_dump() for h in data.operating_hours],
        "booking_rules": data.booking_rules.model_dump(),
        "ai_system_prompt_override": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.restaurants.insert_one(restaurant_doc)
    
    return {
        "id": str(result.inserted_id),
        "message": "Restaurant created successfully",
        "note": "Add this ID to your .env as RESTAURANT_ID"
    }
