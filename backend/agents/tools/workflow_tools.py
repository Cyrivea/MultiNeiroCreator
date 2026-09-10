"""Assistant 可调用的 Workflow 控制工具。

这些工具不直接把歌词结果发给聊天；它们修改 Draft、运行节点。工具返回的 JSON 带
内部字段 ``_ui_events``，编排器转成 workflow_snapshot SSE 事件后在回填模型前剥离，
现有画布据此实时更新。user/project 归属由编排器注入，模型不可见。
"""

import json

from langchain_core.tools import tool

from schemas.capability import LyricsGenerateInput, LyricsLanguage, LyricsMood, LyricsStyle
from services.capabilities import current_capability_context
from services.workflow_service import configure_lyrics, run_lyrics_workflow

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
) -> str:
    """在当前工作区创建或配置歌词生成节点，并自动连接输入和输出。

    Args:
        theme: 歌词主题，长度不能超过 200 个字符。
        style: 歌曲风格，只能选择平台支持的风格。
        mood: 歌词情绪，只能选择平台支持的情绪。
        language: 歌词语言，只能选择平台支持的语言。
    """
    execution = current_capability_context()
    inputs = LyricsGenerateInput(theme=theme, style=style, mood=mood, language=language)
    configured = configure_lyrics(execution.user_id, execution.project_id, inputs.model_dump())
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
async def run_current_workflow() -> str:
    """运行当前工作区 Workflow，并把节点的状态和结果写回画布。"""
    execution = current_capability_context()
    result = await run_lyrics_workflow(execution.user_id, execution.project_id)
    return _json(
        {
            "status": result["result"].status,
            "run_id": result["run_id"],
            "revision": result["revision"],
            "message": "当前 Workflow 已执行，结果已写入歌词节点。",
            "error": result["result"].error,
            "_ui_events": [
                {"type": "workflow_snapshot", "snapshot": result["running_draft"]},
                {"type": "workflow_snapshot", "snapshot": result["draft"]},
            ],
        }
    )


# 配置和运行是两个受控命令，不是 Capability 本身；
# CapabilityResult 只出现在 Workflow Runner 内部。
