import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.bodylimit import BodySizeLimitMiddleware
from core.config import APP_ENV, CORS_ORIGINS, IS_PRODUCTION, REDIS_URL
from core.exceptions import register_exception_handlers
from core.logging_config import setup_logging
from core.migrations import run_migrations
from core.ratelimit import redis_client
from core.request_context import RequestContextMiddleware
from routers.assistant import router as assistant_router
from routers.auth import router as auth_router
from routers.capabilities import router as capabilities_router
from routers.jobs import router as jobs_router
from routers.projects import router as projects_router
from routers.workflows import router as workflows_router

setup_logging()
logger = logging.getLogger("main")

# 生产环境关闭交互式 API 文档（/docs /redoc /openapi.json），减少攻击面
app = FastAPI(
    title="Neyria API",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)
# add_middleware 后添加的在外层，实际栈由外到内：CORS → request_context → body 限制。
# CORS 最外让 413/500 也能拿到 CORS 头；request_context 包住 body 限制，使 413 也有 access log 和 X-Request-ID。
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],  # 允许浏览器 JS 读取，前端报错时可展示给用户
)

register_exception_handlers(app)


app.include_router(auth_router)
app.include_router(assistant_router)
app.include_router(capabilities_router)
app.include_router(projects_router)
app.include_router(jobs_router)
app.include_router(workflows_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
async def bootstrap() -> None:
    logger.info("服务启动", extra={"evt": "startup", "env": APP_ENV})
    run_migrations()
    try:
        await redis_client.ping()
    except Exception as exc:
        raise RuntimeError(
            f"无法连接 Redis（{REDIS_URL}），限流功能依赖 Redis，服务拒绝启动。"
            "请先启动 redis-server（WSL: sudo service redis-server start）"
        ) from exc
