import os
from dotenv import load_dotenv
import openai
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime


load_dotenv()# Load environment variables from .env file

# Set your API key (directly or via environment variable)
AI_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_client = MongoClient("mongodb://localhost:27017/")

db = DB_client["News"]
topics = db["Topics"]
topic_updates = db["Topic updates"]


def new_topic(user_topic):
    user_topics = user_topic.lower().split(",")  # Normalize and split if string input

    # Check if the topic already exists in the database
    existing_topic = topics.find_one({"keywords": user_topics})

    if existing_topic:
        keyword_id = existing_topic["_id"]
        score = check_topic_score(keyword_id)  # Get the score of the existing topic
    else:
        # Creating "topics" in MongoDB
        topic = topics.insert_one({"keywords": user_topics})
        keyword_id = topic.inserted_id
        score = 0

    # Creating "summary" for the topic using GPT
    response = AI_client.chat.completions.create(
        model="gpt-4o",  # or "gpt-3.5-turbo"
        messages=[
            {"role": "system", "content": "You are a journalist and you write with a news like style. Don't forget some interesting facts or headlines about the topic"
            " the user will give you. MAX 100 words"},
            {"role": "user", "content": f"Can you tell me some news about the {user_topics}"}
        ]
    )

    # Creating a timestamp for the update
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Creating "topicupdates" in MongoDB
    topic_updates.insert_one({
        "topic_id": keyword_id,
        "summary": response.choices[0].message.content,
        "score": score, # When created, score is set to 0
        "update_time": timestamp
    })

def seach_by_keyword(keyword):
    keyword = keyword.lower()  # Normalize the keyword to lowercase
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
    # Checking the score of a topic
    latest_topic_update = topic_updates.find_one({"topic_id": topic_id}, sort=[("update_time", -1)])  # Get the most recent update
    
    response = AI_client.chat.completions.create(
    model="gpt-4",  # or "gpt-3.5-turbo"
    messages=[
        {"role": "system", "content": "You are a helpful assistant. Your answer is going to be only a number from 0 to 1 rounded to 2 decimal places. 0 is not relevant and 1 is very relevant."},
        {"role": "user", "content": f"Here is my text: {latest_topic_update['summary']}. Can you give me a score for this topic update?"},
        ]
    )

    return float(response.choices[0].message.content.strip())

def update_using_id(topic_id):
    keywords = topics.find_one({"_id": topic_id})["keywords"]
    new_topic(keywords)  # Reuse the new_topic function to update the topic

def full_update():
    # Full update of all topics
    updates = 0
    for topic in topics.find():
        topic_id = topic["_id"]
        latest_topic_update = topic_updates.find_one({"topic_id": topic_id}, sort=[("update_time", -1)])  # Get the most recent update

        if latest_topic_update:
            score = check_topic_score(topic_id)  # Get the score of the existing topic
            if score <= 0.5:
                print(f"Topic ID: {topic_id} is not relevant anymore.\n updating it...")
                update_using_id(topic_id)
                updates += 1
    
    if updates == 0:
        print("All topics are relevant, no updates needed.")
    else:
        print(f"Updated {updates} topics.")


# Creating a new topic with initial keywords (vvvv EXAMPLE vvvv)
#new_topic(["nuclear weapons", "war", "Russia", "Ukraine"])
#new_topic(["Russia", "Military"])

# Searching for topics by keyword (vvvv EXAMPLE vvvv)
#seach_by_keyword("Russia")

# Checking the score of a topic (vvvv EXAMPLE vvvv)
#check_topic_score(ObjectId('6894cf7cf27c64a21c14455f'))

#full_update()  # Full update of all topics