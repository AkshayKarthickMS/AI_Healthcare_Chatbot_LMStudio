from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from uuid import uuid4
import sqlite3
import os
import json
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure secret key

MODEL_URL = "http://127.0.0.1:1234/v1/chat/completions"

def init_db():
    if not os.path.exists('chatbot.db'):
        conn = sqlite3.connect('chatbot.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            password TEXT NOT NULL
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS chats (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            chat_id TEXT,
                            title TEXT,
                            messages TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY(user_id) REFERENCES users(id)
                          )''')
        conn.commit()
        conn.close()

init_db()

# Update existing database if needed
def update_db():
    conn = sqlite3.connect('chatbot.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE chats ADD COLUMN title TEXT")
        cursor.execute("ALTER TABLE chats ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.close()

update_db()

def chat_with_model(user_input, conversation_history):
    if len(conversation_history) == 0:
        conversation_history.append({
            "role": "system", 
            "content": "You are Dr. Akshay Karthick, a compassionate and concise doctor. Respond to patient queries with empathy and warmth, using 1-2 complete sentences. Ask only 1-2 questions at a time to keep the conversation focused. Offer virtual medications when appropriate and suggest physical visits only in rare cases. If any questions apart from medical queries are asked, respond like 'I'm a doctor, I can't answer those questions.' Always respond without exceeding 50 words limit. Also mainly provide the answer with the language same as the question and mainly respond with the language of  what the user provide their queries"
        })
    
    conversation_history.append({"role": "user", "content": user_input})
    
    payload = {
        "model": "llama-3.2-3b-instruct",
        "messages": conversation_history,
        "temperature": 0.8,
        "max_tokens": 100,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "top_p": 0.95,
        "min_p": 0.05,
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(MODEL_URL, json=payload, headers=headers)
        response.raise_for_status()
        model_reply = response.json().get('choices', [{}])[0].get('message', {})
        if 'content' in model_reply:
            conversation_history.append(model_reply)
            return model_reply['content']
        else:
            return "I'm having trouble understanding your request. Can you please rephrase it?"
    except requests.RequestException as e:
        return f"An error occurred: {e}"

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('chat_page'))
    return render_template('index.html')

@app.route('/chat_page')
def chat_page():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = sqlite3.connect('chatbot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user[2], password):
        session['user_id'] = user[0]
        session['username'] = username
        return jsonify({"success": True, "message": "Login successful"})
    return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password are required"}), 400

    hashed_password = generate_password_hash(password)
    
    conn = sqlite3.connect('chatbot.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                      (username, hashed_password))
        conn.commit()
        return jsonify({"success": True, "message": "Registration successful"})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Username already exists"}), 400
    finally:
        conn.close()

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})

@app.route('/get_specific_chat/<chat_id>')
def get_specific_chat(chat_id):
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401

    conn = sqlite3.connect('chatbot.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT messages 
        FROM chats 
        WHERE user_id = ? AND chat_id = ?
    """, (session['user_id'], chat_id))
    chat = cursor.fetchone()
    conn.close()

    if chat:
        messages = json.loads(chat[0])
        session['current_chat_id'] = chat_id
        session['conversation_history'] = messages
        return jsonify({
            "success": True,
            "messages": messages
        })
    return jsonify({"success": False, "message": "Chat not found"}), 404

@app.route('/set_current_chat', methods=['POST'])
def set_current_chat():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json()
    chat_id = data.get('chat_id')
    
    conn = sqlite3.connect('chatbot.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT messages 
        FROM chats 
        WHERE user_id = ? AND chat_id = ?
    """, (session['user_id'], chat_id))
    chat = cursor.fetchone()
    conn.close()
    
    if chat:
        session['current_chat_id'] = chat_id
        session['conversation_history'] = json.loads(chat[0])
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Chat not found"}), 404



@app.route('/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    user_input = data.get('message')
    chat_id = data.get('chatId') or session.get('current_chat_id')
    
    # Get or create conversation history
    conn = sqlite3.connect('chatbot.db')
    cursor = conn.cursor()
    
    if not chat_id:
        # New chat
        chat_id = str(uuid4())
        session['current_chat_id'] = chat_id
        conversation_history = []
    else:
        # Fetch existing conversation history for this chat_id
        cursor.execute("""
            SELECT messages 
            FROM chats 
            WHERE user_id = ? AND chat_id = ?
        """, (session['user_id'], chat_id))
        result = cursor.fetchone()
        conversation_history = json.loads(result[0]) if result else []

    # Get the response from the model
    reply = chat_with_model(user_input, conversation_history)
    
    # Save the updated conversation history
    title = user_input[:30] + "..." if len(user_input) > 30 else user_input

    # Check if chat already exists
    cursor.execute("""
        SELECT COUNT(*) 
        FROM chats 
        WHERE user_id = ? AND chat_id = ?
    """, (session['user_id'], chat_id))
    exists = cursor.fetchone()[0] > 0

    if exists:
        # Update existing chat
        cursor.execute("""
            UPDATE chats 
            SET messages = ?, created_at = datetime('now') 
            WHERE user_id = ? AND chat_id = ?
        """, (json.dumps(conversation_history), session['user_id'], chat_id))
    else:
        # Insert new chat
        cursor.execute("""
            INSERT INTO chats (user_id, chat_id, title, messages, created_at) 
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (session['user_id'], chat_id, title, json.dumps(conversation_history)))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "reply": reply,
        "chatId": chat_id
    })


@app.route('/get_chat_history', methods=['GET'])
def get_chat_history():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401

    conn = sqlite3.connect('chatbot.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT chat_id, title, messages, created_at
        FROM chats 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    """, (session['user_id'],))
    chats = cursor.fetchall()
    conn.close()

    chat_history = []
    for chat in chats:
        chat_history.append({
            "chat_id": chat[0],
            "title": chat[1],
            "messages": json.loads(chat[2]),
            "created_at": chat[3]
        })

    return jsonify({"success": True, "chat_history": chat_history})

# ... (rest of the routes remain the same)

@app.route('/new_chat', methods=['POST'])
def new_chat():
    session['conversation_history'] = []
    session.pop('current_chat_id', None)
    return jsonify({"success": True, "message": "New chat started"})
        
if __name__ == '__main__':
    app.run(debug=True)
