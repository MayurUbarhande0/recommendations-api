import mysql.connector
import json
from datetime import datetime
import os

# -------------------------------
# JSON serializer for datetime
# -------------------------------
def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# -------------------------------
# Connect to local MySQL server
# -------------------------------
conn = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="Mayur@12",  # replace with your root password
    port=3306,
    database="searches"   # replace with your DB name
)

cursor = conn.cursor(dictionary=True)  # fetch results as dictionaries

# -------------------------------
# Fetch search data for user
# -------------------------------
def get_search_data(user_id: int):
    try:
        cursor.execute(f"SELECT * FROM searches WHERE id = {user_id} LIMIT 5")    
        rows = cursor.fetchall()

        os.makedirs("data", exist_ok=True)
        file_path = f"data/cache_searches_{user_id}.json"
        with open(file_path, "w") as f:
            json.dump(rows, f, indent=4, default=json_serial)

        print(f"✅ Search cache saved for user {user_id}")
    except Exception as e:
        print(f"Error saving {file_path}: {e}")

# -------------------------------
# Fetch purchase data for user
# -------------------------------
def get_recent_purchased(user_id: int):
    try:
        cursor.execute(f"SELECT * FROM purchase WHERE id = {user_id} LIMIT 5")    
        rows = cursor.fetchall()

        os.makedirs("data", exist_ok=True)
        file_path = f"data/cache_purchase_{user_id}.json"
        with open(file_path, "w") as f:
            json.dump(rows, f, indent=4, default=json_serial)

        print(f"✅ Purchase cache saved for user {user_id}")
    except Exception as e:
        print(f"Error saving {file_path}: {e}")
