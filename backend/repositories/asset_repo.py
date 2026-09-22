"""资产表 repo：每次 capability 产出（/api/assets/...）都对应账本一行。


资产文件命名本身是最外层的不可信任标识（uuid hex），库里这一行才是
{谁, 哪个项目, 哪次运行， 调用哪个能力， 花多少钱} 的可查询事实。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from core.database import db_connection

_COLUMNS = (
    "id, user_id, project_id, run_id, capability_id, kind, filename, content_type, "
    "byte_size, prompt_snapshot_json, usage_event_id, created_at"
)


def _row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    if item.get("prompt_snapshot_json"):
        import json

        item["prompt_snapshot"] = json.loads(item.pop("prompt_snapshot_json"))
    else:
        item["prompt_snapshot"] = None
    return item


def insert(
    *,
    user_id: int,
    project_id: int | None,
    run_id: str | None,
    capability_id: str,
    kind: str,
    filename: str,
    content_type: str,
    byte_size: int,
    prompt_snapshot: dict[str, Any] | None,
    usage_event_id: int | None,
    created_at: str,
) -> dict[str, Any]:
    asset_id = f"asset-{uuid.uuid4().hex[:12]}"
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            f"INSERT INTO assets ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                asset_id,
                user_id,
                project_id,
                run_id,
                capability_id,
                kind,
                filename,
                content_type,
                byte_size,
                json.dumps(prompt_snapshot, ensure_ascii=False) if prompt_snapshot else None,
                usage_event_id,
                created_at,
            ),
        )
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM assets WHERE id=?", (asset_id,)
        ).fetchone()
    assert row is not None
    return _row(row)


def list_for_user(
    user_id: int, project_id: int | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        if project_id is None:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM assets WHERE user_id=? AND project_id IS NULL "
                f"ORDER BY created_at DESC LIMIT ?",
                (user_id, min(limit, 500)),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM assets WHERE user_id=? AND project_id=? ORDER BY created_at DESC LIMIT ?",
                (user_id, project_id, min(limit, 500)),
            ).fetchall()
    return [_row(r) for r in rows]
