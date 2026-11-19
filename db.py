import sqlite3
import threading

from config import DB_PATH, FREE_DOCS

_lock = threading.Lock()


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, free_used INTEGER DEFAULT 0, credits INTEGER DEFAULT 0)")
    return c


def get(uid: str):
    with _lock, _conn() as c:
        c.execute("INSERT OR IGNORE INTO users(id) VALUES (?)", (uid,))
        return c.execute("SELECT free_used, credits FROM users WHERE id=?", (uid,)).fetchone()


def left(uid: str) -> int:
    used, credits = get(uid)
    return max(FREE_DOCS - used, 0) + credits


def consume(uid: str) -> bool:
    """Bitta hujjat limitini yechadi. Limit yo‘q bo‘lsa False."""
    with _lock, _conn() as c:
        c.execute("INSERT OR IGNORE INTO users(id) VALUES (?)", (uid,))
        used, credits = c.execute("SELECT free_used, credits FROM users WHERE id=?", (uid,)).fetchone()
        if used < FREE_DOCS:
            c.execute("UPDATE users SET free_used=free_used+1 WHERE id=?", (uid,))
            return True
        if credits > 0:
            c.execute("UPDATE users SET credits=credits-1 WHERE id=?", (uid,))
            return True
        return False


def refund(uid: str):
    with _lock, _conn() as c:
        c.execute("UPDATE users SET credits=credits+1 WHERE id=?", (uid,))


def add_credits(uid: str, n: int):
    with _lock, _conn() as c:
        c.execute("INSERT OR IGNORE INTO users(id) VALUES (?)", (uid,))
        c.execute("UPDATE users SET credits=credits+? WHERE id=?", (n, uid))
