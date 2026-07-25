import asyncio
import json
import os
import tempfile
from typing import AsyncGenerator

from fastapi import HTTPException, UploadFile

from agents.neyria import build_system_prompt, client, tools_map, tools_schema
from repositories.chat_repo import append_message, clear_history as repo_clear_history, list_history
from repositories.user_repo import get_profile, update_profile
from services.rag import add_document, delete_document, get_document_chunks, list_documents, reindex_document, replace_document, search


TOOL_TRIGGER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "calculate": ("计算", "算一下", "等于", "+", "-", "*", "/", "加", "减", "乘", "除"),
    "get_current_time": ("几点", "时间", "日期", "今天", "星期", "几号"),
    "search_web": (
        "新闻",
        "最新",
        "天气",
        "股价",
        "价格",
        "最近",
        "近况",
        "实时",
        "发生了什么",
        "查询",
        "搜索",
    ),
}

MAX_ATTACHMENT_CONTEXT_CHARS = 12000
MAX_RETRIEVED_CONTEXT_CHARS = 6000


def load_profile(user_id: int) -> str:
    return get_profile(user_id)


def save_profile(user_id: int, profile: str) -> None:
    update_profile(user_id, profile)


def get_history(user_id: int, project_id: int | None = None) -> list[dict]:
    return list_history(user_id, project_id)


def clear_history(user_id: int, project_id: int | None = None) -> dict:
    repo_clear_history(user_id, project_id)
    return {"status": "ok"}


async def upload_document(file: UploadFile, user_id: int, project_id: int | None = None) -> dict:
    tmp_path = None
    try:
        suffix = os.path.splitext(file.filename or "")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        chunks_count = await asyncio.to_thread(
            replace_document,
            tmp_path,
            file.filename or "upload.txt",
            user_id,
            project_id,
        )
        return {"status": "success", "message": f"成功导入文档: {file.filename}（共分切成 {chunks_count} 块）"}
    except Exception as exc:
        return {"status": "error", "message": f"导入失败: {str(exc)}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def get_rag_documents(user_id: int, project_id: int | None = None) -> list[dict]:
    return list_documents(user_id=user_id, project_id=project_id)


def remove_rag_document(filename: str, user_id: int, project_id: int | None = None) -> dict:
    deleted_count = delete_document(filename=filename, user_id=user_id, project_id=project_id)
    if deleted_count == 0:
        return {"status": "error", "message": f"未找到文档: {filename}"}
    return {"status": "success", "message": f"已删除文档: {filename}", "deleted_chunks": deleted_count}


def rebuild_rag_document(filename: str, user_id: int, project_id: int | None = None) -> dict:
    chunks_count = reindex_document(filename=filename, user_id=user_id, project_id=project_id)
    return {"status": "success", "message": f"已重建文档索引: {filename}", "chunks_count": chunks_count}


def should_enable_tools(message: str) -> bool:
    normalized = (message or "").strip().lower()
    if not normalized:
        return False

    for keywords in TOOL_TRIGGER_KEYWORDS.values():
        if any(keyword in normalized for keyword in keywords):
            return True

    return False


def extract_stream_content(chunk) -> str:
    if isinstance(chunk, dict):
        return chunk["choices"][0]["delta"].get("content", "")

    delta = chunk.choices[0].delta
    return delta.content if hasattr(delta, "content") and delta.content else ""


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


def build_attachment_context(
    user_id: int,
    project_id: int | None = None,
    attachments: list[dict] | None = None,
) -> str:
    normalized_attachments = normalize_attachments(attachments)
    if not normalized_attachments:
        return ""

    sections: list[str] = []
    consumed = 0
    for attachment in normalized_attachments:
        chunks = get_document_chunks(
            filename=attachment["name"],
            user_id=user_id,
            project_id=project_id,
        )
        if not chunks:
            continue

        remaining = MAX_ATTACHMENT_CONTEXT_CHARS - consumed
        if remaining <= 0:
            break

        content = "\n".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()
        if not content:
            continue

        snippet = content[:remaining]
        sections.append(f"[附件 {attachment['name']}]\n{snippet}")
        consumed += len(snippet)

    return "\n\n".join(sections)


def build_retrieved_context(
    user_id: int,
    message: str,
    project_id: int | None = None,
) -> str:
    if not (message or "").strip():
        return ""

    docs = search(message, n_results=3, user_id=user_id, project_id=project_id)
    if not docs:
        return ""

    joined = "\n".join(doc.strip() for doc in docs if doc.strip()).strip()
    return joined[:MAX_RETRIEVED_CONTEXT_CHARS] if joined else ""


async def stream_chat(
    user: dict,
    message: str,
    history: list[dict],
    project_id: int | None = None,
    attachments: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    if client is None:
        raise HTTPException(status_code=503, detail="未配置 API_KEY，聊天功能暂不可用")

    display_message = (message or "").strip() or "已发送附件"

    try:
        attachment_context, retrieved_context = await asyncio.gather(
            asyncio.to_thread(build_attachment_context, user["id"], project_id, attachments),
            asyncio.to_thread(build_retrieved_context, user["id"], message, project_id),
        )
        context_sections = [item for item in [attachment_context, retrieved_context] if item]
        context = "\n\n".join(context_sections)
    except Exception:
        context = ""

    profile = load_profile(user["id"])
    system_prompt = build_system_prompt(profile, context)

    messages = [{"role": "system", "content": system_prompt}]
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
        history_item = {"role": role, "content": content}
        if normalized_history_attachments:
            history_item["attachments"] = normalized_history_attachments
        clean_history.append(history_item)

    normalized_attachments = normalize_attachments(attachments)
    messages.append(
        {
            "role": "user",
            "content": format_message_content_for_model(message, normalized_attachments),
        }
    )
    current_user_history_item = {"role": "user", "content": message}
    if normalized_attachments:
        current_user_history_item["attachments"] = normalized_attachments
    clean_history.append(current_user_history_item)

    func_name = None
    reply = ""

    if should_enable_tools(message):
        response = client.chat.completions.create(model="glm-4-flash", messages=messages, tools=tools_schema)
        msg = response.choices[0].message

        if msg.tool_calls:
            tool_call = msg.tool_calls[0]
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            yield f"data: {json.dumps({'type': 'tool', 'tool_name': func_name}, ensure_ascii=False)}\n\n"
            result = tools_map[func_name].invoke(func_args)
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {"name": func_name, "arguments": tool_call.function.arguments},
                        }
                    ],
                }
            )
            messages.append({"role": "tool", "content": result, "tool_call_id": tool_call.id})
            final_stream = await asyncio.to_thread(
                client.chat.completions.create,
                model="glm-4-flash",
                messages=messages,
                stream=True,
            )
        else:
            final_stream = [{"choices": [{"delta": {"content": msg.content}}]}]
    else:
        final_stream = await asyncio.to_thread(
            client.chat.completions.create,
            model="glm-4-flash",
            messages=messages,
            stream=True,
        )

    for chunk in final_stream:
        content = extract_stream_content(chunk)
        if content:
            reply += content
            yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"

    messages.append({"role": "assistant", "content": reply})
    if not (message or "").strip():
        current_user_history_item["content"] = display_message
    append_message(user["id"], "user", current_user_history_item["content"], project_id, normalized_attachments)
    append_message(user["id"], "assistant", reply, project_id)
    clean_history.append({"role": "assistant", "content": reply})
    yield f"data: {json.dumps({'type': 'done', 'history': clean_history, 'tool_used': func_name}, ensure_ascii=False)}\n\n"
