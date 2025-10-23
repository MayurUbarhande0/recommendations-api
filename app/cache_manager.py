import json
import os

# -------------------------------
# Load JSON safely
# -------------------------------
def load_json(file_path):
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

# -------------------------------
# Combine category viewed + purchases
# -------------------------------
def category_viewed(user_id):
    # Per-user cache files
    search_file = f"data/cache_searches_{user_id}.json"
    purchase_file = f"data/cache_purchase_{user_id}.json"

    data_s = load_json(search_file)
    data_p = load_json(purchase_file)

    if not data_s or not data_p:
        return None  # missing cache

    # Return combined dictionary
    result = {
        "category_viewed": data_s.get("category", []),
        "recently_purchased": data_p.get("purchased", [])
    }
    return result
