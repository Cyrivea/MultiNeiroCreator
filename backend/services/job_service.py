import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from core import config
from repositories import document_repo, job_repo, project_repo

SUPPORTED_JOB_TYPES = {"document_ingest", "document_reindex", "workflow_run"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _validate_payload(
    user_id: int,
    project_id: int | None,
    job_type: str,
    payload: dict[str, Any],
) -> None:
    if job_type not in SUPPORTED_JOB_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的任务类型: {job_type}")
    if job_type in {"document_ingest", "document_reindex"}:
        document_id = payload.get("document_id")
        if not isinstance(document_id, str) or len(document_id) != 32:
            raise HTTPException(status_code=422, detail=f"{job_type} 需要合法的 document_id")
        document = document_repo.get(document_id, user_id)
        if document is None:
            raise HTTPException(status_code=404, detail="文档不存在")
        if document["project_id"] != project_id:
            raise HTTPException(status_code=409, detail="任务项目与文档不一致")
    if job_type == "workflow_run":
        run_id = payload.get("run_id")
        if not isinstance(run_id, str) or len(run_id) < 8:
            raise HTTPException(status_code=422, detail="workflow_run 任务需要合法的 run_id")
        draft = payload.get("draft")
        if not isinstance(draft, dict) or not isinstance(draft.get("nodes"), list):
            raise HTTPException(status_code=422, detail="workflow_run 任务需要 draft 快照")


def create_job(
    user_id: int,
    job_type: str,
    payload: dict[str, Any],
    project_id: int | None = None,
) -> dict[str, Any]:
    _validate_payload(user_id, project_id, job_type, payload)
    if project_id is not None and project_repo.get_by_id(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    return job_repo.create(
        job_id=uuid.uuid4().hex,
        job_type=job_type,
        user_id=user_id,
        project_id=project_id,
        payload=payload,
        max_attempts=config.JOB_MAX_ATTEMPTS,
        created_at=utc_now(),
    )


def get_job(user_id: int, job_id: str) -> dict[str, Any]:
    job = job_repo.get_for_user(user_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


def list_jobs(user_id: int, project_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
    if project_id is not None and project_repo.get_by_id(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return job_repo.list_for_user(user_id, project_id, max(1, min(limit, 100)))


def retry_job(user_id: int, job_id: str) -> dict[str, Any]:
    existing = job_repo.get_for_user(user_id, job_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if existing["status"] != "failed":
        raise HTTPException(status_code=409, detail="只有失败任务可以人工重试")
    if existing["type"] in {"document_ingest", "document_reindex"}:
        document_id = existing["payload"].get("document_id")
        if not isinstance(document_id, str) or not document_repo.queue_for_retry(document_id, utc_now()):
            raise HTTPException(status_code=409, detail="关联文档当前状态不可重试")
    retried = job_repo.retry_failed(user_id, job_id, utc_now())
    if retried is None:
        raise HTTPException(status_code=409, detail="任务状态已变化，请稍后重试")
    return retried


def cancel_job(user_id: int, job_id: str) -> dict[str, Any]:
    existing = job_repo.get_for_user(user_id, job_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    job = job_repo.request_cancel(user_id, job_id, utc_now())
    assert job is not None
    if existing["status"] in {"queued", "running"} and existing["type"] in {
        "document_ingest",
        "document_reindex",
    }:
        document_id = existing["payload"].get("document_id")
        if isinstance(document_id, str):
            document_repo.mark_cancelled(document_id, utc_now())
    return job
