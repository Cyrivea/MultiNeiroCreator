from datetime import UTC, datetime, timedelta

import pytest

from core import database, migrations
from repositories import job_repo
from workers import job_worker


def now() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture
def job_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "jobs.db")
    migrations.run_migrations()
    with database.db_connection() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("job-owner@example.com", "hash"),
        )
        user_id = conn.execute("SELECT id FROM users").fetchone()[0]
    return user_id


def create_test_job(user_id: int, **kwargs):
    return job_repo.create(
        job_id=kwargs.get("job_id", "job-1"),
        job_type=kwargs.get("job_type", "test"),
        user_id=user_id,
        project_id=None,
        payload=kwargs.get("payload", {"value": 1}),
        max_attempts=kwargs.get("max_attempts", 3),
        created_at=now(),
    )


def test_migration_creates_jobs_and_is_idempotent(job_db):
    migrations.run_migrations()
    with database.db_connection() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 11
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    assert {"status", "payload_json", "lease_expires_at", "cancel_requested"} <= columns
    with database.db_connection() as conn:
        message_columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    assert {"citations_json", "interrupted"} <= message_columns
    with database.db_connection() as conn:
        document_columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
    assert {"storage_path", "status", "job_id", "indexed_at"} <= document_columns


def test_migration_creates_workflow_drafts(job_db):
    with database.db_connection() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(workflow_drafts)")}
    assert {"user_id", "project_id", "revision", "draft_json"} <= columns


def test_claim_is_atomic_and_success_persists_result(job_db):
    create_test_job(job_db)

    claimed = job_repo.claim_next("worker-a", 60, now())
    assert claimed is not None
    assert claimed["status"] == "running"
    assert claimed["attempts"] == 1
    assert job_repo.claim_next("worker-b", 60, now()) is None

    assert job_repo.mark_succeeded("job-1", "worker-a", {"ok": True}, now())
    stored = job_repo.get_for_user(job_db, "job-1")
    assert stored is not None
    assert stored["status"] == "succeeded"
    assert stored["progress"] == 100
    assert stored["result"] == {"ok": True}


def test_queued_job_can_be_cancelled_before_worker_claims(job_db):
    create_test_job(job_db)
    cancelled = job_repo.request_cancel(job_db, "job-1", now())

    assert cancelled is not None
    assert cancelled["status"] == "cancelled"
    assert job_repo.claim_next("worker-a", 60, now()) is None


def test_expired_running_job_is_recovered(job_db):
    create_test_job(job_db)
    claimed = job_repo.claim_next("dead-worker", 60, now())
    assert claimed is not None

    with database.db_connection() as conn:
        conn.execute(
            "UPDATE jobs SET lease_expires_at=? WHERE id=?",
            ((datetime.now(UTC) - timedelta(minutes=5)).isoformat(), "job-1"),
        )

    assert job_repo.recover_expired(now(), now()) == 1
    recovered = job_repo.get_for_user(job_db, "job-1")
    assert recovered is not None
    assert recovered["status"] == "queued"
    assert recovered["claimed_by"] is None


def test_expired_running_job_at_attempt_limit_is_failed(job_db):
    create_test_job(job_db, max_attempts=1)
    claimed = job_repo.claim_next("dead-worker", 60, now())
    assert claimed is not None

    with database.db_connection() as conn:
        conn.execute(
            "UPDATE jobs SET lease_expires_at=? WHERE id=?",
            ((datetime.now(UTC) - timedelta(minutes=5)).isoformat(), "job-1"),
        )

    assert job_repo.recover_expired(now(), now()) == 0
    recovered = job_repo.get_for_user(job_db, "job-1")
    assert recovered is not None
    assert recovered["status"] == "failed"
    assert "最大重试" in recovered["error"]


def test_expired_running_job_also_requeues_processing_document(job_db):
    create_test_job(job_db)
    claimed = job_repo.claim_next("dead-worker", 60, now())
    assert claimed is not None
    with database.db_connection() as conn:
        conn.execute(
            "INSERT INTO documents "
            "(id, user_id, filename, storage_path, status, size_bytes, created_at, updated_at, job_id) "
            "VALUES (?, ?, ?, ?, 'processing', 1, ?, ?, ?)",
            ("doc-1", job_db, "notes.txt", "/tmp/notes.txt", now(), now(), "job-1"),
        )
        conn.execute(
            "UPDATE jobs SET lease_expires_at=? WHERE id=?",
            ((datetime.now(UTC) - timedelta(minutes=5)).isoformat(), "job-1"),
        )

    assert job_repo.recover_expired(now(), now()) == 1
    with database.db_connection() as conn:
        assert conn.execute("SELECT status FROM documents WHERE id='doc-1'").fetchone()[0] == "queued"


def test_worker_dispatches_handler_and_marks_success(job_db, monkeypatch):
    create_test_job(job_db, job_type="test")

    def handler(job, update_progress, is_cancel_requested):
        update_progress(50, "一半")
        assert not is_cancel_requested()
        return {"value": job["payload"]["value"] + 1}

    monkeypatch.setitem(job_worker.JOB_HANDLERS, "test", handler)
    worker = job_worker.JobWorker("worker-test")

    assert worker.run_once()
    stored = job_repo.get_for_user(job_db, "job-1")
    assert stored is not None
    assert stored["status"] == "succeeded"
    assert stored["result"] == {"value": 2}


def test_worker_retries_then_marks_failure(job_db, monkeypatch):
    create_test_job(job_db, job_type="test", max_attempts=1)
    monkeypatch.setitem(
        job_worker.JOB_HANDLERS, "test", lambda *_args: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    worker = job_worker.JobWorker("worker-test")

    assert worker.run_once()
    stored = job_repo.get_for_user(job_db, "job-1")
    assert stored is not None
    assert stored["status"] == "failed"
    assert "boom" in stored["error"]
