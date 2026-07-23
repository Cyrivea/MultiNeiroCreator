from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from core.deps import verify_token
from schemas.chat import ChatRequest, ProfileRequest, RagDocumentDeleteRequest
from services.assistant_service import (
    clear_history,
    get_history,
    get_rag_documents,
    load_profile,
    rebuild_rag_document,
    remove_rag_document,
    save_profile,
    stream_chat,
    upload_document,
)


router = APIRouter(tags=["assistant"])


@router.post("/chat")
async def chat(req: ChatRequest, user=Depends(verify_token)):
    history = [item.model_dump() for item in req.history]
    return StreamingResponse(
        stream_chat(user, req.message, history, req.project_id),
        media_type="text/event-stream",
    )


@router.post("/profile")
def set_profile(req: ProfileRequest, user=Depends(verify_token)):
    save_profile(user["id"], req.profile)
    return {"status": "success", "message": "个人信息已更新"}


@router.get("/profile")
def get_profile_route(user=Depends(verify_token)):
    return {"profile": load_profile(user["id"])}


@router.get("/history")
async def get_history_route(project_id: int | None = None, user=Depends(verify_token)):
    return get_history(user["id"], project_id)


@router.delete("/history")
async def clear_history_route(project_id: int | None = None, user=Depends(verify_token)):
    return clear_history(user["id"], project_id)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), user=Depends(verify_token)):
    return await upload_document(file, user["id"])


@router.get("/documents")
async def list_rag_documents_route(user=Depends(verify_token)):
    return get_rag_documents(user["id"])


@router.delete("/documents")
async def delete_rag_document_route(req: RagDocumentDeleteRequest, user=Depends(verify_token)):
    return remove_rag_document(req.filename, user["id"])


@router.post("/documents/reindex")
async def reindex_rag_document_route(
    filename: str = Query(..., min_length=1, max_length=255),
    user=Depends(verify_token),
):
    return rebuild_rag_document(filename, user["id"])
