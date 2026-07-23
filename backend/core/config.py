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

SECRET_KEY = os.getenv("SECRET_KEY", "multineirocreator-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
API_KEY = os.getenv("API_KEY", "").strip()
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "").strip()
