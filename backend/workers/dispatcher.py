"""Job dispatcher：任务类型白名单与各处理器。"""

import logging
from collections.abc import Callable
from typing import Any

from services.document_service import process_document
from services.workflow_service import execute_workflow_run_job

logger = logging.getLogger("job_worker")


class JobCancelled(Exception):
    """任务在安全检查点发现用户取消请求。"""


JobContext = Callable[[int, str | None], None]


def handle_document_index(
    job: dict[str, Any],
    update_progress: JobContext,
    is_cancel_requested: Callable[[], bool],
) -> dict[str, Any]:
    try:
        return process_document(
            document_id=job["payload"]["document_id"],
            update_progress=update_progress,
            is_cancel_requested=is_cancel_requested,
        )
    except InterruptedError as exc:
        raise JobCancelled(str(exc)) from exc


def handle_workflow_run(
    job: dict[str, Any],
    update_progress: JobContext,
    _is_cancel_requested: Callable[[], bool],
) -> dict[str, Any]:
    payload = job["payload"]
    update_progress(10, "开始执行 Workflow")
    result = execute_workflow_run_job(
        job_id=job["id"],
        run_id=payload["run_id"],
        draft_snapshot=payload["draft"],
        user_id=job["user_id"],
        project_id=job["project_id"],
    )
    update_progress(100, "Workflow 执行完成")
    return result


JOB_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "document_ingest": handle_document_index,
    "document_reindex": handle_document_index,
    "workflow_run": handle_workflow_run,
}
