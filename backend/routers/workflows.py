"""Workflow Draft 与运行 API。"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from core.deps import verify_token
from schemas.workflow import WorkflowDraftRequest, WorkflowDraftResponse, WorkflowRunResponse
from services.project_service import get_project
from services.workflow_service import (
    get_draft,
    get_run_status_detail,
    save_draft,
    submit_workflow_run,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _check_project(user_id: int, project_id: int | None) -> None:
    if project_id is not None and get_project(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")


@router.get("/draft", response_model=WorkflowDraftResponse)
def get_workflow_draft(project_id: int | None = Query(None), user=Depends(verify_token)):
    _check_project(user["id"], project_id)
    return get_draft(user["id"], project_id)


@router.put("/draft", response_model=WorkflowDraftResponse)
def save_workflow_draft(req: WorkflowDraftRequest, user=Depends(verify_token)):
    _check_project(user["id"], req.project_id)
    return save_draft(user["id"], req.project_id, req.draft, req.expected_revision)


@router.get("/runs/latest")
def latest_run_status(project_id: int | None = Query(None), user=Depends(verify_token)):
    """当前项目最近一次 Workflow 运行的状态与各节点步骤（前端进度面板/排查用）。"""
    _check_project(user["id"], project_id)
    return get_run_status_detail(user["id"], project_id, None)


@router.get("/runs/{run_id}")
def get_run_status_route(run_id: str, user=Depends(verify_token)):
    return get_run_status_detail(user["id"], None, run_id)


@router.post("/run", response_model=WorkflowRunResponse, status_code=202)
async def run_workflow(project_id: int | None = Query(None), user=Depends(verify_token)):
    await asyncio.to_thread(_check_project, user["id"], project_id)
    return await asyncio.to_thread(submit_workflow_run, user["id"], project_id)
