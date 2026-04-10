from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from bson import ObjectId

from models.table import TableCreate, TableUpdate
from services.table_service import get_table_status
from db.connection import get_db
from config import settings
from middleware.auth_middleware import (
    get_current_admin, 
    require_manage_tables
)

router = APIRouter()


async def get_restaurant():
    """Get the default restaurant"""
    db = get_db()
    restaurant = await db.restaurants.find_one({"_id": ObjectId(settings.RESTAURANT_ID)})
    if not restaurant:
        restaurant = await db.restaurants.find_one()
    return restaurant


@router.get("")
async def list_tables():
    """List all active tables (public endpoint)"""
    db = get_db()
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=500, detail="Restaurant not configured")
    
    tables = await db.tables.find({
        "restaurant_id": restaurant["_id"],
        "is_active": True
    }).to_list(length=100)
    
    # Convert ObjectIds to strings
    for table in tables:
        table["_id"] = str(table["_id"])
        table["restaurant_id"] = str(table["restaurant_id"])
    
    return {"tables": tables}


@router.get("/{table_id}")
async def get_table(table_id: str):
    """Get a single table by ID"""
    db = get_db()
    
    try:
        table = await db.tables.find_one({"_id": ObjectId(table_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid table ID")
    
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    table["_id"] = str(table["_id"])
    table["restaurant_id"] = str(table["restaurant_id"])
    
    return table


@router.post("", dependencies=[Depends(require_manage_tables)])
async def create_table(data: TableCreate):
    """Create a new table (admin only)"""
    db = get_db()
    restaurant = await get_restaurant()
    
    if not restaurant:
        raise HTTPException(status_code=500, detail="Restaurant not configured")
    
    # Check if table number already exists
    existing = await db.tables.find_one({
        "restaurant_id": restaurant["_id"],
        "table_number": data.table_number
    })
    
    if existing:
        raise HTTPException(status_code=409, detail="Table number already exists")
    
    table_doc = {
        "restaurant_id": restaurant["_id"],
        "table_number": data.table_number,
        "label": data.label,
        "capacity": data.capacity,
        "min_capacity": data.min_capacity,
        "location": data.location,
        "features": data.features,
        "is_active": True,
        "status": "available",
        "notes": data.notes,
        "created_at": __import__('datetime').datetime.utcnow(),
        "updated_at": __import__('datetime').datetime.utcnow()
    }
    
    result = await db.tables.insert_one(table_doc)
    
    return {
        "id": str(result.inserted_id),
        "message": "Table created successfully"
    }


@router.put("/{table_id}", dependencies=[Depends(require_manage_tables)])
async def update_table(table_id: str, data: TableUpdate):
    """Update a table (admin only)"""
    db = get_db()
    
    try:
        table = await db.tables.find_one({"_id": ObjectId(table_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid table ID")
    
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Build update document
    update_data = {}
    for field in ["label", "capacity", "min_capacity", "location", "features", "is_active", "status", "notes"]:
        value = getattr(data, field)
        if value is not None:
            update_data[field] = value
    
    update_data["updated_at"] = __import__('datetime').datetime.utcnow()
    
    await db.tables.update_one(
        {"_id": ObjectId(table_id)},
        {"$set": update_data}
    )
    
    return {"message": "Table updated successfully"}


@router.delete("/{table_id}", dependencies=[Depends(require_manage_tables)])
async def delete_table(table_id: str):
    """Deactivate a table (soft delete, admin only)"""
    db = get_db()
    
    try:
        table = await db.tables.find_one({"_id": ObjectId(table_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid table ID")
    
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Soft delete - just mark as inactive
    await db.tables.update_one(
        {"_id": ObjectId(table_id)},
        {"$set": {"is_active": False, "updated_at": __import__('datetime').datetime.utcnow()}}
    )
    
    return {"message": "Table deactivated successfully"}


@router.get("/status/live", dependencies=[Depends(get_current_admin)])
async def get_live_table_status():
    """Get live status of all tables (admin only)"""
    restaurant = await get_restaurant()
    if not restaurant:
        raise HTTPException(status_code=500, detail="Restaurant not configured")
    
    tables = await get_table_status(str(restaurant["_id"]))
    
    # Convert ObjectIds to strings
    for table in tables:
        table["_id"] = str(table["_id"])
        table["restaurant_id"] = str(table["restaurant_id"])
    
    return {"tables": tables}
