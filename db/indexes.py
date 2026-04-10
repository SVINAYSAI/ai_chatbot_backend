from db.connection import get_db


async def create_indexes():
    """Create all MongoDB indexes as specified in DATABASE.md"""
    db = get_db()
    
    # restaurants collection
    await db.restaurants.create_index("slug", unique=True)
    print("[DB] Created index: restaurants.slug (unique)")
    
    # tables collection
    await db.tables.create_index([("restaurant_id", 1), ("table_number", 1)], unique=True)
    await db.tables.create_index([("restaurant_id", 1), ("status", 1)])
    await db.tables.create_index([("restaurant_id", 1), ("capacity", 1)])
    print("[DB] Created indexes: tables")
    
    # bookings collection
    await db.bookings.create_index("booking_ref", unique=True)
    await db.bookings.create_index([("restaurant_id", 1), ("booking_datetime", 1)])
    await db.bookings.create_index([("restaurant_id", 1), ("table_id", 1), ("booking_datetime", 1)])
    await db.bookings.create_index([("restaurant_id", 1), ("status", 1)])
    await db.bookings.create_index("guest_info.email")
    await db.bookings.create_index("user_id")
    await db.bookings.create_index([("created_at", -1)])
    # Compound index for availability check (most critical)
    await db.bookings.create_index([
        ("table_id", 1),
        ("booking_datetime", 1),
        ("end_datetime", 1),
        ("status", 1)
    ])
    print("[DB] Created indexes: bookings")
    
    # users collection
    await db.users.create_index("email", unique=True)
    print("[DB] Created index: users.email (unique)")
    
    # admins collection
    await db.admins.create_index("email", unique=True)
    await db.admins.create_index([("restaurant_id", 1), ("role", 1)])
    print("[DB] Created indexes: admins")
    
    # chat_sessions collection
    await db.chat_sessions.create_index("session_token", unique=True)
    await db.chat_sessions.create_index([("restaurant_id", 1), ("status", 1)])
    await db.chat_sessions.create_index("last_message_at")
    await db.chat_sessions.create_index("booking_id")
    print("[DB] Created indexes: chat_sessions")
    
    # notifications_log collection
    await db.notifications_log.create_index("booking_id")
    await db.notifications_log.create_index([("sent_at", -1)])
    print("[DB] Created indexes: notifications_log")
    
    print("[DB] All indexes created successfully")
