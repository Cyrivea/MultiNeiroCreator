import sqlite3
from typing import Optional

from core.database import get_connection


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, username, password_hash, profile, created_at FROM users WHERE username=?",
        (username,),
    ).fetchone()
    conn.close()
    return row


def create_user(username: str, password_hash: str) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def get_profile(user_id: int) -> str:
    conn = get_connection()
    row = conn.execute("SELECT profile FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return row[0] if row else ""


def update_profile(user_id: int, profile: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE users SET profile=? WHERE id=?", (profile, user_id))
    conn.commit()
    conn.close()
