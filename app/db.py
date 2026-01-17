# app/db.py
import sqlite3
from pathlib import Path
import bcrypt

DB_PATH = Path(__file__).resolve().parent / "routers.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    with open(Path(__file__).parent / "models.sql", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()


def get_routers():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT name, host, username, password, port
        FROM routers
        WHERE enabled = 1
        ORDER BY name
        """
    )

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]

# --- users ---
def add_user(username: str, password: str, role: str = "viewer"):
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role)
        )
        conn.commit()
        return True  # **success**
    except sqlite3.IntegrityError:
        return False  # **user exist**
    except Exception as e:
        return e  # **another error**
    finally:
        conn.close()

# def add_user(username: str, password: str, role: str = "viewer"):
#     password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
#     conn = get_connection()
#     cur = conn.cursor()
#     cur.execute(
#         "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
#         (username, password_hash, role)
#     )
#     conn.commit()
#     conn.close()

def get_user(username: str):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())

# --- users ---
def list_users():
    """Returns all users with username and role"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT username, role FROM users ORDER BY username")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_user_role(username: str, role: str):
    """Update the user role"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET role=? WHERE username=?", (role, username))
    conn.commit()
    conn.close()

def update_user_password(username: str, password: str):
    """Update the user's password"""
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash=? WHERE username=?", (password_hash, username))
    conn.commit()
    conn.close()

def delete_user(username: str):
    """Delete a user"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()

def users_count():
    """Number of users"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    conn.close()
    return count
