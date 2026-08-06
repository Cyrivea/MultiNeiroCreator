"""统一限流模块：所有接口的频率/配额限制都从这里走。

计数存储在 Redis（固定窗口计数器）：
- 计数键格式 rl:{规则名}:{业务key}，INCRBY + EXPIRE 构成一个窗口；
- "每日"类规则按 Asia/Shanghai 自然日划分窗口：key 中拼日期，过期时间取到次日零点；
- 启动时连不上 Redis 会拒绝启动（fail-fast，见 main.py），运行中 Redis 抖动则降级放行
  （fail-open），避免限流组件本身把服务打挂。

已知取舍：
- 固定窗口在窗口边界最多有 2 倍突发（0:59 和 1:01 各打满一轮），本项目场景可接受，
  需要更平滑时升级滑动窗口/令牌桶；
- 字节配额的"先检查后累加"分两步，极端并发下可能少量超发，严格原子需 Lua 脚本，留到部署阶段；
- IP 取 request.client.host：本地开发经 Vite 代理后全是 127.0.0.1，上反向代理后需改读 X-Forwarded-For。
"""
import logging
from datetime import datetime, timedelta

import pytz
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from redis.exceptions import RedisError

from core import config
from core.deps import verify_token
from schemas.auth import AuthRequest, SendCodeRequest

logger = logging.getLogger("ratelimit")

# BlockingConnectionPool：连接池打满时新请求排队等空闲连接（最多等 timeout 秒），
# 而默认 ConnectionPool 会直接抛 "Too many connections"，高并发下把限流打成 fail-open。
redis_client = aioredis.Redis(
    connection_pool=aioredis.BlockingConnectionPool.from_url(
        config.REDIS_URL, max_connections=50, timeout=5, decode_responses=True
    )
)

_TZ = pytz.timezone("Asia/Shanghai")


def _today() -> str:
    return datetime.now(_TZ).strftime("%Y-%m-%d")


def _seconds_until_midnight() -> int:
    now = datetime.now(_TZ)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(int((tomorrow - now).total_seconds()), 1)


async def hit(rule: str, key: str, limit: int, period_seconds: int, amount: int = 1) -> int | None:
    """计一次数并判断是否超限。未超限返回 None；超限返回建议等待秒数。

    超限后继续计数（爆破尝试本身也算次数），但窗口过期时间只在 key 新建时设置一次，
    不会被后续请求顺延。
    """
    redis_key = f"rl:{rule}:{key}"
    try:
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.incrby(redis_key, amount)
            pipe.ttl(redis_key)
            count, ttl = await pipe.execute()
        if ttl < 0:  # 新建的 key 还没有过期时间；并发下可能重复设置，误差可忽略
            await redis_client.expire(redis_key, period_seconds)
            ttl = period_seconds
        if count > limit:
            logger.warning("限流触发 rule=%s key=%s count=%s limit=%s", rule, key, count, limit)
            return max(ttl, 1)
        return None
    except (RedisError, OSError) as exc:
        logger.error("Redis 不可用，限流降级放行 rule=%s key=%s err=%s", rule, key, exc)
        return None


async def consume_quota(rule: str, key: str, amount: int, limit: int, period_seconds: int) -> bool:
    """配额型限制（如每日上传字节数）：先检查再累加，被拒绝的请求不消耗配额。"""
    redis_key = f"rl:{rule}:{key}"
    try:
        used = int(await redis_client.get(redis_key) or 0)
        if used + amount > limit:
            logger.warning("配额超限 rule=%s key=%s used=%s amount=%s limit=%s", rule, key, used, amount, limit)
            return False
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.incrby(redis_key, amount)
            pipe.ttl(redis_key)
            _, ttl = await pipe.execute()
        if ttl < 0:
            await redis_client.expire(redis_key, period_seconds)
        return True
    except (RedisError, OSError) as exc:
        logger.error("Redis 不可用，配额降级放行 rule=%s key=%s err=%s", rule, key, exc)
        return True


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------- FastAPI 依赖：挂到路由上即生效 ----------


async def chat_rate_limit(user=Depends(verify_token)) -> dict:
    """/chat 专用：每分钟 + 每日双重限制。

    必须在依赖层拒绝：/chat 返回 SSE 流，一旦进入 StreamingResponse 再拒绝，
    前端收到的是断流而不是 429。
    """
    uid = user["id"]
    wait = await hit("chat_min", str(uid), config.CHAT_RATE_PER_MINUTE, 60)
    if wait is not None:
        raise HTTPException(status_code=429, detail=f"消息发送太频繁，请 {wait} 秒后再试")
    wait = await hit("chat_day", f"{uid}:{_today()}", config.CHAT_RATE_PER_DAY, _seconds_until_midnight())
    if wait is not None:
        raise HTTPException(status_code=429, detail=f"今日对话已达上限（{config.CHAT_RATE_PER_DAY} 条），请明天再来")
    return user


async def login_rate_limit(req: AuthRequest, request: Request) -> None:
    wait = await hit("login", f"{_client_ip(request)}:{req.username}", config.LOGIN_RATE_PER_MINUTE, 60)
    if wait is not None:
        raise HTTPException(status_code=429, detail=f"登录尝试过于频繁，请 {wait} 秒后再试")


async def register_rate_limit(request: Request) -> None:
    wait = await hit("register", _client_ip(request), config.REGISTER_RATE_PER_MINUTE, 60)
    if wait is not None:
        raise HTTPException(status_code=429, detail=f"注册请求过于频繁，请 {wait} 秒后再试")


async def send_code_rate_limit(req: SendCodeRequest, request: Request) -> None:
    email, ip = req.username, _client_ip(request)
    wait = await hit("code_cd", email, 1, config.CODE_SEND_COOLDOWN_SECONDS)
    if wait is not None:
        raise HTTPException(status_code=429, detail=f"验证码发送过于频繁，请 {wait} 秒后再试")
    day_window = _seconds_until_midnight()
    wait = await hit("code_email_day", f"{email}:{_today()}", config.CODE_SEND_PER_EMAIL_PER_DAY, day_window)
    if wait is not None:
        raise HTTPException(status_code=429, detail="该邮箱今日验证码发送次数已达上限，请明天再试")
    wait = await hit("code_ip_day", f"{ip}:{_today()}", config.CODE_SEND_PER_IP_PER_DAY, day_window)
    if wait is not None:
        raise HTTPException(status_code=429, detail="今日验证码发送次数已达上限，请明天再试")


async def enforce_upload_limits(user_id: int, size: int) -> None:
    """/upload 专用：单文件大小 + 每日累计字节配额。"""
    max_file = config.UPLOAD_MAX_FILE_MB * 1024 * 1024
    if size > max_file:
        raise HTTPException(status_code=413, detail=f"单个文件不能超过 {config.UPLOAD_MAX_FILE_MB}MB")
    daily_total = config.UPLOAD_DAILY_TOTAL_MB * 1024 * 1024
    ok = await consume_quota("upload_day", f"{user_id}:{_today()}", size, daily_total, _seconds_until_midnight())
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=f"今日上传总量已达上限（{config.UPLOAD_DAILY_TOTAL_MB}MB），请明天再试",
        )
