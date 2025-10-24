import aiomysql
import json
import os
from datetime import datetime

DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "Mayur@12",
    "port": 3306,
    "db": "searches",
}


def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


async def get_search_data(user_id: int, pool):
    """
    Fetch user's search data asynchronously and save to cache.
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT * FROM searches WHERE id = %s LIMIT 5", (user_id,))
            rows = await cursor.fetchall()

    os.makedirs("data", exist_ok=True)
    file_path = f"data/cache_searches_{user_id}.json"
    try:
        with open(file_path, "w") as f:
            json.dump(rows, f, indent=4, default=json_serial)
        print(f"✅ Search cache saved for user {user_id}")
    except Exception as e:
        print(f"Error saving {file_path}: {e}")

    return rows


async def get_recent_purchased(user_id: int, pool):
    """
    Fetch user's purchase data asynchronously and save to cache.
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT * FROM purchases WHERE id = %s LIMIT 5", (user_id,))
            rows = await cursor.fetchall()

    os.makedirs("data", exist_ok=True)
    file_path = f"data/cache_purchase_{user_id}.json"
    try:
        with open(file_path, "w") as f:
            json.dump(rows, f, indent=4, default=json_serial)
        print(f"✅ Purchase cache saved for user {user_id}")
    except Exception as e:
        print(f"Error saving {file_path}: {e}")

    return rows
