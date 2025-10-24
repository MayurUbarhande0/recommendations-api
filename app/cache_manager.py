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
    "category_viewed": [row["category"] for row in data_s],
    "recently_purchased": [row["product_category"] for row in data_p]
   }

    return result
