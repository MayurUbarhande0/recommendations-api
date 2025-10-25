import json
import os
from typing import Optional, Dict, List

def load_json(file_path: str) -> List[dict]:
    """
    Load JSON data from a file. Returns an empty list if file is missing or error occurs.
    Converts BIT/TINYINT(1) values to Python bool.
    """
    if not os.path.exists(file_path):
        print(f"⚠️ File not found: {file_path}")
        return []

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        # Convert any BIT/TINYINT fields to bool automatically
        for entry in data:
            for key, value in entry.items():
                if value in (0, 1):
                    entry[key] = bool(value)
        return data
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return []

def category_viewed(user_id: int, merge_categories: bool = False) -> Optional[Dict[str, List[dict]]]:
    """
    Combine search and purchase cache for a user.
    If merge_categories=True, returns a set of all categories viewed/purchased.
    """
    search_file = f"data/cache_search_{user_id}.json"
    purchase_file = f"data/cache_purchase_{user_id}.json"

    search_data = load_json(search_file)
    purchase_data = load_json(purchase_file)

    if not search_data and not purchase_data:
        return None

    result = {
        "search": search_data or [],
        "purchase": purchase_data or []
    }

    if merge_categories:
        categories = set()
        for item in search_data:
            if "category" in item:
                categories.add(item["category"])
        for item in purchase_data:
            if "product_category" in item:
                categories.add(item["product_category"])
        result["all_categories"] = list(categories)

    return result
