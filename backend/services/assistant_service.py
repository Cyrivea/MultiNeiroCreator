import asyncio
import json
import os
import tempfile
from typing import AsyncGenerator

from fastapi import HTTPException, UploadFile

from agents.neyria import build_system_prompt, client, tools_map, tools_schema
from repositories.chat_repo import append_message, clear_history as repo_clear_history, list_history
from repositories.user_repo import get_profile, update_profile
from services.rag import add_document, delete_document, list_documents, reindex_document, replace_document, search


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


async def stream_chat(
    user: dict,
    message: str,
    history: list[dict],
    project_id: int | None = None,
) -> AsyncGenerator[str, None]:
    if client is None:
        raise HTTPException(status_code=503, detail="未配置 API_KEY，聊天功能暂不可用")

    try:
        docs = await asyncio.to_thread(search, message, n_results=3, user_id=user["id"], project_id=project_id)
        context = "\n".join(docs) if docs else ""
    except Exception:
        context = ""

    profile = load_profile(user["id"])
    system_prompt = build_system_prompt(profile, context)

    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    messages.append({"role": "user", "content": message})

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
    clean_history = []
    for item in messages:
        if item.get("role") in ["user", "assistant"] and item.get("content"):
            if item.get("role") == "assistant" and item.get("tool_calls"):
                continue
            clean_history.append({"role": item["role"], "content": item["content"]})

    append_message(user["id"], "user", message, project_id)
    append_message(user["id"], "assistant", reply, project_id)
    yield f"data: {json.dumps({'type': 'done', 'history': clean_history, 'tool_used': func_name}, ensure_ascii=False)}\n\n"
