"""Workflow Draft 和第一版单歌词节点 Runner。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from core.exceptions import AppError
from repositories import workflow_repo
from schemas.capability import LyricsGenerateInput
from services.capabilities import CapabilityContext, run_capability
from services.project_service import get_project

INPUT_ID = "workflow-input"
OUTPUT_ID = "workflow-output"
LYRICS_CAPABILITY = "lyrics.generate"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def empty_draft() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": INPUT_ID,
                "kind": "endpoint",
                "endpoint": "input",
                "name": "输入",
                "description": "主题、初始文本和参考文件",
                "x": 36,
                "y": 280,
            },
            {
                "id": OUTPUT_ID,
                "kind": "endpoint",
                "endpoint": "output",
                "name": "输出",
                "description": "展示、保存和导出最终结果",
                "x": 900,
                "y": 280,
            },
        ],
        "edges": [],
        "endpointPositions": {"input": {"x": 36, "y": 280}},
    }


def _check_project_owner(user_id: int, project_id: int | None) -> None:
    """默认工作区（project_id=None）允许；指定项目必须属于当前用户。"""
    if project_id is not None and get_project(user_id, project_id) is None:
        raise AppError("项目不存在", status_code=404)


def get_draft(user_id: int, project_id: int | None) -> dict[str, Any]:
    _check_project_owner(user_id, project_id)
    saved = workflow_repo.get(user_id, project_id)
    if saved is None:
        return {"id": None, "revision": 0, "draft": empty_draft()}
    return {"id": saved["id"], "revision": saved["revision"], "draft": saved["draft"]}


def save_draft(
    user_id: int,
    project_id: int | None,
    draft: dict[str, Any],
    expected_revision: int,
) -> dict[str, Any]:
    current = get_draft(user_id, project_id)
    if current["revision"] != expected_revision:
        raise AppError("Workflow 已被其他操作更新，请刷新后重试", status_code=409)
    _validate_draft_shape(draft)
    saved = workflow_repo.upsert(user_id, project_id, expected_revision + 1, draft, _now())
    return {"id": saved["id"], "revision": saved["revision"], "draft": saved["draft"]}


def _validate_draft_shape(draft: dict[str, Any]) -> None:
    nodes = draft.get("nodes")
    edges = draft.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise AppError("Workflow Draft 格式错误")
    if len(nodes) > 50 or len(edges) > 100:
        raise AppError("Workflow 节点或连接数量超过限制")
    ids = [str(node.get("id", "")) for node in nodes if isinstance(node, dict)]
    if len(ids) != len(set(ids)) or any(not node_id for node_id in ids):
        raise AppError("Workflow 节点 ID 不合法或重复")
    valid = set(ids) | {INPUT_ID, OUTPUT_ID}
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("source") not in valid or edge.get("target") not in valid:
            raise AppError("Workflow 包含无效连接")
def _find_node(draft: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    return next((node for node in draft.get("nodes", []) if node.get("id") == node_id), None)


def _ensure_edge(draft: dict[str, Any], source: str, target: str) -> None:
    edges = draft.setdefault("edges", [])
    if not any(edge.get("source") == source and edge.get("target") == target for edge in edges):
        edges.append({"source": source, "target": target})


def configure_lyrics(
    user_id: int,
    project_id: int | None,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    _check_project_owner(user_id, project_id)
    validated = LyricsGenerateInput.model_validate(inputs)
    current = get_draft(user_id, project_id)
    draft = current["draft"]
    node = next(
        (item for item in draft.get("nodes", []) if item.get("capability_id") == LYRICS_CAPABILITY),
        None,
    )
    if node is None:
        node = {
            "id": f"workflow-node-lyrics-{uuid.uuid4().hex[:10]}",
            "kind": "tool",
            "toolId": f"assistant-lyrics-{uuid.uuid4().hex[:10]}",
            "type": "lyrics",
            "capability_id": LYRICS_CAPABILITY,
            "name": "歌词生成",
            "badge": "文字创作",
            "description": "根据主题、情绪和曲风生成完整歌词草稿。",
            "color": "#b7b7b7",
            "x": 320,
            "y": 280,
        }
        draft.setdefault("nodes", []).append(node)
    node["params"] = validated.model_dump()
    node["runStatus"] = "idle"
    node["result"] = None
    _ensure_edge(draft, INPUT_ID, node["id"])
    _ensure_edge(draft, node["id"], OUTPUT_ID)
    revision = current["revision"] + 1
    saved = workflow_repo.upsert(user_id, project_id, revision, draft, _now())
    return {"id": saved["id"], "revision": revision, "draft": draft, "node_id": node["id"]}


def _assert_lyrics_graph(draft: dict[str, Any]) -> dict[str, Any]:
    lyrics_nodes = [
        node for node in draft.get("nodes", []) if node.get("capability_id") == LYRICS_CAPABILITY
    ]
    if len(lyrics_nodes) != 1:
        raise AppError("当前第一版 Workflow 需要且只能有一个歌词生成节点")
    node = lyrics_nodes[0]
    if not any(e.get("source") == INPUT_ID and e.get("target") == node["id"] for e in draft.get("edges", [])):
        raise AppError("歌词节点尚未连接输入节点")
    if not any(e.get("source") == node["id"] and e.get("target") == OUTPUT_ID for e in draft.get("edges", [])):
        raise AppError("歌词节点尚未连接输出节点")
    return node


async def run_lyrics_workflow(user_id: int, project_id: int | None) -> dict[str, Any]:
    _check_project_owner(user_id, project_id)
    current = await asyncio.to_thread(get_draft, user_id, project_id)
    draft = current["draft"]
    node = _assert_lyrics_graph(draft)
    node["runStatus"] = "running"
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    running_saved = await asyncio.to_thread(
        workflow_repo.upsert, user_id, project_id, current["revision"] + 1, draft, _now()
    )
    running_draft = running_saved["draft"]
    inputs = node.get("params") or {}
    result = await run_capability(
        LYRICS_CAPABILITY,
        inputs,
        context=CapabilityContext(user_id=user_id, project_id=project_id, source="workflow"),
    )
    latest = await asyncio.to_thread(get_draft, user_id, project_id)
    latest_node = _find_node(latest["draft"], node["id"])
    if latest_node is not None:
        latest_node["runStatus"] = result.status
        latest_node["result"] = result.result
        latest_node["error"] = result.error
    final_saved = await asyncio.to_thread(
        workflow_repo.upsert, user_id, project_id, latest["revision"] + 1, latest["draft"], _now()
    )
    return {
        "run_id": run_id,
        "revision": final_saved["revision"],
        "draft": final_saved["draft"],
        "running_draft": running_draft,
        "result": result,
    }
