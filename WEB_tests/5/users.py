from datetime import datetime
from pymongo import MongoClient

DB_client = MongoClient("mongodb://localhost:27017/")
db = DB_client["News"]
users = db["Users"]

def create_user(username, password_hash):
    return users.insert_one({
        "username": username,
        "password": password_hash,
        "tokens": 3,
        "created_at": datetime.now()
    })

def get_user(username):
    return users.find_one({"username": username})

def use_token(username):
    user = get_user(username)
    if user and user["tokens"] > 0:
        users.update_one({"username": username}, {"$inc": {"tokens": -1}})
        return True
    return False

def reset_all_tokens():
    users.update_many({}, {"$set": {"tokens": 3}})
