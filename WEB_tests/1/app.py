from flask import Flask, request, render_template, redirect
from bson.objectid import ObjectId
from news import new_topic, seach_by_keyword, check_topic_score, update_using_id, full_update, topics

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/add_topic', methods=['POST'])
def add_topic():
    keyword = request.form.get('keyword')
    if keyword:
        new_topic(keyword)  # wrap in list if your function expects a list
    return redirect('/')

@app.route('/search', methods=['GET'])
@app.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('keyword')
    results = seach_by_keyword(keyword) if keyword else []
    return render_template('search.html', keyword=keyword, results=results)


@app.route('/full_update')
def trigger_full_update():
    full_update()
    return "Full update triggered. Go back to <a href='/'>home</a>."

if __name__ == '__main__':
    app.run(debug=True)
