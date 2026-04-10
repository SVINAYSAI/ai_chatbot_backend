from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime
from bson import ObjectId

from models.user import UserRegister, UserLogin, UserResponse
from models.admin import AdminLogin, TokenResponse
from services.auth_service import hash_password, verify_password, create_token, decode_token
from db.connection import get_db
from middleware.auth_middleware import get_current_user

router = APIRouter()


@router.post("/register", response_model=dict)
async def register_user(data: UserRegister):
    """Register a new customer user"""
    db = get_db()
    
    # Check if email already exists
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    
    # Create user document
    user_doc = {
        "restaurant_id": None,  # Will be set if needed
        "name": data.name,
        "email": data.email,
        "phone": data.phone,
        "password_hash": hash_password(data.password),
        "is_verified": False,
        "booking_history": [],
        "preferences": {},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_doc)
    
    # Create token
    token = create_token(str(result.inserted_id), "user")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "user",
        "user": {
            "id": str(result.inserted_id),
            "name": data.name,
            "email": data.email
        }
    }


@router.post("/login", response_model=TokenResponse)
async def login_user(data: UserLogin):
    """Login a customer user"""
    db = get_db()
    
    # Find user by email
    user = await db.users.find_one({"email": data.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create token
    token = create_token(str(user["_id"]), "user")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "user"
    }


@router.post("/admin/login", response_model=TokenResponse)
async def login_admin(data: AdminLogin):
    """Login an admin user"""
    db = get_db()
    
    # Find admin by email
    admin = await db.admins.find_one({"email": data.email})
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check if active
    if not admin.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated")
    
    # Verify password
    if not verify_password(data.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Update last login
    await db.admins.update_one(
        {"_id": admin["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    # Create token
    token = create_token(str(admin["_id"]), admin["role"])
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": admin["role"]
    }


@router.get("/me", response_model=dict)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    db = get_db()
    
    user_id = current_user.get("sub")
    role = current_user.get("role")
    
    if role in ["super_admin", "manager", "staff"]:
        # Get admin profile
        admin = await db.admins.find_one({"_id": ObjectId(user_id)})
        if not admin:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": str(admin["_id"]),
            "name": admin["name"],
            "email": admin["email"],
            "role": admin["role"],
            "permissions": current_user.get("permissions", []),
            "is_admin": True
        }
    else:
        # Get user profile
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "phone": user.get("phone"),
            "preferences": user.get("preferences"),
            "is_admin": False
        }
