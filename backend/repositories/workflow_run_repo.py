"""Workflow run / step 账本的持久化访问层。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from core.database import db_connection

_RUN_COLUMNS = (
    "id, user_id, project_id, workflow_id, draft_revision, draft_snapshot_json, "
    "status, error, job_id, created_at, started_at, finished_at"
)
_STEP_COLUMNS = (
    "id, run_id, node_id, capability_id, status, input_json, output_json, error, created_at"
)


def _run(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["draft_snapshot"] = json.loads(item.pop("draft_snapshot_json"))
    return item


def _step(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["input"] = json.loads(item["input_json"]) if item.pop("input_json") else None
    item["output"] = json.loads(item["output_json"]) if item.pop("output_json") else None
    return item


def create(
    run_id: str,
    user_id: int,
    project_id: int | None,
    draft_revision: int,
    draft_snapshot: dict[str, Any],
    workflow_id: int | None,
    job_id: str | None,
    created_at: str,
) -> dict[str, Any]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            f"INSERT INTO workflow_runs ({_RUN_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, 'queued', NULL, ?, ?, NULL, NULL)",
            (
                run_id,
                user_id,
                project_id,
                workflow_id,
                draft_revision,
                json.dumps(draft_snapshot, ensure_ascii=False),
                job_id,
                created_at,
            ),
        )
        row = conn.execute(
            f"SELECT {_RUN_COLUMNS} FROM workflow_runs WHERE id=?", (run_id,)
        ).fetchone()
    assert row is not None
    return _run(row)


def get(user_id: int, run_id: str) -> dict[str, Any] | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"SELECT {_RUN_COLUMNS} FROM workflow_runs WHERE id=? AND user_id=?",
            (run_id, user_id),
        ).fetchone()
    return _run(row) if row else None


def find_active_for_workflow(user_id: int, workflow_id: int | None) -> dict[str, Any] | None:
    """检查某一份 Draft 当前是否有 queued/running 的运行；编辑锁用它拒绝写入。"""
    if workflow_id is None:
        return None
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"SELECT {_RUN_COLUMNS} FROM workflow_runs "
            "WHERE workflow_id=? AND user_id=? AND status IN ('queued','running') "
            "ORDER BY created_at DESC LIMIT 1",
            (workflow_id, user_id),
        ).fetchone()
    return _run(row) if row else None


def list_recent(user_id: int, project_id: int | None, limit: int = 5) -> list[dict[str, Any]]:
    """某项目最近的运行记录（新→旧）；默认工作区 project_id 用 COALESCE 匹配。"""
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT {_RUN_COLUMNS} FROM workflow_runs "
            "WHERE user_id=? AND COALESCE(project_id, -1)=COALESCE(?, -1) "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, project_id, max(1, min(limit, 20))),
        ).fetchall()
    return [_run(row) for row in rows]


def update_status(
    run_id: str,
    status: str,
    *,
    error: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE workflow_runs SET status=?, error=COALESCE(?, error), "
                "started_at=COALESCE(?, started_at), finished_at=COALESCE(?, finished_at) "
                "WHERE id=?",
                (status, error, started_at, finished_at, run_id),
            ).rowcount
            == 1
        )


def create_step(
    step_id: str,
    run_id: str,
    node_id: str,
    capability_id: str,
    input_payload: dict[str, Any] | None,
    created_at: str,
) -> dict[str, Any]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            f"INSERT INTO workflow_steps ({_STEP_COLUMNS}) VALUES (?, ?, ?, ?, 'queued', ?, NULL, NULL, ?)",
            (
                step_id,
                run_id,
                node_id,
                capability_id,
                json.dumps(input_payload, ensure_ascii=False) if input_payload else None,
                created_at,
            ),
        )
        row = conn.execute(
            f"SELECT {_STEP_COLUMNS} FROM workflow_steps WHERE id=?", (step_id,)
        ).fetchone()
    assert row is not None
    return _step(row)


def finish_step(
    step_id: str,
    status: str,
    output_payload: dict[str, Any] | None,
    error: str | None,
) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE workflow_steps SET status=?, output_json=?, error=? WHERE id=?",
                (
                    status,
                    json.dumps(output_payload, ensure_ascii=False) if output_payload else None,
                    error,
                    step_id,
                ),
            ).rowcount
            == 1
        )


def list_steps(user_id: int, run_id: str) -> list[dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT s." + "s.".join(_STEP_COLUMNS.split(", ")) + " FROM workflow_steps s "
            "JOIN workflow_runs r ON r.id = s.run_id "
            "WHERE s.run_id=? AND r.user_id=? ORDER BY s.created_at ASC",
            (run_id, user_id),
        ).fetchall()
    return [_step(row) for row in rows]
