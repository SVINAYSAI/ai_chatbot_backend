import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def check_db():
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME")
    restaurant_id = os.getenv("RESTAURANT_ID")
    
    print(f"Connecting to: {uri}")
    print(f"DB: {db_name}")
    print(f"Restaurant ID: {restaurant_id}")
    
    client = AsyncIOMotorClient(uri)
    db = client[db_name]
    
    # Check tables
    tables_count = await db.tables.count_documents({"restaurant_id": restaurant_id})
    print(f"Tables count: {tables_count}")
    
    # Check admins
    admins_count = await db.admins.count_documents({})
    print(f"Admins count (total): {admins_count}")
    
    # Check if this restaurant exists
    restaurant = await db.restaurants.find_one({"_id": restaurant_id}) # Note: it might be ObjectId or string
    if not restaurant:
        from bson import ObjectId
        try:
            restaurant = await db.restaurants.find_one({"_id": ObjectId(restaurant_id)})
            print(f"Restaurant found with ObjectId: {restaurant['name'] if restaurant else 'None'}")
        except:
            print("Failed to check with ObjectId")
    else:
         print(f"Restaurant found with string ID: {restaurant['name']}")

    client.close()

if __name__ == "__main__":
    asyncio.run(check_db())
