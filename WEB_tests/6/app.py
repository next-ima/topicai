from flask import Flask, request, render_template, redirect, jsonify, session, url_for
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from news import (
    new_topic,
    search_by_keyword,
    full_update,
    topics,
    topic_updates,
    get_popular_updates,
    add_voting_keyword,
    vote_keyword,
    get_voting_keywords,
    clear_voting
)
from users import (
    create_user,
    get_user,
    use_token,
    reset_all_tokens
)
from security import (
    validate_topic_list,
    validate_keyword,
    safe_object_id
)

app = Flask(__name__)
app.secret_key = "super-secret"
ADMIN_PASSWORD = "changeme"


# --- Home ---
@app.route('/')
def home():
    return render_template('index.html', selected_group="Home")


# --- Search ---
@app.route('/search', methods=['GET'])
def search():
    keywords = request.args.get('keyword', '')
    try:
        validated = validate_keyword(keywords)
    except ValueError:
        return render_template('search.html', keyword=keywords, result=[], error="Invalid search term")
    results = search_by_keyword(validated)
    return render_template('search.html', keyword=validated, result=results)


# --- API feed ---
@app.route('/api/news')
def api_news():
    page = int(request.args.get("page", 1))
    per_page = 10
    skip = (page - 1) * per_page
    group = request.args.get("group", "Home")

    if group == "Home":
        updates = get_popular_updates(skip, per_page)
    else:
        updates = list(topic_updates.find({"group": group}).sort("update_time", -1).skip(skip).limit(per_page))

    items = []
    for u in updates:
        items.append({
            "id": str(u["_id"]),
            "headline": u["name"],
            "summary": u["summary"],
            "time": u["update_time"]
        })

    return jsonify(items)


# --- Article detail ---
@app.route('/article/<id>')
def article(id):
    try:
        oid = safe_object_id(id)
    except ValueError:
        return "Invalid article id", 400

    article = topic_updates.find_one({"_id": oid})
    if not article:
        return "Article not found", 404
    topic = topics.find_one({"_id": article["topic_id"]})
    return render_template("article.html", article=article, topic=topic)


# --- Filter by group ---
@app.route('/filter/<group>')
def filter_news(group):
    return render_template('index.html', selected_group=group)


# --- User auth ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        if get_user(username):
            return render_template("register.html", error="User already exists")
        password = generate_password_hash(request.form["password"])
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
    keywords = get_voting_keywords()
    return render_template("voting.html", keywords=keywords, user=user)


@app.route("/submit_keyword", methods=["POST"])
def submit_keyword():
    if "username" not in session:
        return redirect(url_for("login"))
    keyword = request.form.get("keyword", "")
    try:
        validated_kw = validate_keyword(keyword)
    except ValueError:
        return "Invalid keyword", 400

    if validated_kw and use_token(session["username"]):
        add_voting_keyword(validated_kw, session["username"])
        return redirect(url_for("voting"))

    return "Not enough tokens"


@app.route("/vote_keyword/<id>")
def vote_keyword_route(id):
    if "username" not in session:
        return redirect(url_for("login"))
    if use_token(session["username"]):
        vote_keyword(id)
        return redirect(url_for("voting"))
    return "No tokens left"


# --- Weekly winners ---
@app.route("/weekly_winners")
def weekly_winners():
    top_keywords = get_voting_keywords()[:5]
    for k in top_keywords:
        try:
            toks = validate_topic_list(k["keyword"])
        except ValueError:
            continue
        new_topic(",".join(toks), created_by=k["created_by"])

    reset_all_tokens()
    clear_voting()

    return redirect(url_for("voting"))


# --- Topics update ---
@app.route("/update")
def update():
    full_update()


if __name__ == '__main__':
    app.run(debug=True)
    #app.run(host="0.0.0.0", port=5000, debug=True)
