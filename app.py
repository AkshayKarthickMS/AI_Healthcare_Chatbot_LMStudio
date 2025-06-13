from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from uuid import uuid4
import sqlite3
import os
import json
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_community.chat_models import ChatOpenAI
from transformers import AutoTokenizer
from tqdm import tqdm
from functools import lru_cache


PUBMED_API_KEY = "your_pubmed_api_key_here"
VECTORDB_DIR = "vector_index"
MAX_PUBMED_ARTICLES = 10
RECENT_DAYS = 7
DB_PATH = 'chatbot.db'  # Path to SQLite database

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


def detect_language(text):
    try:
        from langdetect import detect
        return detect(text)
    except:
        return "en"


def chat_with_model(user_input, conversation_history):
    if len(conversation_history) == 0:
        summary = session.get('health_summary', 'No prior health records found.')
        conversation_history.insert(0, {
            "role": "system",
            "content": f"""You are Dr. AI&DS, a compassionate and concise doctor. Below is the summary of this patient's prior health records: {summary}. Respond to patient queries based on current health issues and also on that summary with empathy and warmth using 1–2 complete sentences. Ask only 1–2 questions at a time to keep the conversation focused. Do not provide prescriptions or suggest in-person visits. If asked non-medical questions, say: 'I'm a doctor, I can't answer that question.'

Your reply must be in the **exact same language** as the user input. For example:
- User: 'मैं ठीक नहीं हूँ' → Reply in Hindi
- User: 'I feel cold and tired' → Reply in English

Do not guess or switch languages. Respond in the same language unless the user changes it explicitly. Also, do not exceed 50 words."""
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

    if user and check_password_hash(user[2], password):
        session['user_id'] = user[0]
        session['username'] = username

        # ✅ Fetch all chats for that user
        cursor.execute("SELECT messages FROM chats WHERE user_id = ?", (user[0],))
        chats = cursor.fetchall()
        conn.close()

        full_history = []
        for chat in chats:
            messages = json.loads(chat[0])
            for msg in messages:
                if msg['role'] in ['user', 'assistant']:
                    full_history.append(msg)

        if full_history:
            # Add instruction to summarize health
            full_history.insert(0, {
                "role": "system",
                "content": "You are a concise and empathetic doctor. Please summarize ONLY the user's past health issues based on all previous conversations. Do not ask questions or give new advice."
            })
            full_history.append({
                "role": "user",
                "content": "Summarize my previous health problems."
            })

            try:
                summary = chat_with_model("Summarize my previous health problems.", full_history)
                session['health_summary'] = summary
            except Exception as e:
                print("Error summarizing health history:", e)

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
        
def rate_limited_get(url, params=None, max_requests_per_sec=10):
    if not hasattr(rate_limited_get, "last_request_time"):
        rate_limited_get.last_request_time = 0
    elapsed = time.time() - rate_limited_get.last_request_time
    if elapsed < 1.0 / max_requests_per_sec:
        time.sleep((1.0 / max_requests_per_sec) - elapsed)
    rate_limited_get.last_request_time = time.time()
    return requests.get(url, params=params)

def fetch_recent_pubmed_pmids(days=7, max_count=10):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": "medicine OR health",
        "reldate": days,
        "retmax": max_count,
        "sort": "pub+date",
        "retmode": "json",
        "api_key": PUBMED_API_KEY,
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data["esearchresult"]["idlist"]

def fetch_pubmed_abstract(pmid):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml",
        "api_key": PUBMED_API_KEY,
    }
    try:
        response = rate_limited_get(url, params=params)
        soup = BeautifulSoup(response.content, "lxml")
        abstract = soup.find("abstract")
        return abstract.get_text(separator="\n").strip() if abstract else ""
    except Exception as e:
        print(f"Error fetching PMID {pmid}: {e}")
        return ""


# --- Update VectorDB ---
def update_vector_database():
    print("Fetching recent PubMed articles...")
    pmids = fetch_recent_pubmed_pmids(days=RECENT_DAYS, max_count=MAX_PUBMED_ARTICLES)

    pubmed_docs = []
    for pmid in tqdm(pmids, desc="PubMed abstracts"):
        abstract = fetch_pubmed_abstract(pmid)
        if abstract:
            pubmed_docs.append(Document(page_content=abstract, metadata={"source": f"PubMed:{pmid}"}))

    all_docs = pubmed_docs

    print("\nSplitting documents...")
    tokenizer = AutoTokenizer.from_pretrained("thenlper/gte-small")
    splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        tokenizer, chunk_size=200, chunk_overlap=20
    )
    split_docs = splitter.split_documents(all_docs)

    print("\nEmbedding and saving to vector database...")
    embedding_model = HuggingFaceEmbeddings(model_name="thenlper/gte-small")

    # Check if the vector DB exists and append documents
    if os.path.exists(VECTORDB_DIR):
        vectordb = FAISS.load_local(VECTORDB_DIR, embeddings=embedding_model, allow_dangerous_deserialization=True)
        vectordb.add_documents(split_docs)  # Add new documents to the vector DB
    else:
        vectordb = FAISS.from_documents(split_docs, embedding=embedding_model, distance_strategy=DistanceStrategy.COSINE)

    vectordb.save_local(VECTORDB_DIR)
    print("Vector DB saved!")

# --- RAG Context Fetch ---
@lru_cache(maxsize=1)
def get_vectordb():
    return FAISS.load_local(VECTORDB_DIR, embeddings=HuggingFaceEmbeddings(model_name="thenlper/gte-small"), allow_dangerous_deserialization=True)

def get_research_context(query):
    vectordb = get_vectordb()
    docs = vectordb.similarity_search(query, k=3)
    return "\n\n".join(f"Source: {doc.metadata['source']}\n{doc.page_content[:500]}..." for doc in docs)

if __name__ == '__main__':
    import sys
    if os.environ.get("FLASK_RUN_FROM_CLI") != "true" and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        update_vector_database()
    app.run(debug=True)

