# CLAUDE.md

- 用中文和我对话

## 启动方法

本地启动（已不再使用 Docker 或阿里云部署）。**前端和后端都要启动，缺一不可**。

### 后端（FastAPI，提供 /auth、/chat 等 API，负责发邮箱验证码）

```bash
source ~/.venv/bin/activate
cd ~/MultiNeiroCreator/backend
uvicorn main:app --port 8000
```

- 注意：`backend/venv` 是坏的（无 bin 目录），依赖装在 `~/.venv` 里，要用它。
- 前端 `vite.config.ts` 的 proxy 已把 `/api` 指向 `http://127.0.0.1:8000`。

### 前端（Vue + Vite）

```bash
cd ~/MultiNeiroCreator/frontend
pnpm dev
```

## 邮箱验证码

- 注册需要邮箱验证码，由后端 `/auth/send-code` 通过 SMTP 发送。
- **不能用 Gmail**：本地在国内网络环境，连不上 `smtp.gmail.com`（Google 全被墙）。
- 已改用 QQ 邮箱：`smtp.qq.com` 端口 `465`（SSL，代码里用 `use_tls=True`），配置在 `backend/.env`。
