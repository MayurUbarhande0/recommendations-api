import math
import json

def weightage_assigner(result: dict, user_id: int):
    """
    Calculates weightage scores for a user's activity
    based on their viewed and purchased categories.
    """

    
    category_list = result.get("category", [])
    duplicate_searches = len(category_list) - len(set(category_list))
    unique_searches = len(set(category_list))

    weightage_se = duplicate_searches * 2 + (unique_searches / 10)

    
    product_list = result.get("product_category", [])
    duplicate_purchases = len(product_list) - len(set(product_list))
    unique_purchases = len(set(product_list))

    weightage_pp = duplicate_purchases * 2 + (unique_purchases / 10)

    total_weight = round(weightage_se + weightage_pp, 2)

    result_data = {
        "user_id": user_id,
        "weightage_search": round(weightage_se, 2),
        "weightage_purchase": round(weightage_pp, 2),
        "overall_weight": total_weight
    }

    
    with open(f"data/cache_weight_{user_id}.json", "w") as f:
        json.dump(result_data, f, indent=4)

    print(f"✅ Weightage file created for user {user_id}: data/cache_weight_{user_id}.json")

    return result_data
