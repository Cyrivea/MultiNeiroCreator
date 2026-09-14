"""Workflow Draft 和单链路 Runner。

- ``configure_capability``：Assistant 往 Draft 里创建/更新一个工具节点并自动连线。
- ``run_workflow``：从 Input 出发按依赖顺序逐个执行能力节点，结果写回节点。
图像、视频、音频能力暂时没有 Provider，Runner 如实标记 ``model_unavailable``。
"""

from __future__ import annotations

import asyncio
import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from core.exceptions import AppError
from repositories import workflow_repo, workflow_run_repo
from services import job_service
from services.capabilities import CAPABILITY_REGISTRY, CapabilityContext, run_capability
from services.project_service import get_project

INPUT_ID = "workflow-input"
OUTPUT_ID = "workflow-output"

# 每个 capability 在画布上的展示元信息；图片/视频/音频 await real Provider，UI 先按此占位。
CAPABILITY_META: dict[str, dict[str, Any]] = {
    "lyrics.generate": {
        "type": "lyrics",
        "name": "歌词生成",
        "badge": "文字创作",
        "description": "根据主题、情绪和曲风生成完整歌词草稿。",
        "color": "#b7b7b7",
    },
    "image.generate": {
        "type": "image",
        "name": "图像生成",
        "badge": "文字生图",
        "description": "把文字描述转成歌曲封面、角色设定和视觉概念图。",
        "color": "#d0d0d0",
    },
}


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


def clear_workflow(user_id: int, project_id: int | None) -> dict[str, Any]:
    """用户明确说“清空/重建工作区”时从头开始。生成请求不使用这个工具。"""
    _check_project_owner(user_id, project_id)
    current = get_draft(user_id, project_id)
    revision = current["revision"] + 1
    draft = empty_draft()
    saved = workflow_repo.upsert(user_id, project_id, revision, draft, _now())
    return {"id": saved["id"], "revision": revision, "draft": draft}


def _wire_node(
    draft: dict[str, Any],
    node_id: str,
    upstream_node_id: str | None = None,
) -> None:
    """连接一个能力节点。

    - 不传 upstream：默认挂到 Input → 节点 → Output（最小独立流程）。
    - 传了 upstream：把节点接到 upstream 之后；若原图是 upstream → Output，则
      把链尾顺延为 节点 → Output，形成 Input → … → upstream → 节点 → Output。
    """
    edges = draft.setdefault("edges", [])
    valid_sources = {INPUT_ID} | {
        str(n.get("id")) for n in draft.get("nodes", []) if isinstance(n, dict)
    }
    if upstream_node_id is None:
        _ensure_edge(draft, INPUT_ID, node_id)
        _ensure_edge(draft, node_id, OUTPUT_ID)
        return
    if upstream_node_id not in valid_sources or upstream_node_id == OUTPUT_ID:
        raise AppError("upstream 不存在或不可作为上游", status_code=422)

    # 新接线前清掉现有入边，保证每个节点只有一个主输入（当前阶段的约束）
    edges[:] = [edge for edge in edges if edge.get("target") != node_id]
    existing_tail = next(
        (
            edge
            for edge in edges
            if edge.get("source") == upstream_node_id and edge.get("target") == OUTPUT_ID
        ),
        None,
    )
    has_outgoing = any(edge.get("source") == node_id for edge in edges)
    _ensure_edge(draft, upstream_node_id, node_id)
    if existing_tail is not None and not has_outgoing:
        edges.remove(existing_tail)
        _ensure_edge(draft, node_id, OUTPUT_ID)


def configure_capability(
    user_id: int,
    project_id: int | None,
    capability_id: str,
    tool_type: str,
    params: dict[str, Any],
    upstream_node_id: str | None = None,
) -> dict[str, Any]:
    """创建或更新一个能力节点；支持把它接到既有链尾或默认 Input。"""
    _check_project_owner(user_id, project_id)
    meta = CAPABILITY_META.get(capability_id)
    if meta is None:
        raise AppError(f"未知的生产能力: {capability_id}")

    current = get_draft(user_id, project_id)
    draft = current["draft"]
    nodes = draft.get("nodes", [])
    # 同 capability 只保留一个实例：多余的连同连接线一起清除，避免并联残留
    same_capability_ids = [
        item.get("id")
        for item in nodes
        if isinstance(item, dict) and item.get("capability_id") == capability_id
    ]
    drop_ids = set(same_capability_ids[1:])
    if drop_ids:
        draft["nodes"] = [item for item in nodes if item.get("id") not in drop_ids]
        draft["edges"] = [
            edge
            for edge in draft.get("edges", [])
            if edge.get("source") not in drop_ids and edge.get("target") not in drop_ids
        ]
    node = next(
        (item for item in draft.get("nodes", []) if item.get("capability_id") == capability_id),
        None,
    )
    if node is None:
        node = {
            "id": f"workflow-node-{tool_type}-{uuid.uuid4().hex[:10]}",
            "kind": "tool",
            "toolId": f"assistant-{tool_type}-{uuid.uuid4().hex[:10]}",
            "type": tool_type,
            "capability_id": capability_id,
            **meta,
            "x": 320 + 300 * len(draft.get("nodes", [])),
            "y": 280,
        }
        # capability meta 字段已包含 name/badge/description/color，去掉 type 重复
        node.pop("type", None)
        node["type"] = tool_type
        draft.setdefault("nodes", []).append(node)
    node["params"] = params
    node["runStatus"] = "idle"
    node["result"] = None
    _wire_node(draft, node["id"], upstream_node_id)
    revision = current["revision"] + 1
    saved = workflow_repo.upsert(user_id, project_id, revision, draft, _now())
    return {"id": saved["id"], "revision": revision, "draft": draft, "node_id": node["id"]}


def configure_lyrics(
    user_id: int,
    project_id: int | None,
    inputs: dict[str, Any],
    upstream_node_id: str | None = None,
) -> dict[str, Any]:
    from schemas.capability import LyricsGenerateInput

    validated = LyricsGenerateInput.model_validate(inputs)
    return configure_capability(
        user_id,
        project_id,
        "lyrics.generate",
        "lyrics",
        validated.model_dump(),
        upstream_node_id,
    )


def configure_image(
    user_id: int,
    project_id: int | None,
    inputs: dict[str, Any],
    upstream_node_id: str | None = None,
) -> dict[str, Any]:
    from schemas.capability import ImageGenerateInput

    validated = ImageGenerateInput.model_validate(inputs)
    return configure_capability(
        user_id,
        project_id,
        "image.generate",
        "image",
        validated.model_dump(),
        upstream_node_id,
    )


def _execution_order(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """从 Input 出发做广度优先排序；能跑的能力节点按拓扑次序逐个执行。"""
    edges = draft.get("edges", [])
    nodes_by_id = {n["id"]: n for n in draft.get("nodes", [])}
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        outgoing.setdefault(str(edge.get("source", "")), []).append(str(edge.get("target", "")))

    ordered: list[dict[str, Any]] = []
    visited = set()
    queue = list(outgoing.get(INPUT_ID, []))
    if not queue:
        raise AppError("Workflow 还没有连接输入节点，请先从输入端点连出一个工具节点")
    while queue:
        node_id = queue.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)
        node = nodes_by_id.get(node_id)
        if node is None:
            continue
        if node.get("capability_id"):
            ordered.append(node)
        queue.extend(outgoing.get(node_id, []))

    if not ordered:
        raise AppError("Workflow 里还没有可执行的生产工具节点")
    return ordered


UPSTREAM_RESULT_PATTERN = "${upstream.result.content}"


def _resolve_params(node: dict[str, Any], draft: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    """把参数里的 ``${upstream.result.content}`` 替换为直接上游节点的输出。

    没有上游产物时保留原文，让能力自己决定是否缺参数；这样串联链路是数据流，
    不只是画布上的连线。
    """
    node_id = str(node.get("id", ""))
    upstream_id = next(
        (
            str(edge.get("source"))
            for edge in draft.get("edges", [])
            if str(edge.get("target")) == node_id
        ),
        None,
    )
    upstream_content = (results.get(upstream_id) or {}).get("content") if upstream_id else None
    params = node.get("params") or {}
    resolved: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, str) and upstream_content:
            resolved[key] = value.replace(UPSTREAM_RESULT_PATTERN, upstream_content)
        else:
            resolved[key] = value
    return resolved


async def run_workflow(user_id: int, project_id: int | None) -> dict[str, Any]:
    """从 Input 出发，依次执行可达的能力节点；结果按节点写回 Draft。"""
    _check_project_owner(user_id, project_id)
    current = await asyncio.to_thread(get_draft, user_id, project_id)
    draft = current["draft"]
    ordered = _execution_order(draft)
    # 校验未知能力，防护手写 Draft 里开进了未注册 Block
    for node in ordered:
        capability_id = node.get("capability_id")
        if capability_id not in CAPABILITY_REGISTRY:
            raise AppError(f"未注册的能力: {capability_id}")

    for node in ordered:
        node["runStatus"] = "running"
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    running_saved = await asyncio.to_thread(
        workflow_repo.upsert, user_id, project_id, current["revision"] + 1, draft, _now()
    )
    running_draft = running_saved["draft"]

    first_error: str | None = None
    final_status = "succeeded"
    node_results: dict[str, dict[str, Any]] = {}
    for node in ordered:
        capability_id = node["capability_id"]
        resolved_params = _resolve_params(node, draft, node_results)
        result = await run_capability(
            capability_id,
            resolved_params,
            context=CapabilityContext(user_id=user_id, project_id=project_id, source="workflow"),
        )
        node["resolved_params"] = resolved_params
        node["runStatus"] = result.status
        node["result"] = result.result
        node["error"] = result.error
        if result.result and result.result.get("content") is not None:
            node_results[node["id"]] = result.result
        if result.status != "succeeded":
            first_error = first_error or f"{node.get('name')}: {result.error or result.status}"
            final_status = "failed" if result.status == "failed" else "model_unavailable"

    latest = await asyncio.to_thread(get_draft, user_id, project_id)
    latest_by_id = {n.get("id"): n for n in latest["draft"].get("nodes", [])}
    for node in ordered:
        latest_node = latest_by_id.get(node["id"])
        if latest_node is not None:
            latest_node["runStatus"] = node["runStatus"]
            latest_node["result"] = node["result"]
            latest_node["error"] = node["error"]
            latest_node["resolved_params"] = node.get("resolved_params")

    final_saved = await asyncio.to_thread(
        workflow_repo.upsert, user_id, project_id, latest["revision"] + 1, latest["draft"], _now()
    )
    return {
        "run_id": run_id,
        "revision": final_saved["revision"],
        "draft": final_saved["draft"],
        "running_draft": running_draft,
        "status": final_status,
        "error": first_error,
        "executed": [n["id"] for n in ordered],
    }


# ---------- 异步任务队列接入（submit → 后台 Worker 执行） ----------


def submit_workflow_run(user_id: int, project_id: int | None) -> dict[str, Any]:
    """创建异步运行记录并入队任务；立即返回 run/job 信息，不阻塞 HTTP。"""
    _check_project_owner(user_id, project_id)
    current = get_draft(user_id, project_id)
    draft = current["draft"]
    ordered = _execution_order(draft)
    for node in ordered:
        capability_id = node.get("capability_id")
        if capability_id not in CAPABILITY_REGISTRY:
            raise AppError(f"未注册的能力: {capability_id}")

    run_id = f"run-{uuid.uuid4().hex[:12]}"
    # 先把节点标为 running 存库，画布会有“已排队”的即时反馈
    running_draft = copy.copy(draft)
    running_draft["nodes"] = [
        {
            **n,
            "runStatus": "running" if n.get("capability_id") else n.get("runStatus"),
        }
        for n in draft.get("nodes", [])
    ]
    running_draft["edges"] = list(draft.get("edges", []))
    saved = workflow_repo.upsert(user_id, project_id, current["revision"] + 1, running_draft, _now())

    job = job_service.create_job(
        user_id=user_id,
        job_type="workflow_run",
        payload={"run_id": run_id, "draft": running_draft},
        project_id=project_id,
    )
    workflow_run_repo.create(
        run_id=run_id,
        user_id=user_id,
        project_id=project_id,
        draft_revision=saved["revision"],
        draft_snapshot=running_draft,
        workflow_id=saved["id"],
        job_id=job["id"],
        created_at=_now(),
    )
    return {
        "run_id": run_id,
        "job_id": job["id"],
        "status": "queued",
        "revision": saved["revision"],
        "draft": running_draft,
    }


async def _execute_snapshot_run(
    user_id: int, project_id: int | None, run_id: str, draft_snapshot: dict[str, Any]
) -> dict[str, Any]:
    """后台 Worker 用 Draft 快照真实执行一条 Workflow；每一步写 step 和节点状态。"""
    ordered = _execution_order(draft_snapshot)
    for node in ordered:
        capability_id = node.get("capability_id")
        if capability_id not in CAPABILITY_REGISTRY:
            workflow_run_repo.update_status(
                run_id, "failed", error=f"未注册的能力: {capability_id}", finished_at=_now()
            )
            raise AppError(f"未注册的能力: {capability_id}")

    node_outputs: dict[str, dict[str, Any]] = {}
    first_error: str | None = None
    final_status = "succeeded"
    current_live = await asyncio.to_thread(get_draft, user_id, project_id)
    live_draft = current_live["draft"]
    live_by_id = {n.get("id"): n for n in live_draft.get("nodes", [])}

    for node in ordered:
        resolved_params = _resolve_params(node, draft_snapshot, node_outputs)
        step = workflow_run_repo.create_step(
            step_id=f"step-{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            node_id=node["id"],
            capability_id=node["capability_id"],
            input_payload=resolved_params,
            created_at=_now(),
        )
        result = await run_capability(
            node["capability_id"],
            resolved_params,
            context=CapabilityContext(user_id=user_id, project_id=project_id, source="workflow"),
        )
        workflow_run_repo.finish_step(
            step["id"],
            result.status if result.status != "model_unavailable" else "failed",
            result.result,
            result.error,
        )
        live_node = live_by_id.get(node["id"])
        if live_node is not None:
            live_node["runStatus"] = result.status
            live_node["result"] = result.result
            live_node["error"] = result.error
            live_node["resolved_params"] = resolved_params
            await asyncio.to_thread(
                workflow_repo.upsert,
                user_id,
                project_id,
                current_live["revision"] + 1,
                live_draft,
                _now(),
            )
        if result.result and result.result.get("content") is not None:
            node_outputs[node["id"]] = result.result
        if result.status != "succeeded":
            first_error = first_error or f"{node.get('name')}: {result.error or result.status}"
            final_status = "failed" if result.status == "failed" else "model_unavailable"

    workflow_run_repo.update_status(
        run_id, final_status if final_status == "succeeded" else "failed", error=first_error, finished_at=_now()
    )
    return {
        "run_id": run_id,
        "status": final_status,
        "error": first_error,
        "executed": [n["id"] for n in ordered],
    }


def execute_workflow_run_job(
    job_id: str,
    run_id: str,
    draft_snapshot: dict[str, Any],
    user_id: int,
    project_id: int | None,
) -> dict[str, Any]:
    """同步入口，供 Worker 调用；内部用 asyncio.run 驱动 async Capability Runtime。"""
    workflow_run_repo.update_status(run_id, "running", started_at=_now())
    return asyncio.run(_execute_snapshot_run(user_id, project_id, run_id, draft_snapshot))
