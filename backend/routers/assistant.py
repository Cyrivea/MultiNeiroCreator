from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from core.deps import verify_token
from core.ratelimit import chat_rate_limit, enforce_upload_limits
from schemas.chat import ChatRequest, ProfileRequest, RagDocumentDeleteRequest
from services.assistant_service import (
    clear_history,
    get_history,
    get_rag_documents,
    load_profile,
    rebuild_rag_document,
    remove_rag_document,
    save_profile,
    upload_document,
)
from services.chat.chat_orchestrator import stream_chat

router = APIRouter(tags=["assistant"])


@router.post("/chat")
async def chat(req: ChatRequest, user=Depends(chat_rate_limit)):
    return StreamingResponse(
        stream_chat(user, req.message, req.project_id, [item.model_dump() for item in req.attachments]),
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
def get_history_route(project_id: int | None = None, user=Depends(verify_token)):
    return get_history(user["id"], project_id)


@router.delete("/history")
def clear_history_route(project_id: int | None = None, user=Depends(verify_token)):
    return clear_history(user["id"], project_id)


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    file: UploadFile = File(...),
    project_id: int | None = Query(None),
    user=Depends(verify_token),
):
    # UploadFile 底层是 SpooledTemporaryFile（超阈值自动落盘），seek 到末尾即可拿到大小而不读入内存
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    await enforce_upload_limits(user["id"], size)
    return await upload_document(file, user["id"], project_id, size)


@router.get("/documents")
def list_rag_documents_route(project_id: int | None = None, user=Depends(verify_token)):
    return get_rag_documents(user["id"], project_id)


@router.delete("/documents")
def delete_rag_document_route(req: RagDocumentDeleteRequest, user=Depends(verify_token)):
    return remove_rag_document(req.filename, user["id"], req.project_id, req.document_id)


@router.post("/documents/reindex")
def reindex_rag_document_route(
    document_id: str | None = Query(None, min_length=32, max_length=32),
    filename: str | None = Query(None, min_length=1, max_length=255),
    project_id: int | None = Query(None),
    user=Depends(verify_token),
):
    if document_id is None and filename is None:
        raise HTTPException(status_code=422, detail="document_id 或 filename 至少提供一个")
    return rebuild_rag_document(
        document_id=document_id, filename=filename, user_id=user["id"], project_id=project_id
    )
