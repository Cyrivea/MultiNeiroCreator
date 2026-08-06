import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

DB_FILE = BACKEND_DIR / "data" / "conversations.db"

MAIL_USER = os.getenv("MAIL_USER", "")
MAIL_PASS = os.getenv("MAIL_PASS", "")
MAIL_HOST = os.getenv("MAIL_HOST", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "未配置 SECRET_KEY 环境变量，服务拒绝启动。"
        "请在 .env 中设置一个随机密钥，例如：python -c \"import secrets; print(secrets.token_hex(32))\""
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
API_KEY = os.getenv("API_KEY", "").strip()
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "").strip()

# ===== 限流配置（core/ratelimit.py 使用，全部可用环境变量覆盖）=====
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

CHAT_RATE_PER_MINUTE = int(os.getenv("CHAT_RATE_PER_MINUTE", "10"))
CHAT_RATE_PER_DAY = int(os.getenv("CHAT_RATE_PER_DAY", "200"))
LOGIN_RATE_PER_MINUTE = int(os.getenv("LOGIN_RATE_PER_MINUTE", "5"))  # 每 IP+邮箱
REGISTER_RATE_PER_MINUTE = int(os.getenv("REGISTER_RATE_PER_MINUTE", "5"))  # 每 IP
CODE_SEND_COOLDOWN_SECONDS = int(os.getenv("CODE_SEND_COOLDOWN_SECONDS", "60"))
CODE_SEND_PER_EMAIL_PER_DAY = int(os.getenv("CODE_SEND_PER_EMAIL_PER_DAY", "10"))
CODE_SEND_PER_IP_PER_DAY = int(os.getenv("CODE_SEND_PER_IP_PER_DAY", "20"))
UPLOAD_MAX_FILE_MB = int(os.getenv("UPLOAD_MAX_FILE_MB", "30"))
UPLOAD_DAILY_TOTAL_MB = int(os.getenv("UPLOAD_DAILY_TOTAL_MB", "100"))
