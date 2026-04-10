import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv()

async def check():
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME")
    restaurant_id = os.getenv("RESTAURANT_ID")
    
    client = AsyncIOMotorClient(uri)
    db = client[db_name]
    
    admin = await db.admins.find_one({"email": "admin@gmail.com"})
    print(f"Admin Email: {admin['email'] if admin else 'None'}")
    print(f"Admin Restaurant ID: {admin['restaurant_id'] if admin else 'None'} (Type: {type(admin['restaurant_id']) if admin else 'None'})")
    
    tables_count = await db.tables.count_documents({"restaurant_id": ObjectId(restaurant_id)})
    print(f"Tables count: {tables_count}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check())
