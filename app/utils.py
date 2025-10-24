import json
import os

def save_json(file_path, data):
    """Safely save Python object to JSON file."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4, default=str)
    except Exception as e:
        print(f"❌ Error saving {file_path}: {e}")

def load_json(file_path):
    """Safely load JSON data from a file."""
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {file_path}: {e}")
        return None

def log(message, level="info"):
    prefix = {"info": "ℹ️", "warn": "⚠️", "error": "❌"}.get(level, "🔹")
    print(f"{prefix} {message}")
