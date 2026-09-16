"""Assistant 可调用的 Workflow 控制工具。

这些工具不直接把歌词结果发给聊天；它们修改 Draft、运行节点。工具返回的 JSON 带
内部字段 ``_ui_events``，编排器转成 workflow_snapshot SSE 事件后在回填模型前剥离，
现有画布据此实时更新。user/project 归属由编排器注入，模型不可见。
"""

import asyncio
import json

from langchain_core.tools import tool

from schemas.capability import (
    ImageGenerateInput,
    ImagePalette,
    ImageRatio,
    ImageStyle,
    LyricsGenerateInput,
    LyricsLanguage,
    LyricsMood,
    LyricsStyle,
)
from services.capabilities import current_capability_context
from services.workflow_service import (
    clear_workflow,
    configure_image,
    configure_lyrics,
    get_workflow_summary,
    submit_workflow_run,
)

# 模块级标记：工具注册器据此把这两个工具归入 Capability 路由（ainvoke 异步执行）。
CAPABILITY_ID = "workflow.control"


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


@tool
def configure_lyrics_workflow(
    theme: str,
    style: LyricsStyle = "流行抒情",
    mood: LyricsMood = "温柔、克制",
    language: LyricsLanguage = "中文",
    upstream_node_id: str | None = None,
) -> str:
    """在当前工作区创建或配置歌词生成节点，并自动连接输入和输出。

    当需要把当前节点接到一个已有节点后面时，把既有的上游节点 id 传给
    upstream_node_id；不传时默认接在输入端点后面。

    Args:
        theme: 歌词主题，长度不能超过 200 个字符。
        style: 歌曲风格，只能选择平台支持的风格。
        mood: 歌词情绪，只能选择平台支持的情绪。
        language: 歌词语言，只能选择平台支持的语言。
        upstream_node_id: 上游节点 ID，用于把当前节点接到已有工作流之后。
    """
    execution = current_capability_context()
    inputs = LyricsGenerateInput(theme=theme, style=style, mood=mood, language=language)
    configured = configure_lyrics(
        execution.user_id, execution.project_id, inputs.model_dump(), upstream_node_id
    )
    return _json(
        {
            "status": "configured",
            "workflow_id": configured["id"],
            "revision": configured["revision"],
            "node_id": configured["node_id"],
            "message": "已在工作区创建并配置歌词生成节点。接下来运行当前 Workflow。",
            "_ui_events": [{"type": "workflow_snapshot", "snapshot": configured["draft"]}],
        }
    )


@tool
def configure_image_workflow(
    prompt: str,
    style: ImageStyle = "电影概念艺术",
    ratio: ImageRatio = "16:9",
    palette: ImagePalette = "深蓝与紫色",
    upstream_node_id: str | None = None,
) -> str:
    """在当前工作区创建或配置图像生成节点，并自动连接输入和输出。

    当图像需要承接上一个节点的产物时，把该节点 id 传给 upstream_node_id，
    并在 prompt 里写上 `${upstream.result.content}` 引用上一步结果。

    Args:
        prompt: 画面描述，长度不能超过 300 个字符。
        style: 视觉风格，只能选择平台支持的风格。
        ratio: 画面比例，只能选择 16:9/1:1/9:16/4:3。
        palette: 色彩方向，只能选择平台支持的配色。
        upstream_node_id: 上游节点 ID，用于把当前节点接到已有工作流之后。
    """
    execution = current_capability_context()
    inputs = ImageGenerateInput(prompt=prompt, style=style, ratio=ratio, palette=palette)
    configured = configure_image(
        execution.user_id, execution.project_id, inputs.model_dump(), upstream_node_id
    )
    return _json(
        {
            "status": "configured",
            "workflow_id": configured["id"],
            "revision": configured["revision"],
            "node_id": configured["node_id"],
            "message": "已在工作区创建并配置图像生成节点。图像模型尚未配置时可先搭建流程。",
            "_ui_events": [{"type": "workflow_snapshot", "snapshot": configured["draft"]}],
        }
    )


@tool
def clear_workflow_draft() -> str:
    """仅在用户明确说“清空/重建/全部删掉重来”时才重置整个工作区。

    生成请求绝不能用这个工具；需要调整参数或节点时调用 configure_*，
    先看能否复用已有节点。
    """
    execution = current_capability_context()
    cleared = clear_workflow(execution.user_id, execution.project_id)
    return _json(
        {
            "status": "cleared",
            "workflow_id": cleared["id"],
            "revision": cleared["revision"],
            "message": "已清空工作区，只保留输入输出端点。",
            "_ui_events": [{"type": "workflow_snapshot", "snapshot": cleared["draft"]}],
        }
    )


@tool
def read_workflow_state() -> str:
    """在增删/连接节点或运行 Workflow 之前，先调用它读取当前工作区的完整状态。

    返回节点列表（带 capability_id / 参数 / 运行状态）和现有连接边列表。
    """
    execution = current_capability_context()
    summary = get_workflow_summary(execution.user_id, execution.project_id)
    return _json(
        {
            "status": "ok",
            "revision": summary["revision"],
            "workflow_id": summary["workflow_id"],
            "nodes": summary["nodes"],
            "edges": summary["edges"],
        }
    )


@tool
async def run_current_workflow() -> str:
    """把当前工作区 Workflow 排入后台执行队列，并把节点状态先写成“运行中”发到画布。"""
    execution = current_capability_context()
    result = await asyncio.to_thread(submit_workflow_run, execution.user_id, execution.project_id)
    return _json(
        {
            "status": result["status"],
            "run_id": result["run_id"],
            "job_id": result["job_id"],
            "revision": result["revision"],
            "message": "Workflow 已排队执行，节点显示运行状态，后台 Worker 完成后结果写回画布。",
            "_ui_events": [{"type": "workflow_snapshot", "snapshot": result["draft"]}],
        }
    )


# 配置和运行是两个受控命令，不是 Capability 本身；
# CapabilityResult 只出现在 Workflow Runner 内部。
