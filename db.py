import sqlite3

conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    token TEXT PRIMARY KEY,
    file_id TEXT,
    password TEXT,
    expiry INTEGER
)
""")
conn.commit()


def save_file(token, file_id, password, expiry):
    cursor.execute(
        "INSERT INTO files VALUES (?, ?, ?, ?)",
        (token, file_id, password, expiry)
    )
    conn.commit()


def get_file(token):
    cursor.execute("SELECT * FROM files WHERE token=?", (token,))
    return cursor.fetchone()
