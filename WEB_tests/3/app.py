from flask import Flask, request, render_template, redirect, jsonify, session, url_for
from bson.objectid import ObjectId
from news import (
    new_topic,
    search_by_keyword,
    full_update,
    topics,
    topic_updates,
    get_popular_updates
)

app = Flask(__name__)
app.secret_key = "super-secret"
ADMIN_PASSWORD = "changeme"

# Home page route
@app.route('/')
def home():
    return render_template('index.html')

# Add a new topic via POST form
@app.route('/add_topic', methods=['POST'])
def add_topic():
    keyword = request.form.get('keywords')
    if keyword:
        new_topic(keyword)
    return redirect('/')

# Search for topics by keyword
@app.route('/search', methods=['GET'])
def search():
    keywords = request.args.get('keyword')
    results = search_by_keyword(keywords)
    return render_template('search.html', keyword=keywords, result=results)

# Trigger a full update of all topics
@app.route('/full_update')
def trigger_full_update():
    full_update()
    return "Full update triggered. Go back to <a href='/'>home</a>."

# API endpoint for paginated news feed
@app.route('/api/news')
def api_news():
    page = int(request.args.get("page", 1))
    per_page = 10
    skip = (page - 1) * per_page

    updates = get_popular_updates(skip, per_page)

    items = []
    for u in updates:
        items.append({
            "id": str(u["_id"]),
            "headline": u["name"],
            "summary": u["summary"],
            "score": u["score"],
            "time": u["update_time"]
        })

    return jsonify(items)

# Article detail page
@app.route('/article/<id>')
def article(id):
    article = topic_updates.find_one({"_id": ObjectId(id)})
    if not article:
        return "Article not found", 404

    topic = topics.find_one({"_id": article["topic_id"]})
    return render_template("article.html", article=article, topic=topic)

# Admin login page
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        else:
            return render_template("admin_login.html", error="Invalid password")
    return render_template("admin_login.html")

# Admin dashboard
@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    return render_template("admin.html")

# Admin logout
@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

if __name__ == '__main__':
    app.run(debug=True)
