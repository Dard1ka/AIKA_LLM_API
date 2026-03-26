import sqlite3
from pathlib import Path

DB_PATH = Path("data/chat.db")

def main():
    if not DB_PATH.exists():
        print("chat.db tidak ditemukan:", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # cek total sebelum
    cur.execute("SELECT COUNT(*) FROM messages")
    before = cur.fetchone()[0]

    # update semua conversation_id jadi GLOBAL
    cur.execute("UPDATE messages SET conversation_id = 'GLOBAL'")
    conn.commit()

    # cek total sesudah
    cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = 'GLOBAL'")
    after = cur.fetchone()[0]

    conn.close()

    print("DONE")
    print("Total rows:", before)
    print("Rows in GLOBAL:", after)

if __name__ == "__main__":
    main()
