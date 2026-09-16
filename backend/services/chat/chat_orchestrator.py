"""对话编排器（C2 拆分件之三）：串起 备菜 → 多轮工具循环 → 流式输出 → 持久化。

C3 多轮工具循环（ReAct：推理 → 行动 → 观察 → 再推理）：
- 模型一次返回多个 tool_calls 时全部执行（按 index 聚合流式分片）；
- 工具结果回填后模型仍要工具就进入下一轮，最多 MAX_TOOL_ROUNDS 轮；
- 每轮最多执行 MAX_TOOL_CALLS_PER_ROUND 个调用，超出的必须逐个回复占位
  tool 消息（协议要求每个 tool_call_id 都有应答，否则下一轮请求非法）；
- 轮数耗尽后追加一条说明并发起"无工具"的收尾请求，强制模型给出最终回答，
  杜绝模型无限请求工具把对话拖死。

SSE 事件协议不变：content / tool / done / error，前端零改动。
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from starlette.concurrency import iterate_in_threadpool

from agents.neyria import client
from agents.tools.registry import tools_map, tools_schema
from core import config
from repositories.chat_repo import append_message
from services.capabilities import CapabilityContext, use_capability_context
from services.chat.context_builder import build_chat_context
from services.chat.tool_executor import execute_tool

# 模型名统一走环境变量（config.CHAT_MODEL），不在代码里写死
CHAT_MODEL = config.CHAT_MODEL

MAX_TOOL_ROUNDS = 5
MAX_TOOL_CALLS_PER_ROUND = 5

TOOL_LIMIT_NOTICE = (
    "已达到本次对话的工具调用轮数上限，请基于已获得的信息直接给出最终回答，不要再请求任何工具。"
)
TOOL_SKIPPED_RESULT = "已超出单轮工具调用数量上限，本次调用未执行。请基于已有结果回答。"
WEB_SEARCH_TOOL_NAME = "search_web"
TEXT_TOOL_CALL_MAX_LENGTH = 1200

logger = logging.getLogger("assistant")


def parse_textual_tool_call(text: str) -> tuple[str, str] | None:
    """识别模型偶尔输出的旧式文本工具调用，不把它直接展示给用户。

    智谱的标准响应是 ``delta.tool_calls``，但某些模型/兼容层会把调用写成
    ``search_web {"query": "..."}``。这不是正常回答，必须转换回编排器的
    结构化路径；解析失败时返回 None，普通文本仍按原样流出。
    """
    candidate = text.strip()
    if not candidate or len(candidate) > TEXT_TOOL_CALL_MAX_LENGTH:
        return None

    for tool_name in sorted(tools_map, key=len, reverse=True):
        if not candidate.startswith(tool_name):
            continue
        rest = candidate[len(tool_name) :].lstrip()
        if not rest.startswith("{"):
            continue
        try:
            arguments, end = json.JSONDecoder().raw_decode(rest)
        except json.JSONDecodeError:
            continue
        trailing = rest[end:].strip().removeprefix("```").strip()
        if trailing or not isinstance(arguments, dict):
            continue
        return tool_name, json.dumps(arguments, ensure_ascii=False)
    return None


def _could_be_textual_tool_call_prefix(text: str) -> bool:
    """判断尚未完整到达的文本是否仍可能是工具调用。"""
    candidate = text.lstrip()
    if not candidate or len(candidate) > TEXT_TOOL_CALL_MAX_LENGTH:
        return False
    return any(tool_name.startswith(candidate) or candidate.startswith(tool_name) for tool_name in tools_map)


def _tools_for_context(has_knowledge_context: bool) -> list[dict]:
    """有私有资料时锁住联网工具；无命中时只保留计算和联网后备。

    ``generate_lyrics_block`` 只对 Workflow Runner 内部使用——Assistant 必须通过
    configure_lyrics_workflow/run_current_workflow 操作画布，不能绕过 Workflow
    直接生成一首歌词丢回聊天框。
    """
    direct_capability_tools = {"generate_lyrics_block"}
    if has_knowledge_context:
        return [
            tool
            for tool in tools_schema
            if tool.get("function", {}).get("name") not in {WEB_SEARCH_TOOL_NAME}
            | direct_capability_tools
        ]
    return [
        tool
        for tool in tools_schema
        if tool.get("function", {}).get("name") not in {"get_current_time"}
        | direct_capability_tools
    ]


def split_ui_events(result_text: str) -> tuple[str, list[dict]]:
    """把工具结果里的 ``_ui_events`` 剥出来转成界面事件，模型只看到业务摘要。"""
    try:
        payload = json.loads(result_text)
    except (json.JSONDecodeError, TypeError):
        return result_text, []
    if not isinstance(payload, dict) or not isinstance(payload.get("_ui_events"), list):
        return result_text, []
    events = [event for event in payload.pop("_ui_events") if isinstance(event, dict)]
    return json.dumps(payload, ensure_ascii=False), events


def extract_stream_content(chunk) -> str:
    if not chunk.choices:
        return ""

    delta = chunk.choices[0].delta
    return delta.content if hasattr(delta, "content") and delta.content else ""


def merge_tool_call_delta(pending: dict[int, dict], delta_calls) -> None:
    """把流式分片按 index 聚合成完整的 tool_calls。

    流式模式下一个工具调用会被拆成多个分片（id/name 先到，arguments 逐段追加），
    多个并行调用靠分片上的 index 区分——旧代码只认 tool_calls[0]，多调用时
    其余调用的参数会被错误拼接到第一个上。
    """
    for tool_call in delta_calls:
        index = getattr(tool_call, "index", None)
        if index is None:
            index = 0
        slot = pending.setdefault(index, {"id": "", "name": "", "arguments": ""})
        if tool_call.id:
            slot["id"] = tool_call.id
        if tool_call.function:
            if tool_call.function.name:
                slot["name"] = tool_call.function.name
            if tool_call.function.arguments:
                slot["arguments"] += tool_call.function.arguments


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_chat(
    user: dict,
    message: str,
    project_id: int | None = None,
    attachments: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """对话流外层：兼做流中断兜底。

    SSE 响应头发出后全局异常 handler 就管不到了（无法再发 500），生成器里的
    异常只会表现为前端断流。这里统一兼做：记结构化错误日志 + 向前端发一条
    error 事件体面收尾（前端对未知类型静默忽略，兼容旧版本）。
    """
    started = time.perf_counter()
    try:
        async for event in _orchestrate(user, message, project_id, attachments):
            yield event
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "对话流中断: %s",
            type(exc).__name__,
            extra={
                "evt": "chat_stream_error",
                "error_type": type(exc).__name__,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        yield _sse({"type": "error", "message": "服务器开小差了，请稍后重试"})


async def _orchestrate(
    user: dict,
    message: str,
    project_id: int | None = None,
    attachments: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    if client is None:
        raise HTTPException(status_code=503, detail="未配置 API_KEY，聊天功能暂不可用")

    chat_started = time.perf_counter()
    ctx = await build_chat_context(user["id"], message, project_id, attachments)
    messages = ctx.messages

    available_tools = _tools_for_context(ctx.has_knowledge_context)

    reply = ""
    tools_used: list[str] = []
    tool_rounds = 0
    llm_started = time.perf_counter()
    first_token_at: float | None = None

    # ReAct 主循环：前 MAX_TOOL_ROUNDS 轮允许工具；最后一轮强制"只许说话"收尾
    for round_no in range(MAX_TOOL_ROUNDS + 1):
        allow_tools = round_no < MAX_TOOL_ROUNDS
        if not allow_tools:
            # 走到这里说明前面每一轮模型都在要工具：明示上限，逼出最终回答
            messages.append({"role": "system", "content": TOOL_LIMIT_NOTICE})

        request_kwargs: dict = {"model": CHAT_MODEL, "messages": messages, "stream": True}
        if allow_tools:
            request_kwargs["tools"] = available_tools
        stream = await asyncio.to_thread(client.chat.completions.create, **request_kwargs)

        pending_tool_calls: dict[int, dict] = {}
        textual_tool_candidate = ""
        # 兼容少数模型/代理把 function calling 错误降级成普通文本的情况。
        # 只暂存“像工具名开头”的前缀，普通回答仍逐 chunk 流出。
        async for chunk in iterate_in_threadpool(stream):
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            delta_calls = getattr(delta, "tool_calls", None)
            if delta_calls:
                if textual_tool_candidate:
                    fallback_call = parse_textual_tool_call(textual_tool_candidate)
                    if not fallback_call:
                        reply += textual_tool_candidate
                        yield _sse({"type": "content", "content": textual_tool_candidate})
                    textual_tool_candidate = ""
                merge_tool_call_delta(pending_tool_calls, delta_calls)
                continue
            content = extract_stream_content(chunk)
            if content:
                if textual_tool_candidate:
                    textual_tool_candidate += content
                elif _could_be_textual_tool_call_prefix(content):
                    textual_tool_candidate = content
                else:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    reply += content
                    yield _sse({"type": "content", "content": content})

        if textual_tool_candidate:
            fallback_call = parse_textual_tool_call(textual_tool_candidate)
            if fallback_call and not pending_tool_calls:
                tool_name, arguments = fallback_call
                pending_tool_calls[0] = {
                    "id": f"text-call-{round_no}",
                    "name": tool_name,
                    "arguments": arguments,
                }
            else:
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                reply += textual_tool_candidate
                yield _sse({"type": "content", "content": textual_tool_candidate})

        if not pending_tool_calls:
            break  # 模型不再要工具：本轮输出即最终回答

        tool_rounds += 1
        tool_calls = [pending_tool_calls[i] for i in sorted(pending_tool_calls)]
        messages.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {"name": call["name"], "arguments": call["arguments"]},
                    }
                    for call in tool_calls
                ],
            }
        )
        for position, call in enumerate(tool_calls):
            if position >= MAX_TOOL_CALLS_PER_ROUND:
                # 超额调用不执行，但必须应答该 tool_call_id，否则下一轮请求非法
                messages.append({"role": "tool", "content": TOOL_SKIPPED_RESULT, "tool_call_id": call["id"]})
                continue
            yield _sse({"type": "tool", "tool_name": call["name"]})
            # 跑腿的绝不抛异常：成功/被拒/失败都是一张结果单，这里不分叉
            with use_capability_context(
                CapabilityContext(
                    user_id=user["id"],
                    project_id=project_id,
                    source="assistant",
                )
            ):
                outcome = await execute_tool(call["name"], call["arguments"])
            # 工具可以携带界面事件（如 Workflow Draft 快照），立即透传给前端；
            # 剥离后再回填模型，避免模型把 Draft 当成歌词内容。
            model_result, ui_events = split_ui_events(outcome.result)
            for ui_event in ui_events:
                yield _sse(ui_event)
            tools_used.append(call["name"])
            messages.append({"role": "tool", "content": model_result, "tool_call_id": call["id"]})

    tool_used = tools_used[-1] if tools_used else None

    clean_history = ctx.clean_history
    await asyncio.to_thread(
        append_message,
        user["id"],
        "user",
        ctx.persist_text,
        project_id,
        ctx.attachments,
    )
    assistant_history_item: dict = {"role": "assistant", "content": reply}
    if ctx.citations:
        assistant_history_item["citations"] = ctx.citations
    clean_history.append(assistant_history_item)

    if ctx.citations:
        await asyncio.to_thread(
            append_message,
            user["id"],
            "assistant",
            reply,
            project_id,
            None,
            ctx.citations,
        )
    else:
        await asyncio.to_thread(append_message, user["id"], "assistant", reply, project_id)

    now = time.perf_counter()
    logger.info(
        "对话完成",
        extra={
            "evt": "chat_done",
            "model": CHAT_MODEL,
            "tool": tool_used,
            "tools_used": tools_used,
            "tool_rounds": tool_rounds,
            "history_items": len(clean_history),
            "reply_chars": len(reply),
            # TTFT 从首次请求 LLM 算起；若走了工具分支，包含工具耗时（用户体感口径）
            "ttft_ms": round(((first_token_at or now) - llm_started) * 1000, 1),
            "llm_ms": round((now - llm_started) * 1000, 1),
            "total_ms": round((now - chat_started) * 1000, 1),
        },
    )
    yield _sse(
        {
            "type": "done",
            "history": clean_history,
            "tool_used": tool_used,
            "citations": ctx.citations,
        }
    )
