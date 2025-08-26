from flask import Flask, request, render_template, redirect, jsonify
from bson.objectid import ObjectId
from news import new_topic, search_by_keyword, check_topic_score, update_using_id, full_update, topics, topic_updates, get_popular_updates

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/add_topic', methods=['POST'])
def add_topic():
    keyword = request.form.get('keywords')
    if keyword:
        new_topic(keyword)
    return redirect('/')

@app.route('/search', methods=['GET'])
def search():
    keywords = request.args.get('keyword')
    results = search_by_keyword(keywords)
    return render_template('search.html', keyword=keywords, result=results)

@app.route('/full_update')
def trigger_full_update():
    full_update()
    return "Full update triggered. Go back to <a href='/'>home</a>."

# 🔥 NEW API endpoint for infinite scroll
@app.route('/api/news')
def api_news():
    page = int(request.args.get("page", 1))
    per_page = 10
    skip = (page - 1) * per_page

    updates = get_popular_updates(skip, per_page)

    items = []
    for u in updates:
        topic = topics.find_one({"_id": u["topic_id"]})
        items.append({
            "headline": ", ".join(topic["keywords"]),
            "summary": u["summary"],
            "score": u["score"],
            "time": u["update_time"]
        })

    return jsonify(items)

if __name__ == '__main__':
    app.run(debug=True)
