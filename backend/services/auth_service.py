import secrets
import sqlite3

import aiosmtplib
import redis
from email.mime.text import MIMEText
from fastapi import HTTPException

from core.config import MAIL_HOST, MAIL_PASS, MAIL_PORT, MAIL_USER, REDIS_URL
from core.security import create_token, hash_password, verify_password
from repositories.user_repo import create_user, get_user_by_username


CODE_TTL_SECONDS = 300
CODE_MAX_ATTEMPTS = 5

# 验证码存 Redis（替代原进程内 _codes dict，多 worker/重启后依然有效）。
# 这里用同步客户端：register 是 sync 路由（bcrypt 在线程池里跑，不阻塞事件循环），
# 且单次 Redis 操作是亚毫秒级，即使在 async 的 send_code 里调用也可忽略。
_redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _code_key(email: str) -> str:
    return f"authcode:{email}"


def store_code(email: str) -> str:
    """生成并存储验证码：secrets 保证密码学安全，覆盖旧码并重置失败计数。"""
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    key = _code_key(email)
    pipe = _redis.pipeline(transaction=True)
    pipe.hset(key, mapping={"code": code, "attempts": 0})
    pipe.expire(key, CODE_TTL_SECONDS)
    pipe.execute()
    return code


def verify_and_consume_code(email: str, code: str) -> None:
    """校验验证码，通过则立即删除（一次性）；累计失败 5 次也删除，防在线爆破。"""
    key = _code_key(email)
    record = _redis.hgetall(key)
    if not record:
        raise HTTPException(status_code=400, detail="请先获取验证码（或验证码已过期）")
    if int(record.get("attempts", 0)) >= CODE_MAX_ATTEMPTS:
        _redis.delete(key)
        raise HTTPException(status_code=400, detail="验证码错误次数过多，已失效，请重新获取")
    if not secrets.compare_digest(record.get("code", ""), code):
        _redis.hincrby(key, "attempts", 1)
        raise HTTPException(status_code=400, detail="验证码错误")
    _redis.delete(key)


async def send_code(username: str) -> dict:
    code = store_code(username)

    msg = MIMEText(
        f"""
    <div style="font-family:sans-serif;padding:20px;">
        <h2>MultiNeiroCreator 验证码</h2>
        <p>您的验证码为：</p>
        <h1 style="color:#8b5cf6;letter-spacing:8px">{code}</h1>
        <p style="color:#999">验证码5分钟内有效，请勿泄露给他人。</p>
    </div>
    """,
        "html",
        "utf-8",
    )
    msg["Subject"] = "MultiNeiroCreator 注册验证码"
    msg["From"] = MAIL_USER
    msg["To"] = username

    try:
        await aiosmtplib.send(
            msg,
            hostname=MAIL_HOST,
            port=MAIL_PORT,
            username=MAIL_USER,
            password=MAIL_PASS,
            use_tls=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"邮件发送失败: {str(exc)}") from exc

    return {"status": "ok", "message": "验证码已发送"}


def register(username: str, password: str, code: str) -> dict:
    verify_and_consume_code(username, code)

    try:
        user_id = create_user(username, hash_password(password))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail="该邮箱已注册") from exc

    token = create_token(user_id, username)
    return {"token": token, "username": username}


# 账号不存在时也跑一次 bcrypt 校验（对着这个假哈希），让两种失败耗时一致，
# 防止通过响应时间差枚举"哪些邮箱注册过"（时序侧信道）
_DUMMY_HASH = hash_password("timing-equalizer")


def login(username: str, password: str) -> dict:
    row = get_user_by_username(username)
    password_ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)
    if row is None or not password_ok:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(row["id"], username)
    return {"token": token, "username": username}
