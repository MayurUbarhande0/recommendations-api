import json
import os
import math

def weightage_assigner(result: dict, user_id: int):
    """
    Calculates weightage scores for a user's activity
    based on their viewed and purchased categories.
    """

    # Extract categories from search and purchase data
    category_list = [item["category"] for item in result.get("search", [])]
    product_list = [item["product_category"] for item in result.get("purchase", [])]

    # Compute duplicates and unique counts
    duplicate_searches = len(category_list) - len(set(category_list))
    unique_searches = len(set(category_list))
    weightage_search = duplicate_searches * 2 + (unique_searches / 10)

    duplicate_purchases = len(product_list) - len(set(product_list))
    unique_purchases = len(set(product_list))
    weightage_purchase = duplicate_purchases * 2 + (unique_purchases / 10)

    total_weight = round(weightage_search + weightage_purchase, 2)

    # Build unique and duplicate lists
    def split_unique_duplicates(lst):
        unique = []
        duplicates = []
        for item in lst:
            if item not in unique:
                unique.append(item)
            else:
                duplicates.append(item)
        return unique, duplicates

    unique_categories, duplicate_categories = split_unique_duplicates(category_list)
    unique_products, duplicate_products = split_unique_duplicates(product_list)

    result_data = {
        "user_id": user_id,
        "weightage_search": round(weightage_search, 2),
        "weightage_purchase": round(weightage_purchase, 2),
        "overall_weight": total_weight,
        "search_category_unique": unique_categories,
        "search_category_duplicates": duplicate_categories,
        "purchase_category_unique": unique_products,
        "purchase_category_duplicates": duplicate_products
    }

    # Save weightage cache
    os.makedirs("data", exist_ok=True)
    weight_file = f"data/cache_weight_{user_id}.json"
    with open(weight_file, "w") as f:
        json.dump(result_data, f, indent=4)

    print(f"✅ Weightage file created for user {user_id}: {weight_file}")
    for fname in (f"data/cache_purchase_{user_id}.json", f"data/cache_searches_{user_id}.json"):
        try:
            os.remove(fname)
        except FileNotFoundError:
            # file already removed or never created; ignore
            pass
        except OSError as e:
            # log other errors but continue
            print(f"⚠️ Could not delete {fname}: {e}")

    return result_data
