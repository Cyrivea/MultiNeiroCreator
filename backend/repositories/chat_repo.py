import sqlite3

from core.database import get_connection


def append_message(user_id: int, role: str, content: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content),
    )
    conn.commit()
    conn.close()


def list_history(user_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE user_id=? ORDER BY id",
        (user_id,),
    ).fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]


def clear_history(user_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM messages WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
