import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

DB_FILE = BACKEND_DIR / "data" / "conversations.db"

# ===== 运行环境 =====
# development / production：控制 API 文档开关等环境差异（main.py 使用）
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"

# CORS 白名单：逗号分隔的完整 Origin（协议+域名+端口），默认只放行本地开发地址。
# 开发环境前端经 Vite 代理（/api）访问后端，本身是同源请求；白名单管的是不走代理的直连场景。
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

MAIL_USER = os.getenv("MAIL_USER", "")
MAIL_PASS = os.getenv("MAIL_PASS", "")
MAIL_HOST = os.getenv("MAIL_HOST", "smtp.qq.com")
# 465 = 隐式 TLS，587 = STARTTLS，auth_service 按端口自动选择握手方式
MAIL_PORT = int(os.getenv("MAIL_PORT", "465"))

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "未配置 SECRET_KEY 环境变量，服务拒绝启动。"
        '请在 .env 中设置一个随机密钥，例如：python -c "import secrets; print(secrets.token_hex(32))"'
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
API_KEY = os.getenv("API_KEY", "").strip()
LYRICS_MODEL = os.getenv("LYRICS_MODEL", "glm-4-flash").strip()
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "").strip()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3").strip()
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "https://api.siliconflow.cn/v1/embeddings").strip()
RAG_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "documents_siliconflow_bge_m3").strip()
RAG_DISTANCE_THRESHOLD = float(os.getenv("RAG_DISTANCE_THRESHOLD", "1.10"))

# 原始上传文档只存服务器受控目录，文件名不直接参与路径拼接；可用环境变量迁移到独立数据盘。
DOCUMENT_STORAGE_DIR = Path(
    os.getenv("DOCUMENT_STORAGE_DIR", str(BACKEND_DIR / "data" / "documents"))
).expanduser()

# ===== 限流配置（core/ratelimit.py 使用，全部可用环境变量覆盖）=====
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

CHAT_RATE_PER_MINUTE = int(os.getenv("CHAT_RATE_PER_MINUTE", "10"))
CHAT_RATE_PER_DAY = int(os.getenv("CHAT_RATE_PER_DAY", "200"))
CAPABILITY_RATE_PER_MINUTE = int(os.getenv("CAPABILITY_RATE_PER_MINUTE", "5"))
LOGIN_RATE_PER_MINUTE = int(os.getenv("LOGIN_RATE_PER_MINUTE", "5"))  # 每 IP+邮箱
REGISTER_RATE_PER_MINUTE = int(os.getenv("REGISTER_RATE_PER_MINUTE", "5"))  # 每 IP
CODE_SEND_COOLDOWN_SECONDS = int(os.getenv("CODE_SEND_COOLDOWN_SECONDS", "60"))
CODE_SEND_PER_EMAIL_PER_DAY = int(os.getenv("CODE_SEND_PER_EMAIL_PER_DAY", "10"))
CODE_SEND_PER_IP_PER_DAY = int(os.getenv("CODE_SEND_PER_IP_PER_DAY", "20"))
UPLOAD_MAX_FILE_MB = int(os.getenv("UPLOAD_MAX_FILE_MB", "30"))
UPLOAD_DAILY_TOTAL_MB = int(os.getenv("UPLOAD_DAILY_TOTAL_MB", "100"))

# 全局请求体上限须大于上传单文件上限（30MB + multipart 编码开销）
BODY_MAX_MB = int(os.getenv("BODY_MAX_MB", "32"))

# 字段级上限（业务层）：1MB 的 body 过得了全局限制，但作为单条消息仍不合理
CHAT_MESSAGE_MAX_CHARS = int(os.getenv("CHAT_MESSAGE_MAX_CHARS", "20000"))
CHAT_HISTORY_MAX_ITEMS = int(os.getenv("CHAT_HISTORY_MAX_ITEMS", "200"))
CHAT_ATTACHMENTS_MAX_ITEMS = int(os.getenv("CHAT_ATTACHMENTS_MAX_ITEMS", "20"))
PROFILE_MAX_CHARS = int(os.getenv("PROFILE_MAX_CHARS", "5000"))

# ===== E3 持久化任务 Worker =====
JOB_LEASE_SECONDS = int(os.getenv("JOB_LEASE_SECONDS", "60"))
JOB_MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
JOB_POLL_INTERVAL_SECONDS = float(os.getenv("JOB_POLL_INTERVAL_SECONDS", "1"))
