import os
from dotenv import load_dotenv
import openai
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime

load_dotenv()  # Load environment variables

AI_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_client = MongoClient("mongodb://localhost:27017/")

db = DB_client["News"]
topics = db["Topics"]
topic_updates = db["Topic updates"]

def new_topic(user_topic):
    user_topics = [topic.strip().lower() for topic in user_topic.split(",")]
    existing_topic = topics.find_one({"keywords": user_topics})

    if existing_topic:
        keyword_id = existing_topic["_id"]
        score = check_topic_score(keyword_id)
    else:
        topic = topics.insert_one({"keywords": user_topics})
        keyword_id = topic.inserted_id
        score = 0

    response = AI_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a journalist writing in a news style. Max 100 words."},
            {"role": "user", "content": f"Can you tell me some news about the {user_topics}?"}
        ]
    )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    topic_updates.insert_one({
        "topic_id": keyword_id,
        "summary": response.choices[0].message.content,
        "score": score,
        "update_time": timestamp
    })

def search_by_keyword(keyword):
    keyword = keyword.lower()
    results = []

    for topic in topics.find({"keywords": keyword}):
        updates = topic_updates.find({"topic_id": topic["_id"]})
        for text in updates:
            results.append({
                "summary": text["summary"],
                "score": text["score"],
                "update_time": text["update_time"]
            })
    return results

def check_topic_score(topic_id):
    latest_topic_update = topic_updates.find_one({"topic_id": topic_id}, sort=[("update_time", -1)])
    response = AI_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Return only a number from 0 to 1, rounded to 2 decimals."},
            {"role": "user", "content": f"Here is my text: {latest_topic_update['summary']}. Score it."},
        ]
    )
    return float(response.choices[0].message.content.strip())

def update_using_id(topic_id):
    keywords = topics.find_one({"_id": topic_id})["keywords"]
    new_topic(keywords)

def full_update():
    updates = 0
    for topic in topics.find():
        topic_id = topic["_id"]
        latest_topic_update = topic_updates.find_one({"topic_id": topic_id}, sort=[("update_time", -1)])
        if latest_topic_update:
            score = check_topic_score(topic_id)
            if score <= 0.5:
                update_using_id(topic_id)
                updates += 1
    print("All topics are relevant" if updates == 0 else f"Updated {updates} topics.")

def get_popular_updates(skip=0, limit=10):
    return topic_updates.find().sort([("score", -1), ("update_time", -1)]).skip(skip).limit(limit)
