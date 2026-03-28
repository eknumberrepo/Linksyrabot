import sqlite3

conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    token TEXT PRIMARY KEY,
    msg_id INTEGER,
    password TEXT,
    expiry INTEGER,
    views INTEGER DEFAULT 0,
    one_time INTEGER DEFAULT 0
)
""")
conn.commit()


def save_file(token, msg_id, password, expiry, one_time=0):
    cursor.execute(
        "INSERT INTO files VALUES (?, ?, ?, ?, 0, ?)",
        (token, msg_id, password, expiry, one_time)
    )
    conn.commit()


def get_file(token):
    cursor.execute("SELECT * FROM files WHERE token=?", (token,))
    return cursor.fetchone()


def delete_file(token):
    cursor.execute("DELETE FROM files WHERE token=?", (token,))
    conn.commit()


def increment_views(token):
    cursor.execute("UPDATE files SET views = views + 1 WHERE token=?", (token,))
    conn.commit()


def get_expired(now):
    cursor.execute("SELECT token, msg_id FROM files WHERE expiry < ?", (now,))
    return cursor.fetchall()
