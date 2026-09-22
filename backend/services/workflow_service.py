"""Workflow Draft 和单链路 Runner。

- ``configure_capability``：Assistant 往 Draft 里创建/更新一个工具节点并自动连线。
- ``run_workflow``：从 Input 出发按依赖顺序逐个执行能力节点，结果写回节点。
图像、视频、音频能力暂时没有 Provider，Runner 如实标记 ``model_unavailable``。
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import copy
import logging
import re
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.exceptions import AppError
from repositories import workflow_repo, workflow_run_repo
from schemas.capability import CapabilityResult
from services import job_service
from services.capabilities import CAPABILITY_REGISTRY, CapabilityContext, run_capability
from services.project_service import get_project

logger = logging.getLogger("workflow")

INPUT_ID = "workflow-input"
OUTPUT_ID = "workflow-output"

# 节点网格：与前端 positionForIndex 同一套坐标（起点 300、列宽 300、最多 3 列后换行）。
# 之前的“x = 320 + 300 * n”不取模，节点一多就淤出画布可视区，实测被压到右侧聊天面板后。
def position_x_for_index(tool_index: int) -> int:
    return 300 + (tool_index % 3) * 300

# “画布已读”印记：同一请求轮内，读过画布的用户/项目才被允许 configure/clear。
# 用 contextvars 保证并发请求互不影响；每轮聊天由编排器重置。
_canvas_read_stamp: contextvars.ContextVar[tuple[int, int | None] | None] = (
    contextvars.ContextVar("canvas_read_stamp", default=None)
)


def reset_canvas_read_stamp() -> None:
    _canvas_read_stamp.set(None)


def mark_canvas_read(user_id: int, project_id: int | None) -> None:
    _canvas_read_stamp.set((user_id, project_id))


def _ensure_canvas_read(user_id: int, project_id: int | None, draft: dict[str, Any]) -> None:
    """"先读再改"的保底实现（GLM 时代模型自觉不可靠）：

    模型没读而动手时，平台代它读一次再放行，并在结果里告知——
    安全性由机器保证，可观测性交给工具描述卷。评测过几次证明，该模型在
    prompt、工具描述、被拒重试三档提醒下依然 0% 主动读，不能让用户感受为瓶颈买单。
    """
    has_content = any(n.get("capability_id") for n in draft.get("nodes", []))
    if not has_content:
        mark_canvas_read(user_id, project_id)
        return
    if _canvas_read_stamp.get() == (user_id, project_id):
        return

    get_workflow_summary(user_id, project_id)
    mark_canvas_read(user_id, project_id)


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
                "x": 1230,
                "y": 280,
            },
        ],
        "edges": [],
        "endpointPositions": {"input": {"x": 36, "y": 280}},
    }


def get_workflow_summary(user_id: int, project_id: int | None) -> dict[str, Any]:
    """Assistant 读画布的快速摘要；nodes 带 capability_id/type/params，edges 是全量连接。"""
    current = get_draft(user_id, project_id)
    nodes = [
        {
            "id": n.get("id"),
            "kind": n.get("kind"),
            "type": n.get("type"),
            "name": n.get("name"),
            "capability_id": n.get("capability_id"),
            "params": n.get("params"),
            "run_status": n.get("runStatus"),
        }
        for n in current["draft"].get("nodes", [])
    ]
    edges = [
        {"source": e.get("source"), "target": e.get("target")}
        for e in current["draft"].get("edges", [])
    ]
    return {
        "revision": current["revision"],
        "workflow_id": current["id"],
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
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


_MAX_CAS_RETRIES = 5


def _mutate_draft_with_cas(
    user_id: int,
    project_id: int | None,
    mutate: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    """唯一合法的 Draft 写通道：读最新 → 业务修改 → CAS 写入，冲突重读重试。

    运行期间 Runner 每节点回写 与 模型/用户中途 configure 必然并发；
    没有乐观锁就是“最后一个整档覆盖的赢”，双节点/掉节点都是这里来的。
    """
    for _ in range(_MAX_CAS_RETRIES):
        current = get_draft(user_id, project_id)
        draft = copy.deepcopy(current["draft"])
        mutate(draft)  # 这里的 raise（如连线护栏）会原样传出，不算冲突
        saved = workflow_repo.upsert_if_revision(
            user_id, project_id, current["revision"], draft, _now()
        )
        if saved is not None:
            return {"id": saved["id"], "revision": saved["revision"], "draft": saved["draft"]}
    raise AppError("画布正在被并发更新，请稍后重试", status_code=409)


def save_draft(
    user_id: int,
    project_id: int | None,
    draft: dict[str, Any],
    expected_revision: int,
) -> dict[str, Any]:
    current = get_draft(user_id, project_id)
    if current["revision"] != expected_revision:
        raise AppError("Workflow 已被其他操作更新，请刷新后重试", status_code=409)
    # 运行期间禁止外部编辑：运行快照回写与用户写入并存会互相踩掉对方。
    # 前端有只读锁，这里是兜底；错误码 WORKFLOW_BUSY 供前端区分友好提示。
    # get_active_run 带自愈：job 已终局的僵尸运行会被顺手收尸，不会永远锁住画布。
    if get_active_run(user_id, current["id"]) is not None:
        raise AppError(
            "WORKFLOW_BUSY：Workflow 正在运行，运行结束后会自动解锁，请稍后再编辑",
            status_code=409,
        )
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


_INJECTION_HINT_RE = re.compile(r"忽略.{0,12}(系统提示|规则)|解除(限制|规则)|无视.{0,8}(规则|提示)")


def clear_workflow(
    user_id: int, project_id: int | None, user_message: str = ""
) -> dict[str, Any]:
    """清空画布：用户明确说“清空/重建”才允许，只对正常语气开放。"""
    _check_project_owner(user_id, project_id)
    # 注入式口吻（“忽略你的系统提示”等）诱导的破坏性操作不放行：
    # 这是 prompt 注入实测的真实撞车点，防御必须放服务端而不是靠模型看人下菜。
    if _INJECTION_HINT_RE.search(user_message or ""):
        raise AppError(
            "检测到注入式指令（要求忽略系统规则），破坏性操作被平台拒绝。请用正常语气描述需求。",
            status_code=422,
        )
    current = get_draft(user_id, project_id)
    _ensure_canvas_read(user_id, project_id, current["draft"])
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
    params, referenced_upstream = _normalize_upstream_refs(params)

    # 运行期间允许 configure（续命路径：模型可以在等上一跑结束后继续加节点），
    # 但写入必须走 CAS：与 Runner 的每节点回写并发时丢更新 = 双图像节点事故的根因。
    holder: dict[str, Any] = {}

    def mutate(draft: dict[str, Any]) -> None:
        _ensure_canvas_read(user_id, project_id, draft)
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
                "x": position_x_for_index(len([n for n in draft.get("nodes", []) if n.get("kind") != "endpoint"])),
                "y": 280,
            }
            # capability meta 字段已包含 name/badge/description/color，去掉 type 重复
            node.pop("type", None)
            node["type"] = tool_type
            draft.setdefault("nodes", []).append(node)
        # 重新配置参数 => 旧结果作废；无论是否中途加进来，一律复位待跑
        node["runStatus"] = "idle"
        # 参数增量合并：模型常常只传“要改的字段”，整包覆盖会把没改的字段抹成空
        # （实测：只说“比例换 1:1”就会丢掉 prompt/style）
        node["params"] = {**(node.get("params") or {}), **params}
        node["result"] = None
        _wire_node(draft, node["id"], upstream_node_id)
        if referenced_upstream:
            inbound = [
                edge
                for edge in draft.get("edges", [])
                if edge.get("target") == node["id"] and edge.get("source") != INPUT_ID
            ]
            if not inbound:
                raise AppError(
                    "检测到参数引用了上游结果，但该节点没有任何上游连线，运行时无法取到歌词。"
                    "请先调用 read_workflow_state 读画布，再用 upstream_node_id=上游节点 id 串联后重试。",
                    status_code=422,
                )
        holder["node_id"] = node["id"]

    saved = _mutate_draft_with_cas(user_id, project_id, mutate)
    return {"id": saved["id"], "revision": saved["revision"], "draft": saved["draft"], "node_id": holder["node_id"]}


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
# 模型会发明各种上游引用写法（如 ${workflow-node-xxx.result.content}）；
# 一律归一化为上面的规范形态，且在配置期必须看到真的有上游连线。
UPSTREAM_REF_RE = re.compile(r"\$\{[^}]*?\.result\.content\}")


def _normalize_upstream_refs(params: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """把任意 `${xxx.result.content}` 写法统一为规范引用；返回（新参数, 是否引用了上游）。"""
    normalized: dict[str, Any] = {}
    referenced = False
    for key, value in params.items():
        if isinstance(value, str) and UPSTREAM_REF_RE.search(value):
            referenced = True
            value = UPSTREAM_REF_RE.sub(UPSTREAM_RESULT_PATTERN, value)
        normalized[key] = value
    return normalized, referenced


def _upstream_content(upstream_node: dict[str, Any]) -> str | None:
    """抽取上游节点“要送到下游的内容”，严格按“多版本必须手选”规则：

    1. 有 selectedCandidateId：只认它，找不到对应的成功版本就算不可用；
    2. 只有一个成功版本：直接用它；
    3. 多个成功版本但没选定：返回 None，下游节点报“先选版本”。
    """
    candidates = upstream_node.get("candidates")
    if not isinstance(candidates, list):
        return None
    selected_id = upstream_node.get("selectedCandidateId")
    if selected_id:
        for cand in candidates:
            if cand.get("id") == selected_id and cand.get("status") == "succeeded":
                return cand.get("content")
        return None
    succeeded = [
        cand
        for cand in candidates
        if cand.get("status") == "succeeded" and isinstance(cand.get("content"), str)
    ]
    if len(succeeded) == 1:
        return succeeded[0].get("content")
    return None




def _failure_result(capability_id: str, message: str):
    return CapabilityResult(capability_id=capability_id, status="failed", error=message)


def _append_candidate(node: dict[str, Any], result: Any) -> None:
    """运行成功/失败都留一条候选记录；单一成功默认成下游的输入。"""
    content = result.result.get("content") if isinstance(result.result, dict) else None
    candidates = node.setdefault("candidates", [])
    candidates.append(
        {
            "id": f"cand-{uuid.uuid4().hex[:8]}",
            "status": result.status,
            "content": content,
            "error": result.error,
            "created_at": _now(),
        }
    )
    if result.status == "succeeded":
        succeeded = [c for c in candidates if c.get("status") == "succeeded"]
        if len(succeeded) == 1:
            node["selectedCandidateId"] = succeeded[0]["id"]


def _resolve_params(
    node: dict[str, Any], draft: dict[str, Any], results: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    """替换 ``${upstream.result.content}``；多版本上游未选择时拒绝执行而不是盲跑。"""
    node_id = str(node.get("id", ""))
    upstream_id = next(
        (
            str(edge.get("source"))
            for edge in draft.get("edges", [])
            if str(edge.get("target")) == node_id
        ),
        None,
    )
    upstream_node = next(
        (item for item in draft.get("nodes", []) if str(item.get("id")) == upstream_id),
        None,
    )
    upstream_content = (results.get(upstream_id) or {}).get("content") if upstream_id else None
    if upstream_content is None and upstream_node is not None:
        upstream_content = _upstream_content(upstream_node)

    params = node.get("params") or {}
    # 容忍历史/模型自造的引用形态（如 ${workflow-node-xxx.result.content}），统一按上游引用处理
    needs_reference = any(
        UPSTREAM_REF_RE.search(str(value)) for value in params.values()
    )
    if needs_reference and not upstream_content:
        return params, "上游已产出多个版本，请先在其中选一个，再运行当前节点"
    resolved: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, str) and upstream_content:
            resolved[key] = UPSTREAM_REF_RE.sub(upstream_content, value)
        else:
            resolved[key] = value
    return resolved, None


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
        resolved_params, params_error = _resolve_params(node, draft, node_results)
        if params_error:
            node["resolved_params"] = resolved_params
            node["runStatus"] = "failed"
            node["result"] = None
            node["error"] = params_error
            first_error = first_error or f"{node.get('name')}: {params_error}"
            final_status = "failed"
            _append_candidate(node, _failure_result(capability_id, params_error))
            continue
        result = await run_capability(
            capability_id,
            resolved_params,
            context=CapabilityContext(user_id=user_id, project_id=project_id, source="workflow"),
        )
        node["resolved_params"] = resolved_params
        node["runStatus"] = result.status
        node["result"] = result.result
        node["error"] = result.error
        _append_candidate(node, result)
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
            for key in ("runStatus", "result", "error", "resolved_params", "candidates", "selectedCandidateId"):
                latest_node[key] = node.get(key)

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


# ---------- 活跃运行判定（带自愈） ----------

_JOB_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def get_active_run(user_id: int, workflow_id: int | None) -> dict[str, Any] | None:
    """返回真正活着的运行；关联 job 已终局（失败/取消/成功）的 running/queued 记录
    是僵尸（例如用户取消 job、Worker 崩溃），顺手收尸并返回 None——
    防止画布编辑锁被一个永远等不回来的运行永久顶住。"""
    run = workflow_run_repo.find_active_for_workflow(user_id, workflow_id)
    if run is None:
        return None
    job_id = run.get("job_id")
    if not job_id:
        return run
    try:
        job = job_service.get_job(user_id, str(job_id))
    except Exception:
        return run
    if job["status"] in _JOB_TERMINAL_STATUSES:
        finalize_failed_run(
            user_id,
            run.get("project_id"),
            run["id"],
            f"关联任务已{job['status']}，运行自动清理",
        )
        return None
    return run


# ---------- 运行状态查询（Assistant 进度查询工具与前端进度面板共用） ----------


def _node_display_name(run: dict[str, Any], node_id: str | None) -> str:
    for node in run.get("draft_snapshot", {}).get("nodes", []):
        if str(node.get("id")) == node_id:
            return str(node.get("name") or node_id)
    return node_id or ""


def get_run_status_detail(
    user_id: int,
    project_id: int | None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """返回一次 Workflow 运行的完整状态；run_id 为空时取当前项目最近一条。"""
    if run_id is None:
        _check_project_owner(user_id, project_id)
        recent = workflow_run_repo.list_recent(user_id, project_id, limit=1)
        if not recent:
            raise AppError("目前没有可查询的 Workflow 运行记录", status_code=404)
        run = recent[0]
    else:
        found = workflow_run_repo.get(user_id, run_id)  # repo 已按 user_id 过滤
        if found is None:
            raise AppError("运行记录不存在", status_code=404)
        run = found
        _check_project_owner(user_id, run.get("project_id"))

    steps = workflow_run_repo.list_steps(user_id, run["id"])
    step_items = [
        {
            "node_id": step.get("node_id"),
            "node_name": _node_display_name(run, step.get("node_id")),
            "capability_id": step.get("capability_id"),
            "status": step.get("status"),
            "error": step.get("error"),
        }
        for step in steps
    ]
    done_count = sum(1 for s in step_items if s["status"] in {"succeeded", "failed"})
    return {
        "run_id": run["id"],
        "status": run["status"],
        "env_snapshot": run.get("env_snapshot"),
        "error": run.get("error"),
        "created_at": run.get("created_at"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "progress": {"done": done_count, "total": len(step_items)},
        "steps": step_items,
    }


async def await_workflow_idle(
    user_id: int,
    project_id: int | None,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    """等当前项目工作区的活跃运行结束（最长 timeout），返回最终运行状态。

    供“等它跑完再接着配/跑下一步”的编排使用；超时就如实返回 still_running，
    绝不允许把模型卡在未知数上。
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        current = await asyncio.to_thread(get_draft, user_id, project_id)
        active = await asyncio.to_thread(get_active_run, user_id, current["id"])
        if active is None:
            try:
                return await asyncio.to_thread(
                    get_run_status_detail, user_id, project_id, None
                )
            except AppError:
                return {"status": "idle", "message": "画布上没有运行记录"}
        await asyncio.sleep(2.0)
    return {"status": "still_running", "message": f"超过 {timeout_seconds}s 仍在运行"}


# ---------- 异步任务队列接入（submit → 后台 Worker 执行） ----------


def _build_env_snapshot() -> dict[str, Any]:
    """“当时环境”快照：模型、prompt hash、能力清单，随 run 落库。

    修复语义漂移需要“当时环境”可复现：模型名 + prompt SHA-256 + 段落文件名 + 能力清单。
    """
    import hashlib

    from agents.prompt_loader import _sections  # 装配出段节原文
    from core import config as cfg

    return {
        "chat_model": cfg.CHAT_MODEL,
        "lyrics_model": cfg.LYRICS_MODEL,
        "embedding_model": cfg.EMBEDDING_MODEL,
        "capabilities": sorted(CAPABILITY_REGISTRY.keys()),
        "prompt_sha256": hashlib.sha256("\n\n".join(_sections()).encode()).hexdigest()[:16],
        "prompt_sections": [f.name for f in sorted(Path(cfg.BACKEND_DIR / "prompts").glob("*.md"))],
    }


def submit_workflow_run(user_id: int, project_id: int | None) -> dict[str, Any]:
    """创建异步运行记录并入队任务；立即返回 run/job 信息，不阻塞 HTTP。"""
    _check_project_owner(user_id, project_id)
    current = get_draft(user_id, project_id)
    # 防重复提交：已有 queued/running 运行时拒绝，双跑会互相覆盖候选与状态。
    # 与保存编辑同一错误码，前端/助手读到都先查进度再决定动作。
    if get_active_run(user_id, current["id"]) is not None:
        raise AppError(
            "WORKFLOW_BUSY：已有 Workflow 正在运行，请先查询进度或等待其结束",
            status_code=409,
        )
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
        env_snapshot=_build_env_snapshot(),
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

    for node in ordered:
        # 每个节点执行前都重读最新 Draft：运行期间用户/AI 可能刚改过拓扑，
        # 只允许更新节点状态，坚决不回写 edges / nodes（避免“旧图盖新图”）。
        resolved_params, params_error = _resolve_params(node, draft_snapshot, node_outputs)
        step = workflow_run_repo.create_step(
            step_id=f"step-{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            node_id=node["id"],
            capability_id=node["capability_id"],
            input_payload=resolved_params,
            created_at=_now(),
        )
        if params_error:
            workflow_run_repo.finish_step(step["id"], "failed", None, params_error)

            def write_params_error(
                live_draft: dict[str, Any],
                _node_id: str = str(node["id"]),
                _error: str = params_error,
                _resolved: dict[str, Any] = resolved_params,
            ) -> None:
                live = next(
                    (n for n in live_draft.get("nodes", []) if str(n.get("id")) == _node_id),
                    None,
                )
                if live is not None:
                    live["runStatus"] = "failed"
                    live["result"] = None
                    live["error"] = _error
                    live["resolved_params"] = _resolved

            await asyncio.to_thread(_mutate_draft_with_cas, user_id, project_id, write_params_error)
            first_error = first_error or f"{node.get('name')}: {params_error}"
            final_status = "failed"
            continue
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
        def write_status(
            live_draft: dict[str, Any],
            _node_id: str = str(node["id"]),
            _result=result,
            _resolved: dict[str, Any] = resolved_params,
        ) -> None:
            live = next(
                (n for n in live_draft.get("nodes", []) if str(n.get("id")) == _node_id),
                None,
            )
            if live is None:
                return
            live["runStatus"] = _result.status
            live["result"] = _result.result
            live["error"] = _result.error
            live["resolved_params"] = _resolved
            _append_candidate(live, _result)

        await asyncio.to_thread(_mutate_draft_with_cas, user_id, project_id, write_status)
        if result.result and result.result.get("content") is not None:
            node_outputs[node["id"]] = result.result
        if result.status != "succeeded":
            first_error = first_error or f"{node.get('name')}: {result.error or result.status}"
            final_status = "failed" if result.status == "failed" else "model_unavailable"

    workflow_run_repo.update_status(
        run_id, final_status if final_status == "succeeded" else "failed", error=first_error, finished_at=_now()
    )
    await _notify_run_terminal(
        user_id, project_id, run_id, final_status, first_error, draft_snapshot
    )
    return {
        "run_id": run_id,
        "status": final_status,
        "error": first_error,
        "executed": [n["id"] for n in ordered],
    }


async def _notify_run_terminal(
    user_id: int,
    project_id: int | None,
    run_id: str,
    status: str,
    error: str | None,
    draft_snapshot: dict[str, Any],
) -> None:
    """运行终态 → 向会话插入一条 system-notice 消息（不刷新聊天轮询可捕）

    这是“会 +(system-notice) 通知”的最后一环；画布颜色由前端快照自己来处理。
    """
    names = [
        str(n.get("name") or n.get("id", "?"))
        for n in draft_snapshot.get("nodes", [])
        if n.get("capability_id")
    ]
    if status == "succeeded":
        content = (
            f"Workflow 已完成（{run_id}）：{', '.join(names) if names else '执行完毕'}。"
            "结果已写回画布节点。"
        )
    else:
        content = (
            f"Workflow {'失败' if status=='failed' else '已停止'}（{run_id}）："
            f"{error or '原因未知'}。节点已标记为失败，请在右侧画布检查参数。"
        )
    try:
        from repositories import chat_repo

        await asyncio.to_thread(
            chat_repo.append_message, user_id, "system-notice", content, project_id
        )
    except Exception:
        logger.warning(
            "终态通知插入失败",
            extra={"evt": "notify_failed", "run_id": run_id},
        )


def finalize_failed_run(
    user_id: int,
    project_id: int | None,
    run_id: str,
    error: str,
    run_snapshot: dict[str, Any] | None = None,
) -> None:
    """运行中途崩溃后的“清扫队”：把卡在 running 的节点如实标 failed。

    不这么做的话，workflow_runs 停在 running、画布节点停在 running、
    前端的运行锁和“运行中”横幅会永久挂起（实测生产事故：job 重试 3/3 耗尽，
    但 UI 以为还在跑）。
    """
    workflow_run_repo.update_status(run_id, "failed", error=error[:500], finished_at=_now())

    def mark_failed(draft: dict[str, Any]) -> None:
        for node in draft.get("nodes", []):
            if node.get("runStatus") == "running":
                node["runStatus"] = "failed"
                node["error"] = error[:300]

    # 收尸失败不阻断主呼喊：CAS 耗尽时上层 job/retry 总会再试一次
    with contextlib.suppress(AppError):
        _mutate_draft_with_cas(user_id, project_id, mark_failed)
    _notify_run_terminal_sync(user_id, project_id, run_id, "failed", error, run_snapshot)


def _notify_run_terminal_sync(
    user_id: int,
    project_id: int | None,
    run_id: str,
    status: str,
    error: str | None,
    draft_snapshot: dict[str, Any] | None,
) -> None:
    """同步通知（准点发生）：把“Workflow 已完成/失败”写成聊天侧一条可见消息。"""
    if status != "succeeded" and not error:
        return
    names = [
        str(n.get("name") or n.get("id", "?"))
        for n in (draft_snapshot or {}).get("nodes", [])
        if n.get("capability_id")
    ]
    if status == "succeeded":
        content = (
            f"Workflow 已完成：{', '.join(names) if names else '执行完毕'}。"
            "结果已写回画布节点。"
        )
    else:
        content = (
            f"Workflow {'失败' if status == 'failed' else '已取消'}："
            f"{error or '原因未知'}。画布节点已标记为失败，请检查参数。"
        )
    try:
        from repositories import chat_repo

        chat_repo.append_message(user_id, "system-notice", content, project_id)
    except Exception:
        # 通知失败不影响主流程（写日志排查见下的 log/wrk）
        import logging as _logging

        _logging.getLogger("workflow").warning("终态通知写入失败: %s", run_id)


def execute_workflow_run_job(
    job_id: str,
    run_id: str,
    draft_snapshot: dict[str, Any],
    user_id: int,
    project_id: int | None,
) -> dict[str, Any]:
    """同步入口，供 Worker 调用；内部用 asyncio.run 驱动 async Capability Runtime。"""
    workflow_run_repo.update_status(run_id, "running", started_at=_now())
    try:
        return asyncio.run(_execute_snapshot_run(user_id, project_id, run_id, draft_snapshot))
    except Exception as exc:
        # 崩溃不烂尾：如实标记运行失败并解锁画布，再让 Worker 打出 job 层的重试/失败
        finalize_failed_run(user_id, project_id, run_id, f"{type(exc).__name__}: {exc}")
        raise
