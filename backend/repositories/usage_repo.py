"""usage_events 精确用量账本的持久化写入。"""

from __future__ import annotations

import sqlite3
from typing import Any

from core.database import db_connection

_COLUMNS = (
    "id, user_id, project_id, capability_id, source, model, prompt_tokens, "
    "completion_tokens, total_tokens, status, error, duration_ms, created_at"
)


def insert(
    user_id: int,
    project_id: int | None,
    capability_id: str,
    source: str,
    model: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    status: str,
    error: str | None,
    duration_ms: float | None,
    created_at: str,
) -> dict[str, Any]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            f"INSERT INTO usage_events ({_COLUMNS.removeprefix('id, ')}) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                project_id,
                capability_id,
                source,
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                status,
                error,
                duration_ms,
                created_at,
            ),
        )
        event_id = cursor.lastrowid
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM usage_events WHERE id=?", (event_id,)
        ).fetchone()
    assert row is not None
    return dict(row)


def list_for_user(user_id: int, limit: int = 100) -> list[dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM usage_events WHERE user_id=? "
            "ORDER BY datetime(created_at) DESC LIMIT ?",
            (user_id, max(1, min(limit, 500))),
        ).fetchall()
    return [dict(row) for row in rows]


def count_for_user(user_id: int) -> int:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM usage_events WHERE user_id=?", (user_id,)
        ).fetchone()
    return int(row[0])
