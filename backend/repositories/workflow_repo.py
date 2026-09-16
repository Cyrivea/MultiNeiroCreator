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


def upsert_if_revision(
    user_id: int,
    project_id: int | None,
    expected_revision: int,
    draft: dict[str, Any],
    timestamp: str,
) -> dict[str, Any] | None:
    """乐观锁版 upsert：仅当服务器 revision 与调用方所见的相同时才写入。

    返回 None 表示冲突（期间已有另一个写入者）；调用方应重读后重试，
    不允许悄悄整档覆盖（运行期间 Runner 与 configure 并发写入的丢更新源头）。
    """
    payload = json.dumps(draft, ensure_ascii=False)
    new_revision = expected_revision + 1
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            "SELECT id, revision FROM workflow_drafts "
            "WHERE user_id=? AND COALESCE(project_id, -1)=COALESCE(?, -1)",
            (user_id, project_id),
        ).fetchone()
        if existing is None:
            if expected_revision != 0:
                return None
            conn.execute(
                "INSERT INTO workflow_drafts "
                "(user_id, project_id, revision, draft_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, project_id, new_revision, payload, timestamp, timestamp),
            )
        else:
            updated = conn.execute(
                "UPDATE workflow_drafts SET revision=?, draft_json=?, updated_at=? "
                "WHERE id=? AND revision=?",
                (new_revision, payload, timestamp, existing["id"], expected_revision),
            )
            if updated.rowcount != 1:
                return None
        row = conn.execute(
            "SELECT " + _COLUMNS + " FROM workflow_drafts "
            "WHERE user_id=? AND COALESCE(project_id, -1)=COALESCE(?, -1)",
            (user_id, project_id),
        ).fetchone()
    assert row is not None
    return _decode(row)
