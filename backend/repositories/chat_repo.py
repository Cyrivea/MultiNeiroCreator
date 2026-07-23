import sqlite3

from core.database import get_connection


def append_message(user_id: int, role: str, content: str, project_id: int | None = None) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO messages (user_id, project_id, role, content) VALUES (?, ?, ?, ?)",
        (user_id, project_id, role, content),
    )
    conn.commit()
    conn.close()


def list_history(user_id: int, project_id: int | None = None) -> list[dict]:
    conn = get_connection()
    if project_id is None:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE user_id=? AND project_id IS NULL ORDER BY id",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE user_id=? AND project_id=? ORDER BY id",
            (user_id, project_id),
        ).fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]


def clear_history(user_id: int, project_id: int | None = None) -> None:
    conn = get_connection()
    if project_id is None:
        conn.execute("DELETE FROM messages WHERE user_id=? AND project_id IS NULL", (user_id,))
    else:
        conn.execute("DELETE FROM messages WHERE user_id=? AND project_id=?", (user_id, project_id))
    conn.commit()
    conn.close()
