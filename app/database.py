import mysql.connector
import json
import os


def create_connection():
    """Create and return a MySQL connection."""
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="Mayur@12",   # change if needed
        port=3306,
        database="searches"    # change if different
    )



def save_json(data, file_path):
    """Save data safely as JSON."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving {file_path}: {e}")



def get_search_data(user_id: int, limit: int = 5):
    """Fetch search data for a specific user and save as JSON."""
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    # Safe parameterized query
    cursor.execute("SELECT * FROM searches WHERE id = %s LIMIT %s", (user_id, limit))
    rows = cursor.fetchall()

    # Transform into {column: [values]}
    data = {}
    if rows:
        for col in rows[0].keys():
            data[col] = [row[col] for row in rows]

    # Add meta info
    data["success"] = True
    data["user_id"] = user_id

    # Save JSON
    save_json(data, f"data/cache_searches_{user_id}.json")

    cursor.close()
    conn.close()
    print(f"Search cache saved for user {user_id}")

    return data



def get_recent_purchased(user_id: int, limit: int = 5):
    """Fetch purchase data for a specific user and save as JSON."""
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM purchase WHERE id = %s LIMIT %s", (user_id, limit))
    rows = cursor.fetchall()

    # Transform into {column: [values]}
    data = {}
    if rows:
        for col in rows[0].keys():
            data[col] = [row[col] for row in rows]

    data["success"] = True
    data["user_id"] = user_id

    save_json(data, f"data/cache_purchase_{user_id}.json")

    cursor.close()
    conn.close()
    print(f"Purchase cache saved for user {user_id}")

    return data



if __name__ == "__main__":
    get_search_data(1)
    get_recent_purchased(1)
