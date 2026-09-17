import json

from core.database import db_connection


def append_message(
    user_id: int,
    role: str,
    content: str,
    project_id: int | None = None,
    attachments: list[dict] | None = None,
    citations: list[dict] | None = None,
    interrupted: bool = False,
) -> None:
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO messages "
            "(user_id, project_id, role, content, attachments_json, citations_json, interrupted) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                project_id,
                role,
                content,
                json.dumps(attachments, ensure_ascii=False) if attachments else None,
                json.dumps(citations, ensure_ascii=False) if citations else None,
                1 if interrupted else 0,
            ),
        )


def list_history(user_id: int, project_id: int | None = None) -> list[dict]:
    with db_connection() as conn:
        if project_id is None:
            rows = conn.execute(
                "SELECT role, content, attachments_json, citations_json, interrupted FROM messages"
                " WHERE user_id=? AND project_id IS NULL ORDER BY id",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT role, content, attachments_json, citations_json, interrupted FROM messages"
                " WHERE user_id=? AND project_id=? ORDER BY id",
                (user_id, project_id),
            ).fetchall()
    history: list[dict] = []
    for role, content, attachments_json, citations_json, interrupted in rows:
        item = {"role": role, "content": content}
        if interrupted:
            item["interrupted"] = True
        if attachments_json:
            try:
                item["attachments"] = json.loads(attachments_json)
            except json.JSONDecodeError:
                item["attachments"] = []
        if citations_json:
            try:
                item["citations"] = json.loads(citations_json)
            except json.JSONDecodeError:
                item["citations"] = []
        history.append(item)
    return history


def clear_history(user_id: int, project_id: int | None = None) -> None:
    with db_connection() as conn:
        if project_id is None:
            conn.execute("DELETE FROM messages WHERE user_id=? AND project_id IS NULL", (user_id,))
        else:
            conn.execute("DELETE FROM messages WHERE user_id=? AND project_id=?", (user_id, project_id))
