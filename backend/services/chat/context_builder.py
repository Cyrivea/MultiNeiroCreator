"""上下文构建器：组装模型消息，并保留 RAG 来源引用元数据。"""

import asyncio
import logging
import time
from dataclasses import dataclass, field

from agents.neyria import build_system_prompt
from core import config
from repositories.chat_repo import list_history
from repositories.user_repo import get_profile
from services.rag import get_document_chunk_hits, search_with_metadata

MAX_ATTACHMENT_CONTEXT_CHARS = 12000
MAX_RETRIEVED_CONTEXT_CHARS = 6000

logger = logging.getLogger("assistant")


@dataclass
class ChatContext:
    """一次对话所需的全部上下文成品。"""

    messages: list[dict]
    clean_history: list[dict]
    persist_text: str
    attachments: list[dict]
    citations: list[dict] = field(default_factory=list)
    has_knowledge_context: bool = False


def normalize_attachments(attachments: list[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    for attachment in attachments or []:
        name = str(attachment.get("name", "")).strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "kind": attachment.get("kind"),
                "badge": attachment.get("badge"),
                "meta": attachment.get("meta"),
            }
        )
    return normalized


def format_message_content_for_model(content: str, attachments: list[dict] | None = None) -> str:
    normalized_attachments = normalize_attachments(attachments)
    if not normalized_attachments:
        return content

    attachment_names = "、".join(item["name"] for item in normalized_attachments)
    base_content = (content or "").strip() or "用户发送了附件，请结合附件内容处理本条请求。"
    return f"{base_content}\n\n[该条消息附带文件：{attachment_names}]"


def _citation_from_hit(hit: dict, source_fallback: str) -> dict:
    return {
        "source": hit.get("source", source_fallback),
        "document_id": hit.get("document_id"),
        "chunk_index": int(hit.get("chunk_index", 0)),
        "chunk_count": int(hit.get("chunk_count", 0)),
        "distance": hit.get("distance"),
    }


def build_attachment_context(
    user_id: int,
    project_id: int | None = None,
    attachments: list[dict] | None = None,
) -> tuple[str, list[dict]]:
    normalized_attachments = normalize_attachments(attachments)
    if not normalized_attachments:
        return "", []

    sections: list[str] = []
    citations: list[dict] = []
    consumed = 0
    for attachment in normalized_attachments:
        hits = get_document_chunk_hits(
            filename=attachment["name"],
            user_id=user_id,
            project_id=project_id,
        )
        if not hits:
            continue

        remaining = MAX_ATTACHMENT_CONTEXT_CHARS - consumed
        if remaining <= 0:
            break

        content_parts: list[str] = []
        for hit in hits:
            text = str(hit.get("content", "")).strip()
            if not text:
                continue
            content_parts.append(text)
            citations.append(_citation_from_hit(hit, attachment["name"]))
        content = "\n".join(content_parts).strip()
        if not content:
            continue

        snippet = content[:remaining]
        sections.append(f"[附件 {attachment['name']}]\n{snippet}")
        consumed += len(snippet)

    return "\n\n".join(sections), citations


def build_retrieved_context(
    user_id: int,
    message: str,
    project_id: int | None = None,
) -> tuple[str, list[dict]]:
    if not (message or "").strip():
        return "", []

    hits = search_with_metadata(message, n_results=3, user_id=user_id, project_id=project_id)
    if not hits:
        return "", []

    sections: list[str] = []
    citations: list[dict] = []
    for hit in hits:
        content = str(hit.get("content", "")).strip()
        if not content:
            continue
        source = str(hit.get("source", "未知文档"))
        chunk_index = int(hit.get("chunk_index", 0)) + 1
        sections.append(f"[来源：{source}｜片段 {chunk_index}]\n{content}")
        citations.append(_citation_from_hit(hit, source))

    joined = "\n\n".join(sections).strip()
    return (joined[:MAX_RETRIEVED_CONTEXT_CHARS] if joined else ""), citations


def assemble_messages(
    system_prompt: str,
    history: list[dict],
    message: str,
    attachments: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """纯函数：把各层素材按固定顺序拼成 (messages, clean_history)。"""
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    clean_history: list[dict] = []
    for item in history:
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        normalized_history_attachments = normalize_attachments(item.get("attachments"))
        if role not in {"user", "assistant"} or not content:
            continue
        messages.append(
            {
                "role": role,
                "content": format_message_content_for_model(content, normalized_history_attachments),
            }
        )
        history_item: dict = {"role": role, "content": content}
        if normalized_history_attachments:
            history_item["attachments"] = normalized_history_attachments
        if item.get("citations"):
            history_item["citations"] = item["citations"]
        clean_history.append(history_item)

    normalized_attachments = normalize_attachments(attachments)
    messages.append(
        {
            "role": "user",
            "content": format_message_content_for_model(message, normalized_attachments),
        }
    )
    current_user_history_item: dict = {"role": "user", "content": message}
    if normalized_attachments:
        current_user_history_item["attachments"] = normalized_attachments
    clean_history.append(current_user_history_item)
    return messages, clean_history


async def build_chat_context(
    user_id: int,
    message: str,
    project_id: int | None = None,
    attachments: list[dict] | None = None,
) -> ChatContext:
    """并行构建附件上下文和普通 RAG 上下文，单个分支失败不连坐。"""
    rag_started = time.perf_counter()
    try:
        results: list[object] = await asyncio.gather(
            asyncio.to_thread(build_attachment_context, user_id, project_id, attachments),
            asyncio.to_thread(build_retrieved_context, user_id, message, project_id),
            return_exceptions=True,
        )
        attachment_result, retrieved_result = results
        attachment_context, attachment_citations = (
            attachment_result if isinstance(attachment_result, tuple) else ("", [])
        )
        retrieved_context, retrieved_citations = (
            retrieved_result if isinstance(retrieved_result, tuple) else ("", [])
        )
        for label, result in (("attachment", attachment_result), ("retrieval", retrieved_result)):
            if isinstance(result, Exception):
                logger.warning(
                    "单个知识库上下文分支失败",
                    extra={
                        "evt": "context_branch_error",
                        "branch": label,
                        "error_type": type(result).__name__,
                    },
                )
        context_sections = [item for item in [attachment_context, retrieved_context] if item]
        context = "\n\n".join(context_sections)
        citations = attachment_citations + retrieved_citations
        logger.info(
            "上下文构建完成",
            extra={
                "evt": "context_build",
                "duration_ms": round((time.perf_counter() - rag_started) * 1000, 1),
                "attachment_chars": len(attachment_context),
                "retrieved_chars": len(retrieved_context),
                "citation_count": len(citations),
            },
        )
    except Exception as exc:
        logger.warning(
            "上下文构建失败，降级为无 RAG 上下文: %s",
            type(exc).__name__,
            exc_info=True,
            extra={"evt": "context_build_error", "error_type": type(exc).__name__},
        )
        context = ""
        citations = []

    profile, full_history = await asyncio.gather(
        asyncio.to_thread(get_profile, user_id),
        asyncio.to_thread(list_history, user_id, project_id),
    )
    system_prompt = build_system_prompt(profile, context)
    history = full_history[-config.CHAT_HISTORY_MAX_ITEMS :]
    messages, clean_history = assemble_messages(system_prompt, history, message, attachments)
    persist_text = message if (message or "").strip() else "已发送附件"
    clean_history[-1]["content"] = persist_text

    return ChatContext(
        messages=messages,
        clean_history=clean_history,
        persist_text=persist_text,
        attachments=normalize_attachments(attachments),
        citations=citations,
        has_knowledge_context=bool(context),
    )
