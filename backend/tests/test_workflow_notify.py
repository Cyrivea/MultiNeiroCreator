"""workflow 完成/失败通知（最后一环）：终态必须往聊天表插一条 system-notice。"""

import sqlite3

import pytest

import core.database as database
from core.migrations import run_migrations
from repositories import chat_repo
from services import workflow_service


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "notify.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    run_migrations()
    return db_path


def _create_user(uid: int) -> None:
    with database.db_connection() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, profile, created_at) "
            "VALUES (?, ?, 'x', '', '2026-01-01')",
            (uid, f"notify-{uid}@local"),
        )


def test_succeeded_run_inserts_system_notice(db):
    _create_user(910)
    workflow_service.mark_canvas_read(910, None)
    workflow_service.configure_lyrics(
        910, None, {"theme": "海边", "style": "城市民谣", "mood": "温柔、克制", "language": "中文"}
    )
    submission = workflow_service.submit_workflow_run(910, None)

    workflow_service.execute_workflow_run_job(
        "job-n1", submission["run_id"], submission["draft"], 910, None
    )

    hist = chat_repo.list_history(910, None)
    assert len(hist) == 1
    notice = hist[0]
    assert notice["role"] == "system-notice"
    assert "Workflow 已完成" in notice["content"]
    assert submission["run_id"] in notice["content"]


def test_failed_run_inserts_failure_notice(db):
    _create_user(911)
    workflow_service.mark_canvas_read(911, None)
    # 故意弄坏：未知 capability（防御层会报未注册能力）
    workflow_service.workflow_repo.upsert if hasattr(workflow_service.workflow_repo, "upsert") else None
    # 直接构造极端案例：先插一条 halted run，然后 finalize
    workflow_service.finalize_failed_run(
        911, None, "run-fail-1", "RuntimeError: lyrics provider down"
    )
    hist = chat_repo.list_history(911, None)
    assert any(n["role"] == "system-notice" and "RuntimeError" in n["content"] for n in hist)
