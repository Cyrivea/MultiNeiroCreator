from fastapi import APIRouter, Depends

from core.ratelimit import login_rate_limit, register_rate_limit, send_code_rate_limit
from schemas.auth import AuthRequest, RegisterRequest, SendCodeRequest
from services.auth_service import login, register, send_code


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-code", dependencies=[Depends(send_code_rate_limit)])
async def send_code_route(req: SendCodeRequest):
    return await send_code(req.username)


@router.post("/register", dependencies=[Depends(register_rate_limit)])
def register_route(req: RegisterRequest):
    return register(req.username, req.password, req.code)


@router.post("/login", dependencies=[Depends(login_rate_limit)])
def login_route(req: AuthRequest):
    return login(req.username, req.password)
