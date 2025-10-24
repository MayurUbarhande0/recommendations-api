import json
import os

def load_json(file_path):
    """
    Load JSON data from a file. Returns an empty list if file is missing or error occurs.
    """
    if not os.path.exists(file_path):
        print(f"⚠️ File not found: {file_path}")
        return []

    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return []


def category_viewed(user_id: int):
    """
    Combine search and purchase cache for a user.
    Returns None if both caches are missing.
    """
    search_file = f"data/cache_searches_{user_id}.json"
    purchase_file = f"data/cache_purchase_{user_id}.json"

    data_s = load_json(search_file)
    data_p = load_json(purchase_file)

    # If both caches are empty, return None
    if not data_s and not data_p:
        return None

    
    return {
        "search": data_s or [],
        "purchase": data_p or []
    }
