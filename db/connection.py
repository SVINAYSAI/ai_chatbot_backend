from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

_client: AsyncIOMotorClient = None


async def connect_db():
    global _client
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    print(f"[DB] Connected to MongoDB: {settings.MONGODB_DB_NAME}")


async def close_db():
    global _client
    if _client:
        _client.close()
        print("[DB] MongoDB connection closed")


def get_db():
    return _client[settings.MONGODB_DB_NAME]
