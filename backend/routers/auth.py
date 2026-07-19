from fastapi import APIRouter

from schemas.auth import AuthRequest
from services.auth_service import login, register, send_code


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-code")
async def send_code_route(req: AuthRequest):
    return await send_code(req.username)


@router.post("/register")
def register_route(req: AuthRequest, code: str = ""):
    return register(req.username, req.password, code)


@router.post("/login")
def login_route(req: AuthRequest):
    return login(req.username, req.password)
