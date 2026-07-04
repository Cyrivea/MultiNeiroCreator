from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import os, json, tempfile, sqlite3, asyncio
from dotenv import load_dotenv
from zhipuai import ZhipuAI
from langchain_core.tools import tool
from fastapi.middleware.cors import CORSMiddleware
from rag import add_document, search
from datetime import datetime, timedelta
import pytz
from fastapi.responses import StreamingResponse, FileResponse
from ddgs import DDGS
import bcrypt
from jose import JWTError, jwt
import aiosmtplib
from email.mime.text import MIMEText
import random
import string

load_dotenv()

DB_FILE = "data/conversations.db"
MAIL_USER = os.getenv("MAIL_USER", "")
MAIL_PASS = os.getenv("MAIL_PASS", "")
MAIL_HOST = os.getenv("MAIL_HOST", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))

# 内存存储验证码 {email: {code, expire}}
import time
_codes: dict = {}
SECRET_KEY = os.getenv("SECRET_KEY", "multineirocreator-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

bearer_scheme = HTTPBearer()

# 直接用原生 bcrypt（passlib 1.7.4 与 bcrypt 4.x 不兼容，hash 时会因 72 字节探测抛 ValueError）
def hash_password(password: str) -> str:
    # bcrypt 只取前 72 字节，超长需手动截断，否则 bcrypt 4.x 会报错
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    pw = password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            profile TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def create_token(user_id: int, username: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "username": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": int(payload.get("sub")), "username": payload.get("username")}
    except JWTError:
        raise HTTPException(status_code=401, detail="token无效或已过期")

def load_profile(user_id: int) -> str:
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute("SELECT profile FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return row[0] if row else ""

def save_profile(user_id: int, profile: str):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE users SET profile=? WHERE id=?", (profile, user_id))
    conn.commit()
    conn.close()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = ZhipuAI(api_key=os.getenv("API_KEY"))

# 静态文件
@app.get("/")
def index(): return FileResponse("index.html")
@app.get("/logo.png")
def logo(): return FileResponse("logo.png")
@app.get("/CascadiaMono.ttf")
def font(): return FileResponse("CascadiaMono.ttf")
@app.get("/favicon.ico")
async def favicon(): return FileResponse("logo.png")

# 注册登录
class AuthRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/send-code")
async def send_code(req: AuthRequest):
    email = req.username
    if "@" not in email:
        raise HTTPException(status_code=400, detail="请输入有效的邮箱地址")
    
    code = "".join(random.choices(string.digits, k=6))
    _codes[email] = {"code": code, "expire": time.time() + 300}
    
    msg = MIMEText(f"""
    <div style="font-family:sans-serif;padding:20px;">
        <h2>MultiNeiroCreator 验证码</h2>
        <p>您的验证码为：</p>
        <h1 style="color:#8b5cf6;letter-spacing:8px">{code}</h1>
        <p style="color:#999">验证码5分钟内有效，请勿泄露给他人。</p>
    </div>
    """, "html", "utf-8")
    msg["Subject"] = "MultiNeiroCreator 注册验证码"
    msg["From"] = MAIL_USER
    msg["To"] = email
    
    try:
        await aiosmtplib.send(
            msg,
            hostname=MAIL_HOST,
            port=MAIL_PORT,
            username=MAIL_USER,
            password=MAIL_PASS,
            use_tls=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"邮件发送失败: {str(e)}")
    
    return {"status": "ok", "message": "验证码已发送"}

@app.post("/auth/register")
def register(req: AuthRequest, code: str = ""):
    email = req.username
    # 验证码校验
    record = _codes.get(email)
    if not record:
        raise HTTPException(status_code=400, detail="请先获取验证码")
    if time.time() > record["expire"]:
        raise HTTPException(status_code=400, detail="验证码已过期")
    if record["code"] != code:
        raise HTTPException(status_code=400, detail="验证码错误")
    
    conn = sqlite3.connect(DB_FILE)
    try:
        password_hash = hash_password(req.password)
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (email, password_hash))
        conn.commit()
        row = conn.execute("SELECT id FROM users WHERE username=?", (email,)).fetchone()
        token = create_token(row[0], email)
        del _codes[email]
        return {"token": token, "username": email}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="该邮箱已注册")
    finally:
        conn.close()

@app.post("/auth/login")
def login(req: AuthRequest):
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute("SELECT id, password_hash FROM users WHERE username=?", (req.username,)).fetchone()
    conn.close()
    if not row or not verify_password(req.password, row[1]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(row[0], req.username)
    return {"token": token, "username": req.username}

# 工具
@tool
def calculate(expression: str) -> str:
    """计算数学表达式"""
    try:
        return str(eval(expression))
    except:
        return "计算失败"

@tool
def search_web(query: str) -> str:
    """搜索网络获取实时信息，适合查询新闻、天气、最新事件等"""
    news_keywords = ['新闻', '动态', '最新', '今天', '事件', '发生', '价格',
                     '天气', '股价', '近况', '怎么样', '情况', '破产', '裁员',
                     '融资', '倒闭', '收购', '上市']
    is_news = any(kw in query for kw in news_keywords)
    try:
        with DDGS(timeout=5) as ddgs:
            if is_news:
                results = list(ddgs.news(query, max_results=5, timelimit='w'))
            else:
                results = list(ddgs.text(query, max_results=5, timelimit='m'))
            if results:
                return "\n".join([f"{r['title']}: {r['body']}" for r in results])
    except Exception as e:
        if is_news:
            try:
                with DDGS(timeout=5) as ddgs:
                    results = list(ddgs.text(f"{query} 最新新闻", max_results=5, timelimit='d'))
                if results:
                    return "\n".join([f"{r['title']}: {r['body']}" for r in results])
            except:
                pass
        return "搜索失败，网络连接超时，请稍后重试。"
    return "没有找到相关结果"

@tool
def get_current_time() -> str:
    """获取当前最新的北京时间以及全球主要城市的精准当地时间"""
    try:
        regions = {
            "中国 (北京)": "Asia/Shanghai",
            "美国 (纽约)": "America/New_York",
            "英国 (伦敦)": "Europe/London",
            "日本 (东京)": "Asia/Tokyo",
            "德国 (柏林)": "Europe/Berlin"
        }
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        result_lines = ["当前全球主要时刻对照："]
        for name, tz_str in regions.items():
            tz = pytz.timezone(tz_str)
            now = datetime.now(tz)
            time_str = now.strftime(f"%Y-%m-%d %H:%M:%S {weekdays[now.weekday()]}")
            result_lines.append(f"- **{name}**：{time_str}")
        return "\n".join(result_lines)
    except Exception as e:
        return f"获取全球时间失败: {str(e)}"

tools_schema = [
    {"type": "function", "function": {"name": "calculate", "description": "计算数学表达式", "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}},
    {"type": "function", "function": {"name": "get_current_time", "description": "获取当前最新的北京时间，当用户询问时间、日期或今天星期几时调用。", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "search_web", "description": "搜索网络获取实时信息，适合查询新闻、天气、最新事件等", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词"}}, "required": ["query"]}}}
]
tools_map = {"calculate": calculate, "get_current_time": get_current_time, "search_web": search_web}

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []

@app.post("/chat")
async def chat(req: ChatRequest, user=Depends(verify_token)):
    try:
        docs = await asyncio.to_thread(search, req.message, n_results=3)
        context = "\n".join(docs) if docs else ""
    except:
        context = ""

    profile = load_profile(user["id"])
    profile_section = f"\n用户信息：\n{profile}" if profile else ""

    system_prompt = f"""你是MultiNeiroCreator，用户的私人AI助手，说话像claude一样简洁明了，不要有情绪。{profile_section}

工具使用规则：
- 涉及实时信息、新闻、天气、最新事件时，必须调用search_web工具
- 涉及数学计算时，调用calculate工具
- 用户追问或质疑某个事实时，必须重新调用search_web验证，不能依赖上下文记忆
- 如果搜索结果包含非中文内容，回答时自动翻译成中文
"""
    if context:
        system_prompt += f"\n\n参考以下资料回答问题：\n{context}"
        system_prompt += "\n- 格式要求：请务必使用 Markdown 格式输出。"

    messages = [{"role": "system", "content": system_prompt}]
    messages += req.history
    messages.append({"role": "user", "content": req.message})

    async def stream_generator():
        response = client.chat.completions.create(model="glm-4-flash", messages=messages, tools=tools_schema)
        msg = response.choices[0].message
        func_name = None

        if msg.tool_calls:
            tool_call = msg.tool_calls[0]
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            yield f"data: {json.dumps({'type': 'tool', 'tool_name': func_name}, ensure_ascii=False)}\n\n"
            result = tools_map[func_name].invoke(func_args)
            messages.append({"role": "assistant", "tool_calls": [{"id": tool_call.id, "type": "function", "function": {"name": func_name, "arguments": tool_call.function.arguments}}]})
            messages.append({"role": "tool", "content": result, "tool_call_id": tool_call.id})
            final_stream = await asyncio.to_thread(client.chat.completions.create, model="glm-4-flash", messages=messages, stream=True)
        else:
            final_stream = [{"choices": [{"delta": {"content": msg.content}}]}]

        reply = ""
        for chunk in final_stream:
            if isinstance(chunk, dict):
                content = chunk["choices"][0]["delta"].get("content", "")
            else:
                delta = chunk.choices[0].delta
                content = delta.content if hasattr(delta, 'content') and delta.content else ""
            if content:
                reply += content
                yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"

        messages.append({"role": "assistant", "content": reply})
        clean_history = []
        for m in messages:
            if m.get("role") in ["user", "assistant"] and m.get("content"):
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    continue
                clean_history.append({"role": m["role"], "content": m["content"]})

        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)", (user["id"], "user", req.message))
        conn.execute("INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)", (user["id"], "assistant", reply))
        conn.commit()
        conn.close()
        yield f"data: {json.dumps({'type': 'done', 'history': clean_history, 'tool_used': func_name}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

class ProfileRequest(BaseModel):
    profile: str

@app.post("/profile")
def set_profile(req: ProfileRequest, user=Depends(verify_token)):
    save_profile(user["id"], req.profile)
    return {"status": "success", "message": "个人信息已更新"}

@app.get("/profile")
def get_profile(user=Depends(verify_token)):
    return {"profile": load_profile(user["id"])}

@app.get("/history")
async def get_history(user=Depends(verify_token)):
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT role, content FROM messages WHERE user_id=? ORDER BY id", (user["id"],)).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

@app.delete("/history")
async def clear_history(user=Depends(verify_token)):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM messages WHERE user_id=?", (user["id"],))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), user=Depends(verify_token)):
    try:
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        chunks_count = await asyncio.to_thread(add_document, tmp_path, file.filename)
        os.unlink(tmp_path)
        return {"status": "success", "message": f"成功导入文档: {file.filename}（共分切成 {chunks_count} 块）"}
    except Exception as e:
        return {"status": "error", "message": f"导入失败: {str(e)}"}
