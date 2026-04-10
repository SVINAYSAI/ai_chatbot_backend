import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_api():
    base_url = "http://localhost:8000"
    email = "admin@gmail.com"
    password = "admin@123" # User said they entered this
    
    # Login
    print(f"Logging in as {email}...")
    try:
        res = requests.post(f"{base_url}/api/auth/admin/login", json={"email": email, "password": password})
        if res.status_code != 200:
             print(f"Login failed: {res.status_code} - {res.text}")
             return
        
        data = res.json()
        token = data["access_token"]
        print("Login successful!")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Check tables
        res = requests.get(f"{base_url}/api/tables/status/live", headers=headers)
        print(f"Tables API ({res.status_code}):")
        print(res.json())
        
        # Check stats
        res = requests.get(f"{base_url}/api/admin/dashboard/stats", headers=headers)
        print(f"Stats API ({res.status_code}):")
        print(res.json())
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
