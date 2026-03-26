import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/chat.db")

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_time ON messages(conversation_id, created_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_role ON messages(role);")
    conn.commit()
    conn.close()

def add_message(conversation_id: str, role: str, content: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

def get_recent_messages(conversation_id: str, limit: int = 20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT role, content, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (conversation_id, limit))
    rows = cur.fetchall()
    conn.close()
    # balikkan urutan dari lama -> baru
    return list(reversed(rows))

def keyword_search(conversation_id: str, query: str, limit: int = 20):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT role, content, created_at
        FROM messages
        WHERE conversation_id = ?
          AND content LIKE ?
        ORDER BY id DESC
        LIMIT ?
    """, (conversation_id, f"%{query}%", limit))
    rows = cur.fetchall()
    conn.close()
    return rows
