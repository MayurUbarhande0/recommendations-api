import mysql.connector
import json

# Connect to local MySQL server
conn = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="Mayur@12",  # replace with your root password
    port=3306,
    database="searches"   # replace with your DB name
)

cursor = conn.cursor(dictionary=True)  # fetch results as dictionaries

# Fetch all data from a table
cursor.execute("SELECT * FROM searches")
rows = cursor.fetchall()

# Save as JSON cache
with open("cache.json", "w") as f:
    json.dump(rows, f, indent=4)

# Close connections
cursor.close()
conn.close()

print("Database cached to cache.json successfully!")
