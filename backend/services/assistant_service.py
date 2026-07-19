import asyncio
import json
import os
import tempfile
from typing import AsyncGenerator

from fastapi import HTTPException, UploadFile

from agents.neyria import build_system_prompt, client, tools_map, tools_schema
from repositories.chat_repo import append_message, clear_history as repo_clear_history, list_history
from repositories.user_repo import get_profile, update_profile
from services.rag_service import add_document, search


def load_profile(user_id: int) -> str:
    return get_profile(user_id)


def save_profile(user_id: int, profile: str) -> None:
    update_profile(user_id, profile)


def get_history(user_id: int) -> list[dict]:
    return list_history(user_id)


def clear_history(user_id: int) -> dict:
    repo_clear_history(user_id)
    return {"status": "ok"}


async def upload_document(file: UploadFile) -> dict:
    try:
        suffix = os.path.splitext(file.filename or "")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        chunks_count = await asyncio.to_thread(add_document, tmp_path, file.filename or "upload.txt")
        os.unlink(tmp_path)
        return {"status": "success", "message": f"成功导入文档: {file.filename}（共分切成 {chunks_count} 块）"}
    except Exception as exc:
        return {"status": "error", "message": f"导入失败: {str(exc)}"}


async def stream_chat(user: dict, message: str, history: list[dict]) -> AsyncGenerator[str, None]:
    if client is None:
        raise HTTPException(status_code=503, detail="未配置 API_KEY，聊天功能暂不可用")

    try:
        docs = await asyncio.to_thread(search, message, n_results=3)
        context = "\n".join(docs) if docs else ""
    except Exception:
        context = ""

    profile = load_profile(user["id"])
    system_prompt = build_system_prompt(profile, context)

    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    messages.append({"role": "user", "content": message})

    response = client.chat.completions.create(model="glm-4-flash", messages=messages, tools=tools_schema)
    msg = response.choices[0].message
    func_name = None

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

    reply = ""
    for chunk in final_stream:
        if isinstance(chunk, dict):
            content = chunk["choices"][0]["delta"].get("content", "")
        else:
            delta = chunk.choices[0].delta
            content = delta.content if hasattr(delta, "content") and delta.content else ""
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

    append_message(user["id"], "user", message)
    append_message(user["id"], "assistant", reply)
    yield f"data: {json.dumps({'type': 'done', 'history': clean_history, 'tool_used': func_name}, ensure_ascii=False)}\n\n"
