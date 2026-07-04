# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

MultiNeiroCreator — a multi-user AI creation platform, evolved from the earlier single-user "Reviagent" assistant. Two parts:

- **`backend/`** — FastAPI backend (entrypoint `main.py`). JWT auth, SQLite persistence, per-user isolation, RAG over ChromaDB, SSE chat streaming. Runs on Zhipu GLM-4-flash via the `zhipuai` SDK. Containerized (Docker) and also deployable behind Nginx + Systemd on Aliyun (47.79.85.117).
- **`frontend/`** — Vue 3 + Vite + TypeScript + Element Plus SPA. Landing page, login/register (email verification code), and a `workstation` view that is still a placeholder. The product vision (see `Home.vue`) is four collaborating AI agents: audio generation, lyric alignment, PV production, image creation — **none of the creation modules are implemented yet**.

> The backend still ships a legacy single-file `index.html` (from the Reviagent era) served at `/`. The real UI is now the Vue app in `frontend/`. The `index.html` is kept because `main.py`'s `/` route still references it; treat it as legacy.

## Commands

### Backend (`backend/`)

```bash
# Local syntax check before every commit (the project's lint gate)
python3 -m py_compile main.py rag.py && echo "OK"

# Run locally (dev)
uvicorn main:app --reload --port 8000

# Run as production does (Docker)
docker compose up -d --build
```

There is no test suite. `python3 -m py_compile` is the only pre-push check.

### Frontend (`frontend/`)

```bash
pnpm install      # or npm install
pnpm dev          # vite dev server; proxies /api -> 47.79.85.117 (see vite.config.ts)
pnpm build        # vue-tsc + vite build
```

### Deploy workflow (see `备忘录.md`)

Local: `py_compile` → `git add . && git commit && git push`.
Server: `cd ~/Reviagent && git pull && docker compose build --no-cache && docker compose up -d`.
(The server directory is still named `~/Reviagent`; the docker-compose service is `multineirocreator`.)

## Architecture

### Backend — `main.py` (all HTTP endpoints + the agent loop)

- **Auth** (`/auth/*`): JWT (`python-jose`, HS256, 30-day expiry) + bcrypt (`passlib`). Registration is gated by an email verification code sent via `aiosmtplib` (`/auth/send-code`); codes live in an in-memory dict `_codes` with a 5-min TTL. `verify_token` is a FastAPI dependency (`HTTPBearer`) injected into every protected route.
- **Persistence** — SQLite at `data/conversations.db`, `init_db()` on startup. Two tables: `users` (id, username, password_hash, profile, created_at) and `messages` (id, user_id, role, content, created_at). Everything is keyed by `user_id`, so profiles and chat history are per-user isolated (this closes the old global-profile gap).
- **`/chat`** (POST, auth): the core flow. Runs RAG `search()` for context, builds a system prompt (persona + tool rules + optional per-user profile + optional RAG context), then does a **single** GLM call to detect a tool call. If a tool is requested it executes one tool, appends the result, and re-calls GLM with `stream=True`; otherwise it streams `msg.content` directly. Responds as SSE (`text/event-stream`) with event types `tool`, `content`, `done`. Persists the user + assistant messages to SQLite. The `done` event returns a cleaned `history` array (assistant tool-call messages stripped) the frontend can resend.
- **`/profile`** (GET/POST, auth): per-user profile stored in the `users.profile` column, injected into the system prompt.
- **`/history`** (GET/DELETE, auth): fetch or clear the calling user's message history from SQLite.
- **`/upload`** (POST, auth): saves the file to a tempfile, calls `rag.add_document`, unlinks the temp.
- **`/`, `/logo.png`, `/CascadiaMono.ttf`, `/favicon.ico`**: serve legacy frontend assets via `FileResponse`.
- **CORS** is wide open (`allow_origins=["*"]`) so the Vue dev server can call it.

### Backend — `rag.py` (RAG over ChromaDB)

`PersistentClient(path="./chroma_db")`, collection `documents`. Embeddings via Zhipu `embedding-3`. `add_document` reads pdf/docx/txt/md, chunks at 500 chars, batch-embeds (one API call for all chunks to avoid rate limits), and stores with `source` filename metadata. `search` is guarded to return `[]` when the collection is empty.

### Backend — Tools (manual agent framework)

Tools are LangChain `@tool` functions (`calculate`, `search_web`, `get_current_time`) but GLM is driven by the hand-written `tools_schema` list and dispatched through `tools_map`. **Adding a tool requires editing three places in `main.py`**: the `@tool` function, an entry in `tools_schema`, and an entry in `tools_map`. The loop only ever executes the first tool call (`msg.tool_calls[0]`) and does not loop for multi-step tool use.

`search_web` uses `ddgs` (DuckDuckGo); it keyword-classifies queries as news vs. text and has a timeout fallback chain (news → text → failure message).

### Frontend — `frontend/src/`

- **`router/index.ts`** — routes `/` (Home), `/login`, `/workstation` (`meta.requiresAuth`). A `beforeEach` guard redirects to `/login` when no token, and away from `/login` to `/workstation` when already logged in.
- **`utils/request.ts`** — axios instance, `baseURL: '/api'`, injects `Authorization: Bearer <token>`, clears storage + redirects to `/login` on 401.
- **`serve/auth.ts`** — `login`, `sendCode`, `register` API calls.
- **`stores/user.ts`** — Pinia store; token + username persisted to `localStorage` (`TOKEN_KEY`, `USERNAME_KEY` from `constants/`).
- **`views/`** — `home/Home.vue` (landing page + canvas particle background), `login/Login.vue` (login/register tabs, 60s code cooldown), `workstation/Workstation.vue` (**placeholder, "待开发"**).
- **`vite.config.ts`** — auto-imports Vue/Router/Pinia + Element Plus; dev server proxies `/api` → `http://47.79.85.117`.

## Conventions & gotchas

- Backend API key is read from `backend/.env` as `API_KEY` (`load_dotenv()` → `ZhipuAI(api_key=...)`). Email creds (`MAIL_USER/PASS/HOST/PORT`) and `SECRET_KEY` are also env-driven. `.env`, `user_profile.json`, `chroma_db/`, `data/`, and `nginx_reviagent.conf` are git-ignored.
- **Frontend talks to the backend only through the `/api` proxy** — the dev proxy points at the production server (`47.79.85.117`), not localhost. To develop against a local backend, change the `proxy.target` in `vite.config.ts`.
- Legacy artifacts kept for compatibility, not active: `backend/index.html` (old single-file UI, still served at `/`), `backend/nginx_reviagent.conf` (only reverse-proxies `/chat` and `/upload`, predates the new auth/history routes).
- **Security notes (developer TODO):** `SECRET_KEY` and DB `user_profile.json` handling should be reviewed; `start.sh` contains server credentials in a comment and should be scrubbed / kept out of git; the Nginx block should be updated to proxy all API routes and deny `.env`.
