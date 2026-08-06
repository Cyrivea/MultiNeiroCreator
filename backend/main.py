import logging

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from core.config import REDIS_URL
from core.database import init_db
from core.ratelimit import redis_client
from routers.assistant import router as assistant_router
from routers.auth import router as auth_router
from routers.projects import router as projects_router
from services.project_service import init_projects_table

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


app.include_router(auth_router)
app.include_router(assistant_router)
app.include_router(projects_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
async def bootstrap() -> None:
    init_db()
    init_projects_table()
    try:
        await redis_client.ping()
    except Exception as exc:
        raise RuntimeError(
            f"无法连接 Redis（{REDIS_URL}），限流功能依赖 Redis，服务拒绝启动。"
            "请先启动 redis-server（WSL: sudo service redis-server start）"
        ) from exc
