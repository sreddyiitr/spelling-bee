import sqlite3
from flask import Flask, render_template, request, jsonify
import random
import os

app = Flask(__name__)
DB_FILE = "spelling_bee.db"

# Global set to track words seen in the CURRENT practice session
session_seen = set()

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS dictionary 
            (word TEXT PRIMARY KEY, 
             is_incorrect INTEGER DEFAULT 0, 
             is_bookmarked INTEGER DEFAULT 0)''')
        conn.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_words', methods=['POST'])
def add_words():
    words = request.json.get('words', [])
    new_count = 0
    with sqlite3.connect(DB_FILE) as conn:
        for word in words:
            clean_word = word.strip().lower()
            if clean_word:
                cursor = conn.execute("INSERT OR IGNORE INTO dictionary (word) VALUES (?)", (clean_word,))
                if cursor.rowcount > 0:
                    new_count += 1
        conn.commit()
    return jsonify({"status": "success", "message": f"Added {new_count} new words!"})

@app.route('/reset_session', methods=['POST'])
def reset_session():
    global session_seen
    session_seen.clear()
    return jsonify({"status": "session reset"})

@app.route('/get_next', methods=['GET'])
def get_next():
    global session_seen
    mode = request.args.get('mode', 'all')   
    letter = request.args.get('letter', 'all').lower()
    
    query = "SELECT word FROM dictionary WHERE 1=1"
    params = []

    if letter != 'all':
        query += " AND word LIKE ?"
        params.append(f"{letter}%")
    
    if mode == 'incorrect':
        query += " AND is_incorrect = 1"
    elif mode == 'bookmarked':
        query += " AND is_bookmarked = 1"

    with sqlite3.connect(DB_FILE) as conn:
        all_potential_words = [row[0] for row in conn.execute(query, params).fetchall()]
    
    available_words = [w for w in all_potential_words if w not in session_seen]
    
    if not available_words:
        return jsonify({"word": None, "total": len(all_potential_words)})
    
    chosen_word = random.choice(available_words)
    session_seen.add(chosen_word)
    current_index = len(all_potential_words) - len(available_words) + 1
    
    return jsonify({
        "word": chosen_word, 
        "current_index": current_index,
        "total": len(all_potential_words)
    })

@app.route('/update_status', methods=['POST'])
def update_status():
    """Updates word flags and immediately returns fresh stats for the UI."""
    word = request.json.get('word')
    action = request.json.get('action') 
    
    with sqlite3.connect(DB_FILE) as conn:
        if action == 'wrong':
            conn.execute("UPDATE dictionary SET is_incorrect = 1 WHERE word = ?", (word,))
        elif action == 'bookmark':
            conn.execute("UPDATE dictionary SET is_bookmarked = 1 WHERE word = ?", (word,))
        elif action == 'clear_wrong':
            conn.execute("UPDATE dictionary SET is_incorrect = 0 WHERE word = ?", (word,))
        elif action == 'clear_bookmark':
            conn.execute("UPDATE dictionary SET is_bookmarked = 0 WHERE word = ?", (word,))
        conn.commit()
    
    # Return the full stats object so the frontend can refresh the history list
    return get_stats()

@app.route('/stats', methods=['GET'])
def get_stats():
    """Returns unique counts and grouped lists for the history section."""
    with sqlite3.connect(DB_FILE) as conn:
        # Get the unique count of words marked as wrong
        wrong_count = conn.execute("SELECT count(*) FROM dictionary WHERE is_incorrect = 1").fetchone()[0]
        
        # Get the actual word lists
        incorrect = conn.execute("SELECT word FROM dictionary WHERE is_incorrect = 1 ORDER BY word ASC").fetchall()
        bookmarks = conn.execute("SELECT word FROM dictionary WHERE is_bookmarked = 1 ORDER BY word ASC").fetchall()
    
    return jsonify({
        "incorrect": [w[0] for w in incorrect],
        "bookmarks": [w[0] for w in bookmarks],
        "unique_wrong_count": wrong_count  # This feeds your 'Badge'
    })

@app.route('/speak', methods=['POST'])
def speak():
    word = request.json.get('word')
    if word:
        os.system(f'say -v Nicky "{word}" -r 140')
    return jsonify({"status": "played"})

@app.route('/add', methods=['GET'])
def add_by_url():
    """Adds a specific word to the database via URL query parameter."""
    word_to_add = request.args.get('word')
    
    if not word_to_add:
        return "<h1>Error</h1><p>No word provided. Usage: /add?word=yourword</p>", 400

    clean_word = word_to_add.strip().lower()
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            # INSERT OR IGNORE prevents errors if the word already exists
            cursor = conn.execute("INSERT OR IGNORE INTO dictionary (word) VALUES (?)", (clean_word,))
            conn.commit()
            
            if cursor.rowcount > 0:
                return f"<h1>Success</h1><p>'{clean_word}' has been added to the hive! <a href='/'>Go Home</a></p>"
            else:
                return f"<h1>Duplicate</h1><p>'{clean_word}' is already in the database. <a href='/'>Go Home</a></p>"
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>", 500
    
@app.route('/delete', methods=['GET'])
def delete_by_url():
    """Deletes a specific word from the database via URL query parameter."""
    word_to_delete = request.args.get('word')
    
    if not word_to_delete:
        return "<h1>Error</h1><p>No word provided. Usage: /delete?word=yourword</p>", 400

    clean_word = word_to_delete.strip().lower()
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute("DELETE FROM dictionary WHERE word = ?", (clean_word,))
            conn.commit()
            
            if cursor.rowcount > 0:
                return f"<h1>Success</h1><p>'{clean_word}' has been permanently removed from the hive. <a href='/'>Go Home</a></p>"
            else:
                return f"<h1>Not Found</h1><p>'{clean_word}' was not in the database. <a href='/'>Go Home</a></p>"
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>", 500
    
@app.route('/clear_all', methods=['GET'])
def clear_all():
    global session_seen
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM dictionary")
            conn.commit()
        session_seen.clear()
        return "<h1>Hive Cleared Successfully!</h1><p><a href='/'>Go back to Home</a></p>"
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>", 500
    
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)
