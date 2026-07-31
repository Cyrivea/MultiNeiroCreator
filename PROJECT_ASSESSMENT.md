# MultiNeiroCreator 项目全面评估与实习简历化改造方案

> 评估日期：2026-07-31
> 评估视角：资深全栈/AI 工程师的代码级 Review + 实习求职简历背书视角
> 目标读者：项目作者（准大二，目标岗位 = AI 全栈工程师 / AI 应用开发 / Agent 工程师）
> 评估方式：通读全部非空源码（后端 27 个 py ≈ 1900 行、前端 33 个源文件 ≈ 7300 行），逐行核实、给出文件:行号证据

---

## 0. 一句话结论

**这是一个"视觉与规划的完成度远高于工程与安全完成度"的单人原型。** happy path（注册登录 → 与 AI 助手 Neyria 流式对话 → 上传文档做 RAG 问答 → 项目自动保存）能跑通，目录分层意识和前端动效设计有亮点；但它当前**不能直接写进简历当核心项目**——存在会在面试第一轮被否掉的致命问题（生产服务器 root 密码进 git、`eval()` 远程代码执行、认证体系可被伪造），以及大量"名义存在、实际空占位"的功能。

**好消息**：它的骨架、命名、部分模块（后端 `services/rag/`、前端 `stores/loading.ts` 与 SSE 解析）质量不错，**拆分与补全的边界非常清晰**。按本文档的路线走 8~10 周，它完全可以成为一个能在实习面试里讲 40 分钟、经得起追问的高质量项目。

| 维度 | 后端 | 前端 |
|---|---|---|
| 架构设计 | 4/10 | 3/10 |
| 代码质量 | 4/10 | 5/10 |
| 安全性 / 类型安全 | 2/10（安全） | 6/10（类型） |
| 可扩展性 / 可维护性 | 3/10 | 3/10 |
| **综合** | **3.25/10** | **3.1/10** |

---

## 1. 项目现状盘点（先认清自己在哪）

### 1.1 "规划 vs 实现" 的巨大落差

`backend_architecture_plan.md` 规划了 15 层后端架构、57 个后端文件，但**其中 30 个是 0 字节空占位**（`models/*` 全 9 个、`workers/*` 全 3 个、`routers/` 6 个、`services/` 9 个、`repositories/` 4 个、`agents/tools/{base,image,video,music}` 4 个）。

真正实现的只有一条主线，约 1900 行：

```
注册/登录 → 与 AI 助手 Neyria 单人对话(智谱 GLM-4-Flash) → 可选上传文档做 RAG 问答 → 项目创建/自动保存
```

**"multi-agent" 目前是名义上的**：实际只有 1 个 agent、3 个工具（计算器、当前时间、联网搜索），无 agent 间通信、无编排、无 workflow。项目名承诺的"多模态创作（生图/生视频/生音频）"在后端**零实现**。

> 这不是贬低——原型阶段先画满骨架很正常。但**简历上必须诚实**：写"multi-agent 创作平台"会在面试被追问时当场穿帮，且诚信减分。当前应表述为"基于 RAG 与工具调用的 AI 助手应用"。

### 1.2 技术栈

| 层 | 技术 | 评价 |
|---|---|---|
| 后端 | FastAPI + uvicorn | 选型合理，主流 |
| 数据库 | SQLite（标准库直连，**无 ORM**） | 原型可接受，生产/简历需升级 |
| 向量库 | ChromaDB（本地持久化） | RAG 场景合理 |
| LLM | 智谱 GLM-4-Flash | 免费够用，但硬编码 |
| Embedding | Google Gemini `gemini-embedding-001` | 与 LLM 供应商割裂，配置分散 |
| 前端 | Vue3 + TS + Vite + Pinia + Element Plus | 选型主流；**Element Plus 引入 1MB 只为一个 toast，是净浪费** |

---

## 2. 全栈架构诊断

### 2.1 后端诊断

#### 架构：目录分了 6 层，实际生效 3 层半

- **越层严重**：`services/project_service.py`（297 行）一个文件同时干了 router 入参处理、service 业务、repository 裸 SQL、DDL 建表四件事，而对应的 `repositories/project_repo.py` **是 0 字节**——作者知道该放哪，只是没放。同目录下 `assistant_service.py` 却规矩地走了 repository，**同一层两种风格并存**，说明没有形成自我约定。
- **`models/` 整层空置 = 没有领域层**：数据在全栈以裸 `dict` 和 `sqlite3.Row` 传递，同一个 "Project 概念" 有 3 个互不同步的定义（SQL DDL、Pydantic schema、service 里手搓的 dict 字面量，且两处 dict 字段还不一致）。"分层"退化成了"分文件夹"。
- **上帝函数**：`stream_chat`（110 行）同时承担上下文组装、工具执行、流式输出、持久化。规划文档自己都要求拆成 `context_builder`/`tool_executor`/`chat_orchestrator`，但未动手。

#### 数据库：无 ORM、无索引、无外键、无正经迁移

- 建表语句分裂在两个文件两层（`core/database.py` 管 users/messages，`project_service.py` 管 projects）。
- **零索引**：所有高频查询（`WHERE user_id=? AND project_id ...`）都是全表扫描，数据量上万即退化。
- **零外键**、且从未 `PRAGMA foreign_keys=ON`：删用户不清理消息，`project_id` 可指向不存在的项目。
- **连接管理有泄漏风险**：9 处 repository 函数用 `conn = get_connection()` 但**没有 try/finally 或 with**，任何查询异常都留下未关闭连接。
- **无 WAL、无 timeout**：前端有周期性自动保存写入，并发写会撞 `database is locked`，且无重试、无日志。

#### 耦合度 / 可维护性 / 可扩展性核心痛点

1. **横向扩展直接不可用**：验证码存进程内存 `_codes` dict，`--workers 2` 就会"请先获取验证码"。
2. **纵向并发能力 ≈ 1**：`stream_chat` 在事件循环线程上**同步消费**流式响应（`assistant_service.py:289`），单个对话独占进程 3~10 秒；`/documents/reindex` 因串行 embedding 可独占 90 秒。作者其实知道 `to_thread`（用对了 2 处），只是用得不彻底。
3. **工具扩展成本高**：加一个工具要同步改 4 处（工具文件 + import + `tools_map` + `tools_schema`），漏改任一处静默失效。`base.py` 空置 = 没有注册机制。

### 2.2 前端诊断

#### 一个 3850 行的上帝组件承载一切

`WorkstationLayout.vue` **独占全前端 52.7% 的代码**，内部 36 个平铺 `ref` + 7 个组件实例外的模块级 `let`（重挂载定时炸弹）+ 73 个函数，扛着 **19 个可独立成模块的职责**（SSE 流式消费、File System Access 本地读写、自动保存、项目 CRUD、附件模型、4 个模态……）。

**讽刺的是拆分作者已经开始过**——`WorkstationHeader/Sidebar/Canvas/Footer/UtilityPanel.vue` 5 个子组件 + 整套 `y2k-theme.css` 设计令牌，就是拆分的遗迹，然后被放弃、变成 296 行死代码。

#### 状态管理错位

核心业务状态（项目、会话、附件）**0 行在 Pinia 里**，全散落在组件里；跨路由靠 **localStorage 传参**（本该是 store 的职责）。2 个 store 都只管 UI，其中 `loading.ts` 是全项目质量最高的文件。

#### 已核实的前端真实 Bug（会被用户/面试官当场看到）

- 🔴 **流式输出实际只有 1Hz 刷新率**：`assistantMessage.content += event.content` 直接改原始对象、绕过 Vue Proxy，打字机效果其实靠"每秒计时器触发重渲染"救场。（`WorkstationLayout.vue:1795`）
- 🔴 **输错密码会整页刷新**：后端登录失败返回 401，被 axios 拦截器当成"未授权"→ `localStorage.clear()` + `location.href='/login'`，表单和错误提示全被冲掉。（`utils/request.ts:20-22`）
- 🔴 **分享 URL / 刷新导致项目身份错配**：`?project=5` 只覆盖了 id，name/path/saveMode 还是上一个项目的值。（`WorkstationLayout.vue:1852-1858`）
- 🔴 **SSE `JSON.parse` 无 try/catch**：后端吐一行坏 JSON，整个流中断、已收内容丢失。（`serve/agent.ts:138,157`）

#### 工程化几乎裸奔

**0 个 ESLint/Prettier、0 个测试、0 个环境变量（`import.meta.env` 全库 0 引用）、0 个 `defineProps`**、README 还是 Vite 模板原文、无分包配置（Element Plus 全量进主 chunk）。

**类型安全是前端唯一亮点**（6/10）：`any` 仅 15 次且 10 次是无害占位、`@ts-ignore` 0 次、`strict` + 4 个额外严格开关、判别联合/`Record<Union,V>` 穷尽映射/`Exclude<>` 都用得地道。

---

## 3. 未完成功能盘点（对标"生产级实习项目"标准）

### 3.1 🔴 必须立刻处理的安全 / 必崩问题（P0）

| # | 问题 | 位置 | 后果 |
|---|---|---|---|
| 1 | **生产服务器 root 明文密码提交进 git 历史** | `start.sh:12-15` | 公网 IP+root+密码三件套泄露，任何拿到仓库的人可登服务器；面试官看 git log 即见 |
| 2 | **`eval()` 远程代码执行** | `calculator.py:8` | 任意注册用户经 `/chat` 提示注入可执行任意代码、读走 `.env` 全部密钥 |
| 3 | **SECRET_KEY 硬编码兜底值且 .env 未配** | `config.py:18` | 任何人用源码公开字符串即可伪造任意用户 JWT，**认证等于零** |
| 4 | **project_path 任意路径写入** | `project_service.py:233-243` | 客户端可传 `/root/.ssh` 等任意路径，Docker 内 root 运行 → 可覆盖系统文件 |
| 5 | **必崩 Bug：参数个数错误** | `project_service.py:207` | `/projects/auto-save/backup` 每次调用必 500，且崩在"磁盘已写、DB 未写"之间造成数据不一致 |
| 6 | **必崩 Bug：引用不存在的文件** | `routers/workstation.py:8-25` | `index.html`/`logo.png` 不存在，根路由与 favicon 必 500 |

### 3.2 缺失的核心功能

- ❌ **真正的多 agent / workflow 编排**（`workflow_service.py`、`workstation_service.py` 空）
- ❌ **异步任务队列 jobs**（`workers/*` 空）——任何重任务无处安放
- ❌ **多模态生成**（生图/生视频/生音频，全空）
- ❌ **工具循环**：当前只取 `tool_calls[0]`、单轮单工具，模型无法"搜索→看结果→再搜索"
- ❌ **登出功能**（`stores/user.ts` 的 `logout` 全项目从未被调用）
- ❌ **模型切换**（前端 UI 有"Auto"占位，后端模型名硬编码 3 处）

### 3.3 缺失的工程化能力

- ❌ **日志**：后端全仓 0 条 logging，所有故障不可观测（比任何单个 bug 都严重）
- ❌ **测试**：前后端各 0 个测试文件
- ❌ **静态检查**：无 mypy/ruff/ESLint/Prettier（`project_service.py:207` 的 TypeError 是 mypy 秒抓的）
- ❌ **CI/CD**：无 `.github`、无 pre-commit hook
- ❌ **依赖锁定**：后端 19 个依赖仅 1 个锁版本
- ❌ **环境变量分离**：前端无 `.env`，API 地址硬编码
- ❌ **健康检查**：无 `/health` 端点

### 3.4 缺失的安全防护机制

无速率限制（`/chat` 可无限刷付费 token）、无请求体大小限制（上传可 OOM）、验证码用非密码学安全的 `random` 且无爆破防护、密码零强度校验（空密码可注册）、客户端可伪造对话历史、CORS `*`、`/docs` 生产未关闭、token 存明文 localStorage 无过期本地校验。

### 3.5 缺失的性能优化点

后端事件循环阻塞（并发≈1）、embedding 串行无批处理、RAG 无 rerank/无相似度阈值过滤（任何问题都强行召回 3 段可能无关的文档）、无 token 截断（会话越长越贵直至崩）；前端无分包、Element Plus 1MB 冗余、流式 1Hz、消息 blob URL 内存泄漏。

### 3.6 缺失的文档建设

前端 README 是模板原文、无前端架构文档、无 API 文档（OpenAPI 未整理）、无部署文档（`start.sh` 是混了三种语法的备忘录）、无 ADR（架构决策记录）。

### 3.7 简历背书所需的核心指标体系（当前几乎为零）

一个能背书的项目需要**可量化的数字**，当前一个都没有。目标建立：
- **性能指标**：接口 P95 延迟、并发 QPS、首 token 延迟、RAG 召回准确率、embedding 吞吐
- **质量指标**：测试覆盖率、类型覆盖率、Lighthouse 分数、包体积
- **规模指标**：支持并发用户数、文档索引量、日均对话数
- **工程指标**：CI 通过率、构建时长、镜像体积

---

## 4. 分阶段落地执行规划（Step-by-Step）

> 总时长约 8~10 周，与暑期到开学的节奏匹配。每个阶段结束都应有一个**可 demo、可写进简历的交付物**，并 git 打 tag。原则：**先止血（安全）→ 再站稳（工程化）→ 后长肌肉（功能与性能）→ 最后包装（指标与文档）**。

### 阶段 0：安全止血（第 1~2 天，最高优先级，必须先做）

| 任务 | 技术方案 / 工具 | 交付物 |
|---|---|---|
| 改服务器 root 密码、禁密码登录改密钥、查 `/var/log/auth.log` | `passwd` + `sshd_config` `PasswordAuthentication no` + SSH key | 服务器加固记录 |
| 清除 git 历史里的密码 | `git filter-repo`（或 BFG），`start.sh` 加入 `.gitignore` | 干净的 git 历史 |
| 删 `eval()` | `ast.literal_eval` + 运算符白名单，或 `simpleeval` 库 | 安全的计算器工具 |
| SECRET_KEY 强制从环境读 | `os.environ["SECRET_KEY"]`，缺失则拒绝启动 | 启动时校验 |
| project_path 白名单 | `Path(p).resolve().is_relative_to(WORKSPACE_DIR)` | 路径校验函数 |
| 修 `project_service.py:207` / `workstation.py` 死路由 | 补参数、改关键字传参 / 删死路由 | 主线不再 500 |

**所需能力**：Linux 基础运维、git 历史操作、Python 安全编码基础。
**产出**：一次"安全审计与修复"commit，本身就是简历上"安全意识"的证据。

### 阶段 1：工程化地基（第 1~2 周）

| 任务 | 技术方案 / 工具 | 交付物 |
|---|---|---|
| 后端结构化日志 + 全局异常处理器 | `logging` + JSON formatter + request_id 中间件；填充 `core/exceptions.py` + `@app.exception_handler` | 可观测的后端 |
| 后端静态检查 | `ruff`（lint+format）+ `mypy` + `pyproject.toml` | `make lint` 通过 |
| 前端静态检查 | `eslint-plugin-vue` + `@typescript-eslint` + Prettier + lint-staged + husky | `pnpm lint` 通过 |
| 依赖锁定 | 后端 `pip freeze` 锁全部版本 / 迁移到 `uv` 或 `poetry`；前端已用 pnpm lock ✅ | 可复现构建 |
| 环境变量分离 | 后端配置集中进 `core/config.py`；前端 `.env.development`/`.env.production` + `import.meta.env` | 换环境不改代码 |
| CI | GitHub Actions：lint + type-check + test + build | 绿色徽章 |
| 前端 4 个 P0 bug 修复 | 见 2.2（响应式代理累加、401 白名单、项目身份、SSE try/catch） | 用户可感知的体验修复 |

**所需能力**：Python 工程化（ruff/mypy）、前端工程化（ESLint/Prettier/husky）、GitHub Actions YAML、结构化日志设计。

### 阶段 2：架构还债（第 3~4 周）

| 任务 | 技术方案 / 工具 | 交付物 |
|---|---|---|
| 拆 `WorkstationLayout.vue`（3850→150 行） | 按"纯函数→composable→组件"顺序：`utils/attachment.ts`、`composables/useAgentChat.ts`、`useProjectSession.ts`、拆 `AssistantPanel.vue` 等 | 可维护的前端 |
| 前端业务状态进 Pinia | 新建 `stores/project.ts` + `stores/chat.ts`，删 localStorage 传参 | 单一数据源 |
| 后端补领域层 | `models/` 用 dataclass/Pydantic 定义 User/Project/Message/Document；SQL 迁进 `repositories/project_repo.py` | 真正的分层 |
| SQLite 加固 | `connect(timeout=30)` + `PRAGMA journal_mode=WAL` + `with closing(...)` + 加索引 | 并发不锁死 |
| 拆 `stream_chat` | `context_builder`/`tool_executor`/`chat_orchestrator`；工具改真 `while` 循环 + 多工具 + 异常隔离 | 可扩展的对话编排 |
| 解决事件循环阻塞 | 智谱异步客户端，或消费循环放线程 + `asyncio.Queue` | 并发能力 >1 |

**所需能力**：Vue composable 设计、Pinia、Python 分层架构、asyncio、SQLite 并发模型。

### 阶段 3：功能补全 + AI 深化（第 5~7 周，简历亮点核心）

> 这是最能体现"AI 工程师"定位的阶段。不要贪多做生图生视频，**把 RAG 和 Agent 做深做对，比铺一堆半成品更有说服力**。

| 任务 | 技术方案 / 工具 | 交付物 |
|---|---|---|
| RAG 质量升级 | embedding 真批处理 + task_type 区分 query/document；检索加**相似度阈值过滤** + **rerank**（bge-reranker 或 Cohere rerank）；chunk 改语义切分（按段落/标题） | 可量化召回率提升 |
| 工具注册机制 | 实现 `agents/tools/base.py` 注册装饰器，`tools_schema` 改 `convert_to_openai_tool` 自动生成 | 加工具只改 1 处 |
| 真·多 agent / workflow（**可选，量力**） | 引入 LangGraph 编排：规划 agent + 执行 agent + 工具，做一个"研究→总结"的最小 workflow | 名副其实的 multi-agent |
| 异步任务队列 | 先用 FastAPI `BackgroundTasks` 起步，进阶用 Celery/RQ + Redis；填充 `workers/` | 长任务不阻塞 |
| 对话历史改从 DB 读 + token 截断 | 服务端不信任客户端 history；`tiktoken` 计数 + 滑窗 | 安全且不超上下文 |
| 登出 + token 过期本地校验 | 调用 `userStore.logout()`；路由守卫解析 JWT `exp` | 完整鉴权闭环 |

**所需能力**：RAG 进阶（rerank、chunk 策略、评估）、LangGraph/Agent 编排、Celery/Redis、tiktoken、JWT 生命周期。

### 阶段 4：性能优化 + 指标体系 + 文档包装（第 8~10 周）

| 任务 | 技术方案 / 工具 | 交付物 |
|---|---|---|
| 前端性能 | 卸 Element Plus 改手写 toast、vite `manualChunks` 分包、图片懒加载 | Lighthouse 分数、包体积对比数据 |
| 后端性能压测 | `locust` 或 `wrk` 压测，记录优化前后 P95/QPS | **简历用的性能数字** |
| RAG 评估 | 构造评估集，用 `ragas` 或自建指标测召回准确率 | **RAG 准确率数字** |
| 补测试 | 后端先测纯函数（chunk_text、security、upsert）；前端 Vitest 测 attachment/datetime 纯函数；目标覆盖率 60%+ | **测试覆盖率数字** |
| 文档 | 前端 README + 架构图 + API 文档整理 + 部署文档 + 3~5 篇 ADR | 完整文档 |
| Docker 化部署 | 修 Dockerfile（加 `USER`、多阶段、`.dockerignore` 补全）+ docker-compose + nginx 反代 | 一键部署 |

**所需能力**：性能压测工具、RAG 评估、单元测试、技术写作、Docker/nginx。

---

## 5. 同步学习路径（边做边学）

> 原则：**每个学习点都绑定一个当周的开发任务，学完立刻用上**。不追求系统啃完一本书，追求"够用即用、用中深化"。作为准大二，把这套走完你的实战能力会明显超过同届。

| 阶段 | 配套学习点 | 推荐资源 / 关键词 | 学习产出 |
|---|---|---|---|
| **阶段 0-1** | ① Web 安全基础（OWASP Top 10：注入、越权、密钥管理）② git 高级操作（filter-repo、history 重写）③ Python 工程化（ruff/mypy/pyproject）④ 结构化日志与可观测性⑤ GitHub Actions | OWASP Top 10 官方、`ruff`/`mypy` 文档、Real Python "logging" | 能独立做一次安全审计 |
| **阶段 2** | ① 分层架构与依赖方向（Repository/Service 模式）② asyncio 事件循环模型（为什么阻塞、to_thread/gather）③ Vue Composition API 深入（composable 抽象、响应式原理）④ Pinia 状态设计⑤ SQLite 并发模型（WAL、锁） | 《Architecture Patterns with Python》、Vue 官方 Composition API、FastAPI 官方 async 章节 | 理解"为什么这样分层" |
| **阶段 3** | ① RAG 进阶（chunk 策略、embedding task_type、rerank、hybrid search）② Agent 编排（ReAct、工具调用循环、LangGraph）③ 消息队列与异步任务（Celery/Redis/RQ）④ LLM 上下文工程（token 管理、prompt 分层）⑤ JWT 生命周期与刷新机制 | LangChain/LangGraph 官方、`ragas` 文档、智谱/Anthropic 工具调用文档、《Designing Data-Intensive Applications》选读 | **这是 AI 工程师的核心竞争力** |
| **阶段 4** | ① 性能压测（locust/wrk、P95/P99 概念）② RAG 评估方法论③ 单元测试与 TDD（pytest/Vitest、fixture、mock）④ 前端性能（bundle 分析、code split、Lighthouse）⑤ Docker 多阶段构建与 nginx 反代⑥ 技术写作（README/ADR） | pytest 官方、Vitest 官方、`ragas`、web.dev performance、Docker 官方 best practices | 能把成果量化并讲清楚 |

### 学习方式建议

1. **先做后学**：遇到任务先查最小可用方案跑通，再回头补原理。原理不懂就问 AI（比如让我解释"为什么同步调用会阻塞事件循环"）。
2. **每周一篇总结**：把当周踩的坑、学的原理写成短博客/笔记。这些笔记本身是面试的谈资，也是"持续学习"的证据。
3. **AI 工程师的护城河在深度不在广度**：把 RAG 的 rerank、chunk 策略、评估这些做到能画图讲清楚、有数据支撑，比会调 10 个 API 更打动面试官。

---

## 6. 简历表述建议（诚实且有力）

改造完成后，可以这样写（每条都要有真实数字支撑）：

- ✅ "独立设计并实现基于 **FastAPI + Vue3 + ChromaDB** 的 AI 助手应用，支持流式对话、工具调用与 **RAG 文档问答**"
- ✅ "通过 **embedding 批处理 + rerank + 相似度阈值过滤**，将 RAG 召回准确率从 X% 提升至 Y%"
- ✅ "解决事件循环阻塞问题，接口并发能力从 1 提升至 N，P95 延迟从 Xs 降至 Ys"（压测数据）
- ✅ "建立完整工程化体系：ruff/mypy/ESLint 静态检查 + Vitest/pytest 测试（覆盖率 60%+）+ GitHub Actions CI"
- ✅ "重构 3850 行上帝组件为分层的 composable + Pinia 架构"
- ❌ 不要写：多模态生成、多 agent 平台（除非真做到了 LangGraph 那步）

---

## 附录：本文档的两条最重要建议

1. **今天就做阶段 0 的第 1 件事**——改服务器密码、清 git 历史。这不是代码问题，是真实的安全事故，且优先级高于一切。
2. **不要贪功能广度，要做深度**。把"注册登录 + 流式对话 + RAG"这条主线打磨到生产级（有日志、有测试、有指标、有安全防护、代码分层干净），远胜过铺十个半成品模块。一个讲得清、经得起追问、有数据的小项目，就是好的简历项目。
