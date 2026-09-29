# Neyria

[![CI](https://github.com/Cyrivea/Neyria/actions/workflows/ci.yml/badge.svg)](https://github.com/Cyrivea/Neyria/actions/workflows/ci.yml)

Neyria 创作工具工作台：注册登录 + 流式聊天助手 + RAG 文档问答 + 可控生产工具 Block + 可编辑 Workflow 规划。

产品边界：普通用户只使用平台提供的工具区块和 Workflow，不接触 API Key、Base URL、后端系统 Prompt、真实上游模型名或代码执行接口。聊天助手可以调用这些 Block，用户也可以直接使用 Block，AI 生成的 Workflow 与用户手动编辑的 Workflow 使用同一份可编辑图结构。

> 完整的架构说明见 `architecture.md`；API/部署文档与量化指标仍在补充（见 `unsolved.md` H2/H3）。本 README 提供最小可复现指引。

第一条真实生产能力已经接通：`lyrics.generate` 使用后端托管的智谱文本模型。用户可以在歌词 Block 参数面板中填写主题、平台预设曲风/情绪/语言并生成 Markdown 歌词；Chat Assistant 也可以调用同一个 Capability Runtime。图片、视频、音频仍是前端原型，等待各自 Provider。


# 后续产品主线

项目不会先做一个只展示多 Agent 节点的画布，而是按下面顺序建设真正的生产闭环：

```text
平台托管模型和 Provider
  → 生产工具 Block
  → 订阅、额度和用量计量
  → 聊天助手调用 Block
  → 用户和 AI 共同编辑 Workflow
  → 生成结果保存为项目资产
```

第一批 Block 优先支持歌词生成、内容审核、视觉 Prompt 和分镜等文本生产能力；图片、视频、音频 Block 通过独立 Provider 接入。平台内部的模型、接口密钥和系统 Prompt 只由管理员维护，前端不暴露这些实现细节。


- **后端**：Python 3.12 / FastAPI / SQLite / Redis / ChromaDB，依赖管理 [uv](https://docs.astral.sh/uv/)
- **前端**：Vue 3 / TypeScript / Vite / Pinia，包管理 pnpm

## 快速启动（开发环境）

```bash
# 后端（需要 backend/.env，至少包含 SECRET_KEY；聊天用 API_KEY，RAG 使用 SiliconFlow 的 SILICONFLOW_API_KEY）
./dev.sh                 # 自动检查/拉起 Redis + 启动 uvicorn --reload

# 前端
cd frontend
pnpm install
pnpm dev
```

```env
# 聊天与歌词 Block：智谱（歌词模型可由后端 LYRICS_MODEL 控制）
API_KEY=...
LYRICS_MODEL=glm-4-flash
# RAG：硅基流动免费版 BAAI/bge-m3
SILICONFLOW_API_KEY=...
EMBEDDING_MODEL=BAAI/bge-m3
```


```bash
# 后端（backend/ 目录）
uv sync --all-groups     # 安装含 dev 组的全部依赖
uv run ruff check .      # lint
uv run mypy              # 类型检查（core/schemas/services/rag）
uv run pytest            # 当前后端 133 passed, 10 skipped

# 前端（frontend/ 目录）
pnpm lint                # ESLint
pnpm format:check        # Prettier
pnpm test                # Vitest（当前 31 个用例）
pnpm build               # vue-tsc + vite
```
