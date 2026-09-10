"""工具执行器（C2 拆分件之一）：安全地执行一次模型请求的工具调用。

合同：无论成功 / 参数不合法被拒 / 执行时抛异常，一律返回 ToolOutcome，
**绝不向外抛异常**——编排器拿到结果单只管转交给模型，流程不分叉；
三种结局的差异只体现在日志里（排障用），不体现在控制流上。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

from agents.tools.registry import capability_map, tools_map

logger = logging.getLogger("assistant")

MAX_TOOL_ARG_LENGTH = 500


@dataclass
class ToolOutcome:
    """工具执行的"结果单"。result 是给模型看的文本，ok 只用于日志/埋点。"""

    result: str
    ok: bool


def validate_tool_call(func_name: str, func_args: dict) -> str | None:
    """校验模型返回的工具调用，返回错误信息；合法时返回 None。"""
    if func_name not in tools_map:
        return f"不支持的工具: {func_name}"
    if not isinstance(func_args, dict):
        return "工具参数格式错误"
    for value in func_args.values():
        if isinstance(value, str) and len(value) > MAX_TOOL_ARG_LENGTH:
            return "工具参数过长"
    return None


async def execute_tool(func_name: str, func_args_raw: str) -> ToolOutcome:
    """执行一次工具调用；同步工具和生产能力都不会阻塞聊天事件循环。"""
    try:
        func_args = json.loads(func_args_raw)
    except (json.JSONDecodeError, TypeError):
        func_args = None
    error = "工具参数解析失败" if func_args is None else validate_tool_call(func_name, func_args)
    if error:
        logger.warning(
            "工具调用被拒绝: %s",
            error,
            extra={"evt": "tool_rejected", "tool": func_name, "reason": error},
        )
        return ToolOutcome(result=f"工具调用被拒绝：{error}", ok=False)

    started = time.perf_counter()
    try:
        if func_name in capability_map:
            # Agent 请求上下文由编排器通过 Capability Runtime 的 ContextVar 绑定；
            # 它不会混进模型可见的工具参数。
            result = await tools_map[func_name].ainvoke(func_args)
        else:
            # 同步工具（如联网搜索可阻塞 5s+）必须丢线程池，否则阻塞事件循环拖死其他用户的 SSE。
            result = await asyncio.to_thread(tools_map[func_name].invoke, func_args)
    except Exception as exc:
        logger.exception(
            "工具执行失败: %s",
            type(exc).__name__,
            extra={
                "evt": "tool_error",
                "tool": func_name,
                "error_type": type(exc).__name__,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return ToolOutcome(result="工具执行失败，请换个方式提问或稍后重试。", ok=False)

    logger.info(
        "工具调用完成",
        extra={
            "evt": "tool_call",
            "tool": func_name,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "result_chars": len(str(result)),
        },
    )
    return ToolOutcome(result=str(result), ok=True)
