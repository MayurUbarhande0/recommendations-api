import os
from database import get_search_data, get_recent_purchased
from cache_manager import category_viewed
from recommender import weightage_assigner

# ------------------------------
# Users to test
# ------------------------------
user_ids = [1, 2]  # Test for dummy users

# ------------------------------
# Step 1: Fetch & cache data
# ------------------------------
for user_id in user_ids:
    search_file = f"data/cache_searches_{user_id}.json"
    purchase_file = f"data/cache_purchase_{user_id}.json"

    # Fetch search data if cache missing or empty
    if not os.path.exists(search_file) or os.path.getsize(search_file) == 0:
        print(f"⚙️ Fetching search data for user {user_id}")
        get_search_data(user_id)

    # Fetch purchase data if cache missing or empty
    if not os.path.exists(purchase_file) or os.path.getsize(purchase_file) == 0:
        print(f"⚙️ Fetching purchase data for user {user_id}")
        get_recent_purchased(user_id)

# ------------------------------
# Step 2: Load cache and compute weightage
# ------------------------------
for user_id in user_ids:
    data = category_viewed(user_id)

    if data is None:
        print(f"❌ No cache data available for user {user_id}")
        continue

    # Prepare input for weightage_assigner
    input_data = {
        "category": data.get("category_viewed", []),
        "product_category": data.get("recently_purchased", [])
    }

    # Compute weight
    weights = weightage_assigner(input_data, user_id)

    print(f"\n✅ Final weightage for user {user_id}:")
    print(weights)
