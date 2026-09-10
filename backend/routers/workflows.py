"""Workflow Draft 与运行 API。"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from core.deps import verify_token
from schemas.workflow import WorkflowDraftRequest, WorkflowDraftResponse, WorkflowRunResponse
from services.project_service import get_project
from services.workflow_service import get_draft, run_lyrics_workflow, save_draft

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


@router.post("/run", response_model=WorkflowRunResponse)
async def run_workflow(project_id: int | None = Query(None), user=Depends(verify_token)):
    await asyncio.to_thread(_check_project, user["id"], project_id)
    run = await run_lyrics_workflow(user["id"], project_id)
    result = run.pop("result")
    return {**run, "status": result.status, "result": result.result, "error": result.error}
