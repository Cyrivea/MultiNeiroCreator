# Neyria 前端

Vue 3 + TypeScript + Vite 的 AI 创作工作台前端，负责项目管理、本地文件夹读写、流式对话和工作流界面。

## 功能现状

- 登录、注册、JWT 过期检查和退出登录
- 项目创建、打开、最近项目和路由项目恢复
- 浏览器 File System Access API 本地项目保存
- Pinia 管理项目、聊天、用户和加载状态
- SSE 流式 AI 对话、工具调用状态和打字机效果
- 四类创作 Block 的参数面板：歌词 Block 已接入智谱生成，图像/视频/音频暂为后端 Provider 待接的界面原型
- 图片/文档附件预览与 Blob URL 生命周期管理
- 前端 Vitest 测试、ESLint、Prettier 和生产构建

## 技术栈

- Vue 3 + `<script setup>`
- TypeScript
- Pinia
- Vue Router
- Axios
- Element Plus（仅按需使用 `ElMessage`）
- Vite 8 / Vitest

## 开发启动

```bash
cd frontend
pnpm install
pnpm dev
```

后端默认由根目录的 `dev.sh` 启动，前端 API 地址由 `.env.development` 中的 `VITE_API_BASE` 配置；生产构建使用 `.env.production`。

## 质量检查

```bash
pnpm lint
pnpm format:check
pnpm test
pnpm build
```

当前测试基线：**31 个 Vitest 用例通过**。构建会生成独立的 Vue、Axios、Element Plus vendor chunk；构建产物 `dist/` 不提交到 Git。

## 目录说明

```text
src/
├── components/       # 项目和助手 UI
├── composables/      # 对话流、自动保存流程
├── stores/           # Pinia 状态
├── serve/            # HTTP/SSE 客户端
├── utils/            # 纯函数与基础设施
└── views/            # 页面与工作台布局
```

`WorkstationLayout.vue` 只做页面级协调，具体职责已经下沉到 stores、composables 和子组件。`src/assets/` 不再保留 Vite 模板遗留资源。
