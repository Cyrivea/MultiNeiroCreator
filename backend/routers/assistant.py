from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from core.deps import verify_token
from schemas.chat import ChatRequest, ProfileRequest
from services.assistant_service import (
    clear_history,
    get_history,
    load_profile,
    save_profile,
    stream_chat,
    upload_document,
)


router = APIRouter(tags=["assistant"])


@router.post("/chat")
async def chat(req: ChatRequest, user=Depends(verify_token)):
    history = [item.model_dump() for item in req.history]
    return StreamingResponse(stream_chat(user, req.message, history), media_type="text/event-stream")


@router.post("/profile")
def set_profile(req: ProfileRequest, user=Depends(verify_token)):
    save_profile(user["id"], req.profile)
    return {"status": "success", "message": "个人信息已更新"}


@router.get("/profile")
def get_profile_route(user=Depends(verify_token)):
    return {"profile": load_profile(user["id"])}


@router.get("/history")
async def get_history_route(user=Depends(verify_token)):
    return get_history(user["id"])


@router.delete("/history")
async def clear_history_route(user=Depends(verify_token)):
    return clear_history(user["id"])


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), user=Depends(verify_token)):
    return await upload_document(file, user["id"])
