from flask import Flask, request, render_template, redirect, url_for, session, flash
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from bson import ObjectId
import markdown2, json

app = Flask(__name__)
app.secret_key = 'TH3EY3@CS34!'  # Change this to a more secure key

client = MongoClient('mongodb+srv://theeye:test@eyecommunity.48uzc.mongodb.net/?retryWrites=true&w=majority&appName=eyeCommunity', server_api=ServerApi('1'))
db = client['eyeCommunity']
events_collection = db['events']
discussions_collection = db['discussions']

class Session(BaseModel):
    name: str
    speaker: str
    start_time: str
    end_time: str
    resources: Optional[str]

class Event(BaseModel):
    event_type: str
    event_name: str
    event_date: str
    event_location: str
    event_desc: str
    event_metadata: Optional[Dict[str, str]] = None
    sessions: Optional[List[Session]] = None
    rsvp_link: Optional[str] = None
    archived: bool = False
    recordings: Optional[str] = None

# Convert Markdown to HTML
def md_to_html(md_text):
    return markdown2.markdown(md_text)

@app.before_request
def check_session_expiration():
    expires = session.get('expires')
    if expires:
        expiration_time = datetime.fromisoformat(expires)
        if datetime.utcnow() > expiration_time:
            session.clear()

@app.route('/')
def index():
    is_authed = 'username' in session
    return render_template('home.html', is_authed=is_authed)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'theeye' and password == 'theEye@CS3A':
            session['username'] = username
            session['expires'] = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
            return redirect(url_for('index'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('expires', None)
    return redirect(url_for('index'))

# CRUD for Events
@app.route('/events')
def get_events():
    is_authed = 'username' in session
    events = list(events_collection.find())
    return render_template('events.html', events=events, is_authed=is_authed)

@app.route('/events/create', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        event_type = request.form['event_type']
        event_name = request.form['event_name']
        event_date = request.form['event_date']
        event_location = request.form['event_location']
        event_desc = request.form['event_desc']
        event_metadata = request.form.get('event_metadata', '')
        sessions = request.form.get('sessions', '')
        rsvp_link = request.form.get('rsvp_link', '')
        archived = 'archived' in request.form
        recordings = request.form.get('recordings', '')

        event_metadata = {kv.split(":")[0]: kv.split(":")[1] for kv in event_metadata.split(",")} if event_metadata else None
        sessions = [{'name': s.split("|")[0], 'speaker': s.split("|")[1], 'start_time': s.split("|")[2], 'end_time': s.split("|")[3], 'resources': s.split("|")[4]} for s in sessions.split(",")] if sessions else None

        event = Event(
            event_type=event_type,
            event_name=event_name,
            event_date=event_date,
            event_location=event_location,
            event_desc=md_to_html(event_desc),
            event_metadata=event_metadata,
            sessions=sessions,
            rsvp_link=rsvp_link if not archived else None,
            archived=archived,
            recordings=recordings
        )
        events_collection.insert_one(event.dict())
        return redirect(url_for('get_events'))

    return render_template('event_form.html', is_authed='username' in session)

@app.route('/events/update', methods=['GET', 'POST'])
def update_event():
    event_id = request.form.get("event_id")
    event = events_collection.find_one({"_id": ObjectId(event_id)})
    if not event:
        print("NOT EVENT", event_id)
        return redirect(url_for('get_events'))

    if request.method == 'POST':
        event_type = request.form['event_type']
        event_name = request.form['event_name']
        event_date = request.form['event_date']
        event_location = request.form['event_location']
        event_desc = request.form['event_desc']
        event_metadata = request.form.get('event_metadata', '')
        sessions = request.form.get('sessions', '')
        rsvp_link = request.form.get('rsvp_link', '')
        archived = 'archived' in request.form
        recordings = request.form.get('recordings', '')

        event_metadata = {kv.split(":")[0]: kv.split(":")[1] for kv in event_metadata.split(",")} if event_metadata else None
        sessions = [{'name': s.split("|")[0], 'speaker': s.split("|")[1], 'start_time': s.split("|")[2], 'end_time': s.split("|")[3], 'resources': s.split("|")[4]} for s in sessions.split(",")] if sessions else None

        updated_event = Event(
            event_type=event_type,
            event_name=event_name,
            event_date=event_date,
            event_location=event_location,
            event_desc=event_desc,  # Assuming md_to_html function is not needed in update
            event_metadata=event_metadata,
            sessions=sessions,
            archived=archived,
            recordings=recordings
        )
        events_collection.update_one({"_id": ObjectId(event_id)}, {"$set": updated_event.dict()})
        return redirect(url_for('get_events'))

    # Convert event metadata and sessions to required input formats
    event_metadata_str = ",".join([f"{key}:{value}" for key, value in event["event_metadata"].items()]) if event["event_metadata"] else ''
    sessions_str = ",".join([ "|".join([s["name"], s["speaker"], s["start_time"], s["end_time"], s["resources"]]) for s in event["sessions"] ]) if event['sessions'] else ''

    return render_template('update_event.html', event=event, event_metadata_str=event_metadata_str, sessions_str=sessions_str, is_authed='username' in session)

@app.route('/events/delete/', methods=['GET', 'POST'])
def delete_event():
    event_id = request.args.get("event_id")
    if request.method == 'POST':
        event_id = request.form.get("event_id")
        result = events_collection.delete_one({"_id": ObjectId(event_id)})
        if result.deleted_count == 0:
            flash('Event not found', 'error')
        return redirect(url_for('get_events'))
    
    event = events_collection.find_one({"_id": ObjectId(event_id)})
    if not event:
        return redirect(url_for('get_events'))
    
    return render_template('confirm_delete.html', event=event, is_authed='username' in session)

# Community Discussion
@app.route('/community')
def get_community():
    tag = request.args.getlist('tag')
    filter_query = {}
    if tag:
        filter_query["tags"] = {"$in": tag}
    discussions = list(discussions_collection.find(filter_query))
    tag_colors = {
        "event-related": "primary",
        "cybersecurity": "success",
        "networking": "warning",
        "design": "info",
        "technical": "danger",
        "weekend event related": "secondary"
    }
    return render_template('community.html', discussions=discussions, tag_colors=tag_colors, is_authed='username' in session)

@app.route('/community/comment', methods=['POST'])
def post_comment():
    comment = request.form['comment']
    author = request.form['author']
    topic = request.form.get('topic', '')
    tags = request.form['tags']
    tag_list = [tag["value"] for tag in json.loads(tags)]
    discussions_collection.insert_one({"comment": comment, "author": author, "topic": topic, "tags": tag_list, "replies": []})
    return redirect(url_for('get_community'))

@app.route('/community/comment/<comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    result = discussions_collection.delete_one({"_id": ObjectId(comment_id)})
    if result.deleted_count == 0:
        return {"status": "error", "message": "Comment not found"}, 404
    return {"status": "success", "comment_id": comment_id}

@app.route('/community/reply/<comment_id>', methods=['POST'])
def post_reply(comment_id):
    comment = request.form['comment']
    author = request.form['author']
    reply = {"_id": ObjectId(), "comment": comment, "author": author}
    result = discussions_collection.update_one({"_id": ObjectId(comment_id)}, {"$push": {"replies": reply}})
    if result.modified_count == 0:
        return {"status": "error", "message": "Comment not found"}, 404
    return redirect(url_for('get_community'))

@app.route('/community/comment/<comment_id>/replies', methods=['GET'])
def get_replies(comment_id):
    discussion = discussions_collection.find_one({"_id": ObjectId(comment_id)})
    if not discussion:
        return {"status": "error", "message": "Comment not found"}, 404
    return {"status": "success", "replies": discussion.get("replies", [])}

@app.route('/community/reply/<reply_id>/<comment_id>', methods=['DELETE'])
def delete_reply(reply_id, comment_id):
    # Check if the comment exists
    comment = discussions_collection.find_one({"_id": ObjectId(comment_id)})
    if not comment:
        return {"status": "error", "message": "Comment not found"}, 404
    
    # Remove the reply
    result = discussions_collection.update_one(
        {"_id": ObjectId(comment_id)},
        {"$pull": {"replies": {"_id": ObjectId(reply_id)}}}
    )
    
    if result.modified_count == 0:
        return {"status": "error", "message": "Reply not found or failed to delete"}, 404
    
    return {"status": "success", "reply_id": reply_id}


if __name__ == '__main__':
    app.run(debug=True)
