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
            {"role": "system", "content": "You are a journalist writing in a news style. Max 500 words. Make the first line a headline. Then leave an empty line and write a brief summary. After that leave another empty line and write the rest of the article."},
            {"role": "user", "content": f"Can you tell me some news about the {user_topics}?"}
        ]
    )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    headline = response.choices[0].message.content.split("\n")[0]
    summary = response.choices[0].message.content.split("\n\n")[1] if len(response.choices[0].message.content.split("\n\n")) > 1 else ""
    article_body = "\n\n".join(response.choices[0].message.content.split("\n\n")[2:]) if len(response.choices[0].message.content.split("\n\n")) > 2 else ""

    topic_updates.insert_one({
        "topic_id": keyword_id,
        "name": headline,
        "summary": summary,
        "text": article_body,
        "score": score,
        "update_time": timestamp
    })

def search_by_keyword(keyword):
    keyword = keyword.lower()
    results = []

    for topic in topics.find({"keywords": keyword}):
        updates = topic_updates.find(
            {"topic_id": topic["_id"]}
        ).sort("update_time", -1)  # newest → oldest

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

def get_popular_updates(skip, limit):
    return list(topic_updates.find().sort("update_time", -1).skip(skip).limit(limit))



# Creating a new topic with initial keywords (vvvv EXAMPLE vvvv)
#new_topic("nuclear weapons, war, Russia, Ukraine")
#new_topic("Russia, Military")

# Searching for topics by keyword (vvvv EXAMPLE vvvv)
#print(search_by_keyword("Russia"))

# Checking the score of a topic (vvvv EXAMPLE vvvv)
#check_topic_score(ObjectId('6894cf7cf27c64a21c14455f'))

#full_update()  # Full update of all topics

# extra_keywords = [
#     "ai, robotics, automation, future",
#     "space, mars, colonization, nasa",
#     "finance, crypto, markets, investment",
#     "sports, olympics, football, athletes",
#     "climate, global warming, renewable, energy",
#     "technology, startups, ai, innovation",
#     "health, nutrition, public health, fitness",
#     "politics, elections, democracy, law",
#     "science, discoveries, astronomy, research",
#     "environment, wildlife, conservation, forests"
# ]


# for item in extra_keywords:
#     new_topic(item)
#     print(f"Added topic: {item}")
