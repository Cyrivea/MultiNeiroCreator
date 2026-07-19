import random
import string
import time

import aiosmtplib
import sqlite3
from email.mime.text import MIMEText
from fastapi import HTTPException

from core.config import MAIL_HOST, MAIL_PASS, MAIL_PORT, MAIL_USER
from core.security import create_token, hash_password, verify_password
from repositories.user_repo import create_user, get_user_by_username


_codes: dict[str, dict] = {}


async def send_code(username: str) -> dict:
    if "@" not in username:
        raise HTTPException(status_code=400, detail="请输入有效的邮箱地址")

    code = "".join(random.choices(string.digits, k=6))
    _codes[username] = {"code": code, "expire": time.time() + 300}

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
    record = _codes.get(username)
    if not record:
        raise HTTPException(status_code=400, detail="请先获取验证码")
    if time.time() > record["expire"]:
        raise HTTPException(status_code=400, detail="验证码已过期")
    if record["code"] != code:
        raise HTTPException(status_code=400, detail="验证码错误")

    try:
        user_id = create_user(username, hash_password(password))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail="该邮箱已注册") from exc

    del _codes[username]
    token = create_token(user_id, username)
    return {"token": token, "username": username}


def login(username: str, password: str) -> dict:
    row = get_user_by_username(username)
    if row is None or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(row["id"], username)
    return {"token": token, "username": username}
