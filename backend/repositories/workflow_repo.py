"""Workflow Draft 的持久化访问层。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from core.database import db_connection

_COLUMNS = "id, user_id, project_id, revision, draft_json, created_at, updated_at"


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["draft"] = json.loads(item.pop("draft_json"))
    return item


def get(user_id: int, project_id: int | None) -> dict[str, Any] | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT " + _COLUMNS + " FROM workflow_drafts "
            "WHERE user_id=? AND COALESCE(project_id, -1)=COALESCE(?, -1)",
            (user_id, project_id),
        ).fetchone()
    return _decode(row) if row else None


def upsert(
    user_id: int,
    project_id: int | None,
    revision: int,
    draft: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    payload = json.dumps(draft, ensure_ascii=False)
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            "SELECT id FROM workflow_drafts "
            "WHERE user_id=? AND COALESCE(project_id, -1)=COALESCE(?, -1)",
            (user_id, project_id),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE workflow_drafts SET revision=?, draft_json=?, updated_at=? WHERE id=?",
                (revision, payload, timestamp, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO workflow_drafts "
                "(user_id, project_id, revision, draft_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, project_id, revision, payload, timestamp, timestamp),
            )
        row = conn.execute(
            "SELECT " + _COLUMNS + " FROM workflow_drafts "
            "WHERE user_id=? AND COALESCE(project_id, -1)=COALESCE(?, -1)",
            (user_id, project_id),
        ).fetchone()
    assert row is not None
    return _decode(row)
