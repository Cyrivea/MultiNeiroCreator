"""Workflow Draft HTTP Schema。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkflowDraftRequest(BaseModel):
    project_id: int | None = None
    draft: dict[str, Any]
    expected_revision: int = Field(ge=0)


class WorkflowDraftResponse(BaseModel):
    id: int | None
    revision: int
    draft: dict[str, Any]


class WorkflowRunResponse(BaseModel):
    run_id: str
    revision: int
    draft: dict[str, Any]
    status: Literal["succeeded", "model_unavailable", "failed"]
    result: dict[str, Any] | None = None
    error: str | None = None
