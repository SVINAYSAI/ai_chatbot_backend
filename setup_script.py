#!/usr/bin/env python3
"""
Setup script for Restaurant Table Management System
Creates initial restaurant and admin user
"""

import asyncio
import os
import sys
from getpass import getpass

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import connect_db, close_db, get_db
from db.indexes import create_indexes
from services.auth_service import hash_password
from bson import ObjectId
from datetime import datetime


async def create_restaurant():
    """Create initial restaurant"""
    db = get_db()
    
    # Check if restaurant already exists
    existing = await db.restaurants.find_one()
    if existing:
        print(f"[Setup] Restaurant already exists: {existing['name']} (ID: {existing['_id']})")
        return str(existing['_id'])
    
    print("[Setup] Creating initial restaurant...")
    
    restaurant_doc = {
        "name": "The Golden Fork",
        "slug": "golden-fork",
        "address": {
            "street": "123 Main Street",
            "city": "New York",
            "state": "NY",
            "zip": "10001",
            "country": "USA"
        },
        "contact": {
            "phone": "+1 555-123-4567",
            "email": "hello@goldenfork.com",
            "website": "https://goldenfork.com"
        },
        "operating_hours": [
            {"day": "monday", "is_open": True, "open_time": "11:00", "close_time": "22:00", "last_booking_time": "21:00"},
            {"day": "tuesday", "is_open": True, "open_time": "11:00", "close_time": "22:00", "last_booking_time": "21:00"},
            {"day": "wednesday", "is_open": True, "open_time": "11:00", "close_time": "22:00", "last_booking_time": "21:00"},
            {"day": "thursday", "is_open": True, "open_time": "11:00", "close_time": "22:00", "last_booking_time": "21:00"},
            {"day": "friday", "is_open": True, "open_time": "11:00", "close_time": "23:00", "last_booking_time": "22:00"},
            {"day": "saturday", "is_open": True, "open_time": "10:00", "close_time": "23:00", "last_booking_time": "22:00"},
            {"day": "sunday", "is_open": True, "open_time": "10:00", "close_time": "21:00", "last_booking_time": "20:00"}
        ],
        "booking_rules": {
            "min_party_size": 1,
            "max_party_size": 20,
            "slot_duration_minutes": 90,
            "advance_booking_days": 30,
            "cancellation_cutoff_hours": 2
        },
        "ai_system_prompt_override": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.restaurants.insert_one(restaurant_doc)
    restaurant_id = str(result.inserted_id)
    
    print(f"[Setup] Restaurant created with ID: {restaurant_id}")
    print(f"[Setup] Add this to your .env file: RESTAURANT_ID={restaurant_id}")
    
    return restaurant_id


async def create_admin_user(restaurant_id):
    """Create initial admin user"""
    db = get_db()
    
    # Check if any admin exists
    existing = await db.admins.find_one()
    if existing:
        print(f"[Setup] Admin user already exists: {existing['email']}")
        return
    
    print("\n[Setup] Creating initial admin user...")
    
    name = input("Admin name: ").strip() or "Admin User"
    email = input("Admin email: ").strip() or "admin@restaurant.com"
    password = getpass("Admin password: ")
    
    if not password:
        print("[Setup] Password is required. Aborting.")
        return
    
    admin_doc = {
        "restaurant_id": ObjectId(restaurant_id),
        "name": name,
        "email": email,
        "password_hash": hash_password(password),
        "role": "super_admin",
        "permissions": [
            "view_bookings", "edit_bookings", "cancel_bookings",
            "manage_tables", "view_reports", "manage_admins",
            "manage_settings", "view_chat_sessions"
        ],
        "last_login": None,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.admins.insert_one(admin_doc)
    
    print(f"[Setup] Admin user created: {email}")
    print(f"[Setup] You can now log in at /admin/login")


async def create_sample_tables(restaurant_id):
    """Create sample tables"""
    db = get_db()
    
    # Check if tables already exist
    existing = await db.tables.find_one({"restaurant_id": ObjectId(restaurant_id)})
    if existing:
        print("[Setup] Tables already exist")
        return
    
    print("\n[Setup] Creating sample tables...")
    
    tables = [
        {"table_number": "T1", "label": "Window Table 1", "capacity": 2, "min_capacity": 1, "location": "indoor", "features": ["near_window"]},
        {"table_number": "T2", "label": "Window Table 2", "capacity": 2, "min_capacity": 1, "location": "indoor", "features": ["near_window"]},
        {"table_number": "T3", "label": "Booth 1", "capacity": 4, "min_capacity": 2, "location": "indoor", "features": ["quiet"]},
        {"table_number": "T4", "label": "Booth 2", "capacity": 4, "min_capacity": 2, "location": "indoor", "features": ["quiet"]},
        {"table_number": "T5", "label": "Center Table 1", "capacity": 6, "min_capacity": 4, "location": "indoor", "features": []},
        {"table_number": "T6", "label": "Center Table 2", "capacity": 8, "min_capacity": 6, "location": "indoor", "features": []},
        {"table_number": "P1", "label": "Patio Table 1", "capacity": 4, "min_capacity": 2, "location": "outdoor", "features": ["outdoor_seating"]},
        {"table_number": "P2", "label": "Patio Table 2", "capacity": 4, "min_capacity": 2, "location": "outdoor", "features": ["outdoor_seating"]},
        {"table_number": "B1", "label": "Bar Seat 1", "capacity": 2, "min_capacity": 1, "location": "bar", "features": ["bar_seating"]},
        {"table_number": "B2", "label": "Bar Seat 2", "capacity": 2, "min_capacity": 1, "location": "bar", "features": ["bar_seating"]},
        {"table_number": "PR1", "label": "Private Room", "capacity": 12, "min_capacity": 8, "location": "private", "features": ["private_room"]},
    ]
    
    for table in tables:
        table_doc = {
            "restaurant_id": ObjectId(restaurant_id),
            "table_number": table["table_number"],
            "label": table["label"],
            "capacity": table["capacity"],
            "min_capacity": table["min_capacity"],
            "location": table["location"],
            "features": table["features"],
            "is_active": True,
            "status": "available",
            "notes": "",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await db.tables.insert_one(table_doc)
    
    print(f"[Setup] Created {len(tables)} sample tables")


async def main():
    """Main setup function"""
    print("=" * 60)
    print("Restaurant Table Management System - Setup")
    print("=" * 60)
    
    # Check environment
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        print("\n[Error] MONGODB_URI not set in environment")
        print("Please set it before running this script:")
        print("  export MONGODB_URI='your-mongodb-uri'")
        return
    
    # Connect to database
    print("\n[Setup] Connecting to MongoDB...")
    await connect_db()
    
    try:
        # Create indexes
        print("[Setup] Creating database indexes...")
        await create_indexes()
        
        # Create restaurant
        restaurant_id = await create_restaurant()
        
        # Create admin user
        await create_admin_user(restaurant_id)
        
        # Create sample tables
        await create_sample_tables(restaurant_id)
        
        print("\n" + "=" * 60)
        print("Setup complete!")
        print("=" * 60)
        print(f"\nNext steps:")
        print(f"1. Add RESTAURANT_ID={restaurant_id} to your .env file")
        print(f"2. Start the backend: uvicorn main:app --reload")
        print(f"3. Start the frontend: npm run dev")
        print(f"4. Visit http://localhost:5173/admin/login to log in")
        
    finally:
        await close_db()


if __name__ == "__main__":
    # Load environment variables from .env file if exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    asyncio.run(main())
