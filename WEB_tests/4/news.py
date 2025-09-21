import os
from dotenv import load_dotenv
import openai
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI and MongoDB clients
AI_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_client = MongoClient("mongodb://localhost:27017/")

# Access MongoDB collections
db = DB_client["News"]
topics = db["Topics"]
topic_updates = db["Topic_updates"]

# Create a new topic and generate a news article using OpenAI
def new_topic(user_topic, created_by=None):
    user_topics = [topic.strip().lower() for topic in user_topic.split(",")]
    existing_topic = topics.find_one({"keywords": user_topics})

    if existing_topic:
        keyword_id = existing_topic["_id"]
        check_topic_score(keyword_id)
    else:
        topic = topics.insert_one({"keywords": user_topics})
        keyword_id = topic.inserted_id

    response = AI_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a journalist writing in a news style. Max 500 words. "
                    "Make the first line a headline. Then leave an empty line and write a brief summary. "
                    "After that leave another empty line and write the rest of the article and leave two empty lines at the end. "
                    "After that list the sources. Each source in next line starting with a dash. Do not include any URLs."
                )
            },
            {
                "role": "user",
                "content": f"Can you tell me some news about the {user_topics}?"
            }
        ]
    )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Parse response into headline, summary, and article body
    headline = response.choices[0].message.content.split("\n")[0]
    summary = (
        response.choices[0].message.content.split("\n\n")[1]
        if len(response.choices[0].message.content.split("\n\n")) > 1
        else ""
    )
    article_body = (
        "\n\n".join(response.choices[0].message.content.split("\n\n")[2:])
        if len(response.choices[0].message.content.split("\n\n")) > 2
        else ""
    )

    inserted = topic_updates.insert_one({
        "topic_id": keyword_id,
        "name": headline,
        "summary": summary,
        "text": article_body,
        "score": 1,
        "update_time": timestamp,
        "created_by": created_by
    })

    return inserted.inserted_id

# Search for topics by keyword
def search_by_keyword(keyword):
    keyword = keyword.lower()
    results = []

    for topic in topics.find({"keywords": keyword}):
        updates = topic_updates.find(
            {"topic_id": topic["_id"]}
        ).sort("update_time", -1)

        for text in updates:
            results.append({
                "id": str(text["_id"]),
                "headline": text["name"],
                "summary": text["summary"],
                "text": text["text"],
                "score": text["score"],
                "update_time": text["update_time"]
            })

    return results

# Get the relevance score for a topic update using OpenAI
def check_topic_score(topic_id):
    latest_topic_update = topic_updates.find_one({"topic_id": topic_id}, sort=[("update_time", -1)])
    response = AI_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Return only a number from 0 to 1, rounded to 2 decimals. "
             "The number represents the relevance of the topic to the current time. "
             "With 1 being very relevant and 0 being not relevant at all."},
            {"role": "user", "content": f"Here is my text: {latest_topic_update['summary']}. Score it."},
        ]
    )
    score = float(response.choices[0].message.content.strip())

    topic_updates.update_one(
        {"_id": latest_topic_update["_id"]},
        {"$set": {"score": score}}
    )

    return score

# Update a topic by its ID
def update_using_id(topic_id):
    keywords = topics.find_one({"_id": topic_id})["keywords"]
    new_topic(keywords)

# Perform a full update of all topics
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

# Get paginated topic updates for the news feed
def get_popular_updates(skip, limit):
    return list(topic_updates.find().sort("update_time", -1).skip(skip).limit(limit))
