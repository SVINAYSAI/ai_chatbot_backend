from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from config import settings

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_token(subject: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": subject, "role": role, "exp": expire},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def get_role_permissions(role: str) -> list:
    """Get permissions based on admin role"""
    permissions_map = {
        "super_admin": [
            "view_bookings", "edit_bookings", "cancel_bookings",
            "manage_tables", "view_reports", "manage_admins",
            "manage_settings", "view_chat_sessions"
        ],
        "manager": [
            "view_bookings", "edit_bookings", "cancel_bookings",
            "manage_tables", "view_reports", "view_chat_sessions"
        ],
        "staff": [
            "view_bookings", "edit_bookings"
        ]
    }
    return permissions_map.get(role, [])
