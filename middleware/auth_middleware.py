from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from services.auth_service import decode_token, get_role_permissions
from db.connection import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current user from JWT token"""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        role = payload.get("role")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Check if it's a user (not admin)
        if role not in ["user"]:
            # Also allow if no role specified (backwards compat)
            pass
        
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_admin(token: str = Depends(oauth2_scheme)):
    """Get current admin from JWT token"""
    try:
        payload = decode_token(token)
        role = payload.get("role")
        
        if role not in ["super_admin", "manager", "staff"]:
            raise HTTPException(status_code=403, detail="Not an admin")
        
        # Add permissions to payload
        payload["permissions"] = get_role_permissions(role)
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_permission(permission: str):
    """Dependency factory to check specific permission"""
    async def check_permission(admin=Depends(get_current_admin)):
        permissions = admin.get("permissions", [])
        if permission not in permissions:
            raise HTTPException(
                status_code=403, 
                detail=f"Permission required: {permission}"
            )
        return admin
    return check_permission


# Common permission checks
require_view_bookings = require_permission("view_bookings")
require_edit_bookings = require_permission("edit_bookings")
require_cancel_bookings = require_permission("cancel_bookings")
require_manage_tables = require_permission("manage_tables")
require_view_reports = require_permission("view_reports")
require_manage_admins = require_permission("manage_admins")
require_manage_settings = require_permission("manage_settings")
require_view_chat_sessions = require_permission("view_chat_sessions")
