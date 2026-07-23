# MultiNeiroCreator 后端架构规划

## 1. 总原则

- 后端采用：**单体应用 + 模块化拆分**
- 不继续把所有功能堆进 `backend/main.py`
- `main.py` 只负责：
  - 创建 `FastAPI app`
  - 注册路由
  - 加载配置
  - 挂载中间件
  - 启动服务
- 业务逻辑拆到独立模块里，后续新增按钮、创作工具、项目管理、AI 助手、生成任务时，直接往模块里扩展

## 2. 后端架构表

| 层级 | 模块 | 作用 | 对应 UI |
|---|---|---|---|
| 入口层 | `main.py` | 创建应用、注册路由、CORS、异常处理、启动服务 | 不直接对应按钮，是后端总入口 |
| 认证层 | `auth` | 登录、注册、验证码、JWT、用户信息 | 登录页、用户状态 |
| 项目层 | `projects` | 创建项目、切换项目、项目列表、项目配置 | 顶栏“选择项目” |
| 工作台层 | `workstation` | 工作台布局状态、当前打开工具、项目内工作区状态 | 整个工作站页面 |
| 工具注册层 | `tools_registry` | 系统内所有创作工具/插件的注册、启用、禁用、排序 | 左侧“添加创作工具 +” |
| 工具实例层 | `tool_instances` | 某个项目里实际挂了哪些工具、位置顺序、参数 | 左侧工具区块 |
| 助手层 | `assistant` | Neyria 对话、上下文、建议、工具调用 | 右侧 AI 助手区 |
| 会话层 | `chat_sessions` | 对话历史、消息流、SSE/流式返回 | 右下输入框、聊天记录 |
| 文件资产层 | `assets` | 上传文件、音频、歌词、参考图、工程附件 | 上传按钮、附件功能 |
| 生成任务层 | `jobs` | 视频生成、图像生成、音频生成、分析任务的异步队列 | 各工具按钮点击后的后台任务 |
| 工作流层 | `workflows` | 多工具串联、步骤状态、失败重试 | 未来“创作流程”“一键执行” |
| 搜索层 | `search` | 搜索项目、工具、设置、页面入口 | 顶栏搜索框 |
| 设置层 | `settings` | 保存模式、模型选择、用户偏好、项目偏好 | “选择保存模式”、模型按钮 |
| RAG/知识层 | `knowledge` | 文档上传、切片、检索、参考资料记忆 | 附件、参考文档、AI 检索 |
| 事件层 | `events` | 通知前端任务进度、工具状态、消息更新 | 未来状态提示、进度刷新 |

## 3. 推荐目录结构

```text
backend/
  main.py
  core/
    config.py
    security.py
    database.py
    deps.py
    exceptions.py
  routers/
    auth.py
    projects.py
    workstation.py
    tools.py
    assistant.py
    chat.py
    assets.py
    jobs.py
    search.py
    settings.py
  services/
    auth_service.py
    project_service.py
    workstation_service.py
    tool_registry_service.py
    tool_instance_service.py
    assistant_service.py
    chat_service.py
    asset_service.py
    job_service.py
    workflow_service.py
    search_service.py
    settings_service.py
    rag_service.py
  models/
    user.py
    project.py
    tool.py
    tool_instance.py
    chat.py
    asset.py
    job.py
    workflow.py
    setting.py
  schemas/
    auth.py
    project.py
    tool.py
    chat.py
    asset.py
    job.py
    setting.py
  repositories/
    user_repo.py
    project_repo.py
    tool_repo.py
    chat_repo.py
    asset_repo.py
    job_repo.py
  agents/
    neyria.py
    tools/
      base.py
      search_web.py
      current_time.py
      music_tools.py
      image_tools.py
      video_tools.py
  workers/
    audio_worker.py
    image_worker.py
    video_worker.py
  rag.py
```

## 4. UI 映射表

| UI 区域 | 前端动作 | 后端模块 |
|---|---|---|
| 选择项目 | 打开项目列表、切换项目 | `projects` |
| 搜索框 | 搜索设置、页面、工具、项目 | `search` |
| 选择保存模式 | 切换保存策略 | `settings` |
| 添加创作工具 + | 打开工具商店/工具列表/启用工具 | `tools_registry` + `tool_instances` |
| 左侧工具栏 | 查看已启用工具 | `tool_instances` |
| 中间创作区 | 展示当前项目工作流、工具输出 | `workstation` + `workflows` |
| 右侧 Neyria | 对话、建议、调工具 | `assistant` + `chat_sessions` |
| 附件按钮 | 上传文档/音频/参考素材 | `assets` + `knowledge` |
| 模型切换 Auto | 切换当前对话模型 | `settings` |
| 发送按钮 | 发消息并流式返回 | `chat` + `assistant` |

## 5. 数据库表建议

| 表名 | 作用 |
|---|---|
| `users` | 用户信息 |
| `projects` | 项目信息 |
| `project_members` | 项目成员，后期多人协作可扩展 |
| `tool_definitions` | 系统里有哪些工具/插件 |
| `project_tools` | 某个项目启用了哪些工具 |
| `chat_sessions` | 一个项目下的会话 |
| `chat_messages` | 会话消息 |
| `assets` | 上传的文件和素材 |
| `jobs` | 后台生成任务 |
| `job_logs` | 任务运行日志 |
| `workflows` | 工作流定义 |
| `workflow_steps` | 工作流步骤 |
| `settings_user` | 用户级设置 |
| `settings_project` | 项目级设置 |

## 6. 按钮/功能映射的正确方式

| 需求 | 后端做法 |
|---|---|
| 新增一个按钮 | 先定义它调用哪个接口 |
| 新增一个创作工具 | 先在 `tool_definitions` 注册，再在 `project_tools` 挂到项目 |
| 新增一个 AI 能力 | 放到 `assistant_service` 或 `agents/tools` |
| 新增一个生成能力 | 建立 `jobs` 异步任务，不要直接堵在请求里 |
| 新增一个项目设置项 | 放进 `settings_project` |
| 新增一个搜索入口 | 接到 `search` 聚合接口 |

## 7. 接口分组建议

```text
/api/auth/*
/api/projects/*
/api/workstation/*
/api/tools/*
/api/chat/*
/api/assistant/*
/api/assets/*
/api/jobs/*
/api/search/*
/api/settings/*
```

## 8. 推荐实施顺序

1. 先拆 `main.py`，只保留入口职责
2. 先做 `projects`，把“选择项目”做实
3. 再做 `tools_registry + project_tools`，把“添加创作工具 +”做实
4. 再做 `chat + assistant`，把右侧 Neyria 接进新工作站
5. 再做 `assets + knowledge`，把附件和文档检索接进来
6. 最后做 `jobs + workflows`，支持视频、图像、音频等重任务

## 9. 一句话结论

MultiNeiroCreator 下一步的后端核心，不是继续往老 `main.py` 补功能，而是先搭成一个**可持续扩展的工作站后端骨架**。最关键的基础模块是：

- 项目
- 工具注册
- 项目内工具实例
- AI 助手
- 任务系统
- 资产系统



- P0：先把 RAG 补到可长期用
- 加 RAG health check
- 加 document list/delete/replace/reindex
- 把 collection.add 改成“先删旧文档再写入”或显式 upsert 策略
- 给 chunk 加 overlap，至少先做 chunk_size + chunk_overlap
- P1：把单 agent 编排拆干净
- 新建 services/agent/context_builder.py
- 新建 services/agent/tool_executor.py
- 新建 services/agent/chat_orchestrator.py
- 新建 services/agent/history_service.py
- 目标是把 stream_chat() 拆成：
  
  - 组装上下文
  - 调模型首轮
  - 执行 tool
  - 二轮生成
  - SSE 输出
  - 持久化历史
- P2：把 agent 从“写死”升级成“可注册”
- 新建 agents/base.py
- 新建 agents/registry.py
- 新建 agents/factory.py
- 先只注册一个 NeyriaAgent ，不要急着多 agent
- 这样后面你再加“作词 agent / 编曲 agent / 项目管理 agent”时，不用再改主流程
- P3：补 Agent 的上下文分层
- 把上下文拆成四层：
  
  - system prompt
  - user profile
  - chat history
  - rag context
- 再加一层 project context
- 这样 assistant 才能真正绑定工作站里的“当前项目”
- P4：最后再考虑多 Agent / 路由
- 只有当你已经明确有多个职责不同的 agent 时，再做：
  
  - agent router
  - task dispatch
  - agent handoff
  - shared workspace state
- 现在做这个会空转，收益低
最实际的落地方案

- 如果你要继续开发，我建议下一步直接做这 3 个文件：
- backend/services/agent/context_builder.py
- backend/services/agent/tool_executor.py
- backend/services/agent/chat_orchestrator.py
- 然后把现有 assistant_service.stream_chat() 改成一个很薄的门面，只负责调用编排器。
你可以这样理解当前阶段

- 你现在已经有了： 单 assistant + tools + RAG + history + profile
- 你还没有： agent registry + agent runtime + project-aware context + document lifecycle + multi-agent dispatch
- 所以下一步不是“继续拆文件”，而是 把 assistant_service 变成 agent runtime 的第一版内核
建议你现在就做的第一项

- 先做 assistant_service 拆分，而不是碰前端，也不是直接上多 agent。
- 这是收益最高、风险最低的一步，做完之后整个后端会从“能跑”变成“能继续长”。
如果你要，我下一步可以直接开始给你落地这一版：

- 先把 assistant_service.py 拆成 context_builder + tool_executor + chat_orchestrator
- 保持现有接口不变
- 不动前端调用
- 顺手把 RAG 的“重复上传同名文件”问题一起修掉。