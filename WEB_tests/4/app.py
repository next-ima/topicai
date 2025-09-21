from flask import Flask, request, render_template, redirect, jsonify, session, url_for
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from news import (
    new_topic,
    search_by_keyword,
    full_update,
    topics,
    topic_updates,
    get_popular_updates
)
from users import (
    create_user,
    get_user,
    use_token,
    reset_all_tokens
)

app = Flask(__name__)
app.secret_key = "super-secret"
ADMIN_PASSWORD = "changeme"

# Home page
@app.route('/')
def home():
    return render_template('index.html')

# Add topic (admin only)
@app.route('/add_topic', methods=['POST'])
def add_topic():
    keyword = request.form.get('keywords')
    if keyword:
        new_topic(keyword, created_by="admin")
    return redirect('/')

# Search topics
@app.route('/search', methods=['GET'])
def search():
    keywords = request.args.get('keyword')
    results = search_by_keyword(keywords)
    return render_template('search.html', keyword=keywords, result=results)

# Trigger full update
@app.route('/full_update')
def trigger_full_update():
    full_update()
    return "Full update triggered. Go back to <a href='/'>home</a>."

# API endpoint for news feed
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

# Article detail
@app.route('/article/<id>')
def article(id):
    article = topic_updates.find_one({"_id": ObjectId(id)})
    if not article:
        return "Article not found", 404
    topic = topics.find_one({"_id": article["topic_id"]})
    return render_template("article.html", article=article, topic=topic)

# --- Admin login ---
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

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    return render_template("admin.html")

@app.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("home"))

# --- User auth ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        if get_user(username):
            return render_template("register.html", error="User already exists")
        create_user(username, password)
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = get_user(username)
        if user and check_password_hash(user["password"], password):
            session["username"] = username
            return redirect("/")
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")

# --- Voting system ---
@app.route("/voting")
def voting():
    if "username" not in session:
        return redirect(url_for("login"))

    user = get_user(session["username"])
    articles = list(topic_updates.find().sort("score", -1))  # sort by votes
    return render_template("voting.html", articles=articles, user=user)

@app.route("/vote/<id>")
def vote(id):
    if "username" not in session:
        return redirect(url_for("login"))
    if use_token(session["username"]):
        topic_updates.update_one(
            {"_id": ObjectId(id)},
            {"$inc": {"score": 1}}
        )
        return redirect(url_for("voting"))
    return "No tokens left"

@app.route("/submit_topic", methods=["POST"])
def submit_topic():
    if "username" not in session:
        return redirect(url_for("login"))
    keywords = request.form.get("keywords")
    if keywords and use_token(session["username"]):
        new_topic(keywords, created_by=session["username"])
        return redirect(url_for("voting"))
    return "Not enough tokens"

# --- Weekly winners ---
@app.route("/weekly_winners")
def weekly_winners():
    cutoff = datetime.now() - timedelta(days=7)
    winners = list(topic_updates.find({
        "update_time": {"$gte": cutoff.strftime("%Y-%m-%d %H:%M:%S")}
    }).sort("score", -1).limit(5))

    for w in winners:
        topic = topics.find_one({"_id": w["topic_id"]})
        if topic:
            new_topic(", ".join(topic["keywords"]))

    reset_all_tokens()
    return redirect(url_for("voting"))

if __name__ == '__main__':
    app.run(debug=True)
