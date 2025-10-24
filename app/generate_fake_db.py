import json
import random

def generate_fake_db(num_users=500):
    categories = [
        "electronics", "fashion", "home", "books", "toys", 
        "beauty", "sports", "automotive", "groceries", "furniture"
    ]

    users = []
    for user_id in range(1, num_users + 1):
        search_count = random.randint(5, 15)
        purchase_count = random.randint(2, 10)

        category_list = [random.choice(categories) for _ in range(search_count)]
        product_list = [random.choice(categories) for _ in range(purchase_count)]

        users.append({
            "user_id": user_id,
            "category": category_list,
            "product_category": product_list
        })

    db = {"users": users}

    with open("data/fake_database.json", "w") as f:
        json.dump(db, f, indent=4)

    print(f"✅ Fake database created with {num_users} users at data/fake_database.json")


if __name__ == "__main__":
    generate_fake_db(500)  # you can change number of users here
