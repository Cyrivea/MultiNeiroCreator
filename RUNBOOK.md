# RUNBOOK — MultiNeiroCreator 本地跑通清单

> 目标：以**最快跑通**为准，不追求功能完整和高标准。
> 你是第一次做 multi-agent 项目，这份清单按「照做就能起来」的顺序写。

---

## 0. 先认清项目现状（重要，别被名字骗了）

这个项目**规划很大、实际做完的很少**。`backend_architecture_plan.md` 里画了 15 层后端，
但大部分文件是 **0 字节空占位**。**当前真正能跑的只有一条主线**：

> 注册/登录 → 和 AI 助手 Neyria 单人对话（智谱 GLM-4-Flash）→ 可选上传文档做 RAG 问答 → 项目创建/自动保存

**还没实现、跑起来也没有的功能**（都是空文件，别期待）：
- ❌ 真正的「多 agent 编排 / workflow」— `services/workflow_service.py`、`workstation_service.py` 是空的
- ❌ 图像/视频/音频生成 — `workers/*.py`、`agents/tools/{image,video,music}_tools.py` 是空的
- ❌ jobs 异步任务队列、assets/tools/settings/search 等模块 — 空的
- ✅ 已实现的工具只有 3 个：计算器、当前时间、联网搜索(DuckDuckGo)

所以「multi-agent」目前是**名义上的**，实质是**单助手 + RAG + 工具调用**。先把这条主线跑通即可。

---

## 1. 技术栈速览

| 层 | 用了什么 | 说明 |
|---|---|---|
| 后端 | FastAPI + uvicorn | 入口 `backend/main.py`，端口 **8000** |
| 数据库 | SQLite（标准库直连，无 ORM） | 文件 `backend/data/conversations.db`，**首次启动自动建表**，无需手动初始化 |
| 向量库 | ChromaDB（本地持久化） | 目录 `backend/chroma_db/`，自动创建 |
| LLM | 智谱 GLM `glm-4-flash` |
| Embedding | Google Gemini `gemini-embedding-001` | 需 `EMBEDDING_API_KEY`，只有用 RAG 才需要 |
| 前端 | Vue3 + TS + Vite + Pinia + Element Plus | `pnpm dev`，`/api` 代理到 `:8000` |

**不需要**：Redis、独立数据库服务器、对象存储、Docker（本地直接跑）。

---



## 3. 常见坑速查

| 现象 | 原因 / 解决 |
|---|---|
| 聊天返回 503「未配置 API_KEY」 | `.env` 没填 `API_KEY` 或没在 `backend/` 目录启动（.env 读的是 `backend/.env`） |
| 上传文档报 `ImportError: google` | 没装 `google-genai`（待办 1） |
| 注册收不到验证码 | SMTP 没配好 / 用了 Gmail；见待办 5 方案 B、C |
| 前端请求 404 或跨域 | 后端没起 / 没在 8000 端口；前端代理写死了 `127.0.0.1:8000` |
| 联网搜索工具没反应 | `ddgs`(DuckDuckGo) 需要外网 |
| 一切正常但没有「多 agent/生图/生视频」 | 那些模块本来就是空文件，尚未实现（见第 0 节） |

---

## 4. 关键文件索引（改代码时看这里）

- 后端入口 / 路由注册：`backend/main.py`
- 配置 / 环境变量：`backend/core/config.py`
- 建表：`backend/core/database.py`、`backend/services/project_service.py`
- 对话编排（核心逻辑）：`backend/services/assistant_service.py`
- Agent 与工具定义：`backend/agents/neyria.py`、`backend/agents/tools/`
- RAG：`backend/services/rag/{embedding,vectorstore,retriever,parser,service}.py`
- 注册/登录：`backend/services/auth_service.py`
- 前端路由/页面：`frontend/src/router/index.ts`、`frontend/src/views/`
- 前端 API 封装：`frontend/src/serve/{auth,agent,project}.ts`
- 前端请求层/代理：`frontend/src/utils/request.ts`、`frontend/vite.config.ts`
