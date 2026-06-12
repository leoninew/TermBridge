# 前端工作台规格 / web Workspace Spec

Review status: Accepted

## Requirement basis

基于 `docs/requirement/20260608-web-workspace.md`，本阶段设计 Web Terminal Workspace 前端。Requirement 因用户新增 UI 技术栈要求回到 Draft。用户补充要求：前端使用 `yarn` 管理依赖，集成主流 ESLint 和格式化依赖，提供内嵌终端组件实现 session 可视化管理，并基于 `reka-ui`、`tailwindcss`、`@tailwindcss/vite`、`@lucide/vue` 实现 UI。

## Overview

前端实现一个 Vue 3 + TypeScript + Vite 单页应用，用于管理后端 ttyd session：

- 展示 session 列表。
- 创建 session。
- 查看 session 摘要/详情。
- 删除/停止 session。
- 在工作台内嵌展示 session 对应终端组件。
- 保留打开 session 对应 ttyd URL 的辅助入口。
- 处理 loading、empty、error 状态。

MVP 不自研终端后端协议，不实现认证，不实现复杂路由或状态管理。终端组件第一版通过内嵌后端返回的 ttyd URL 实现可视化管理；新窗口打开 URL 仅作为辅助入口。

## Design decisions

### 工程布局

当前仓库没有现成前端工程。新增根目录 `web/`：

```text
web/
  package.json
  yarn.lock
  index.html
  vite.config.ts
  tsconfig.json
  tsconfig.node.json
  tailwind.config.ts
  eslint.config.js
  .prettierrc.json
  src/
    main.ts
    App.vue
    api/
      sessions.ts
    types/
      sessions.ts
    components/
      SessionCreateForm.vue
      SessionList.vue
      SessionCard.vue
      SessionTerminal.vue
      AppStatus.vue
    styles.css
```

### 依赖管理

使用 `yarn` 管理前端依赖，提交 `yarn.lock`。

运行脚本：

- `yarn dev`
- `yarn build`
- `yarn preview`
- `yarn lint`
- `yarn format`
- `yarn format:check`
- `yarn typecheck`

### 技术栈

运行依赖：

- `vue`
- `@vitejs/plugin-vue`
- `reka-ui`
- `@lucide/vue`

开发依赖：

- `vite`
- `typescript`
- `vue-tsc`
- `tailwindcss`
- `@tailwindcss/vite`
- `eslint`
- `@eslint/js`
- `typescript-eslint`
- `eslint-plugin-vue`
- `prettier`
- `eslint-config-prettier`

说明：采用 ESLint flat config，这是当前主流 ESLint 配置方式；格式化使用 Prettier，ESLint 负责代码质量，Prettier 负责格式。UI 组件基础使用 `reka-ui`，样式使用 Tailwind CSS、显式 `tailwind.config.ts` 和 `@tailwindcss/vite`，图标使用 `@lucide/vue`；不引入其他 UI 框架和样式方案。依赖版本使用当前解析到的固定版本，不使用 `latest`。

### API client

在 `src/api/sessions.ts` 封装后端请求，组件不直接散落 `fetch` 细节。

接口：

- `listSessions(): Promise<Session[]>`
- `createSession(payload: CreateSessionPayload): Promise<Session>`
- `getSession(id: string): Promise<Session>`
- `deleteSession(id: string): Promise<void>`

API base：

- 默认使用相对路径 `/api`。
- Vite dev server 固定监听 `0.0.0.0:9007`，并配置 proxy 将 `/api` 和 `/health` 转发到 FastAPI 后端 `http://127.0.0.1:9008`。
- 健康检查 `GET /health` 可用于页面展示后端状态。

### TypeScript types

在 `src/types/sessions.ts` 定义：

```ts
type SessionStatus = 'starting' | 'running' | 'stopped' | 'failed'

interface Session {
  id: string
  name: string
  workspace: string
  runtime: string
  status: SessionStatus
  port: number
  url: string
  created_at: string
  updated_at: string
}

interface CreateSessionPayload {
  name: string
  workspace: string
  runtime: string
}
```

### UI 结构

MVP 使用单页面，无需 vue-router：

- Header：项目名、后端健康状态、刷新按钮。
- Create form：name、workspace、runtime select。
- Session list：卡片列表，展示核心字段并支持选择 active session。
- Session terminal：内嵌终端区域，展示当前 active session 的 ttyd 页面。
- Session actions：选择、打开外部终端、删除。
- State views：loading、empty、error。

Runtime 下拉固定为：

- `claude-code`
- `codex`
- `powershell`
- `bash`

### 终端组件

MVP 使用 `SessionTerminal.vue` 作为终端可视化组件：

- 接收当前 active session。
- 当 session 存在且有 `url` 时，通过 `iframe` 内嵌 ttyd URL。
- 未选择 session 时展示空状态提示。
- session 非 running 状态时展示状态提示，并仍允许用户查看 session 信息。
- 提供“在新窗口打开”作为辅助入口。

第一版不引入 `xterm.js` 直连 WebSocket；若后续需要自定义终端协议、复制粘贴增强、命令审计或多 pane，再评估 `xterm.js` 与后端代理协议。

### 终端打开方式

MVP 默认在页面中嵌入 ttyd URL；`window.open(session.url, '_blank', 'noopener,noreferrer')` 仅作为辅助操作。

使用 iframe 的前提是 ttyd 响应允许被当前前端 origin 嵌入；若遇到 `X-Frame-Options` 或 CSP 限制，需要回到后端/ttyd 配置调整。

后端启动 ttyd 时必须使用 writable 模式，否则 iframe 中可以看到终端但无法输入。

### 样式与响应式

使用 Tailwind CSS，不编写独立传统 CSS 体系，不引入 UI 框架。布局要求：

- 桌面端：表单和列表具备清晰分区。
- 窄屏：表单控件纵向排列，session 卡片可读可操作。

### 错误处理

- API 非 2xx 响应转换为用户可读错误。
- 创建失败、删除失败、加载失败分别展示错误。
- 删除前使用浏览器 `confirm` 做最小确认，避免误删。

## Affected components

- 新增前端工程：`web/`。
- 新增前端依赖锁：`web/yarn.lock`。
- 新增过程文档：`docs/spec/20260608-web-workspace.md`。
- 不修改后端 API，除非实现中发现必要契约缺口。

## Interfaces

### fastapi API consumed

- `GET /health`
- `GET /api/sessions`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}`
- `DELETE /api/sessions/{session_id}`

### Create session request

```json
{
  "name": "Preflight",
  "workspace": "D:/projects/preflight",
  "runtime": "claude-code"
}
```

### Session response

```json
{
  "id": "sess_...",
  "name": "Preflight",
  "workspace": "D:/projects/preflight",
  "runtime": "claude-code",
  "status": "running",
  "port": 9001,
  "url": "http://127.0.0.1:9001",
  "created_at": "2026-06-08T00:00:00Z",
  "updated_at": "2026-06-08T00:00:00Z"
}
```

## Technical questions

- 当前机器是否已有 yarn；若没有，需要用户安装或允许使用 Corepack 启用 yarn。
- Vite dev proxy 默认目标固定为 `http://127.0.0.1:9008`；前端开发服务固定使用 `0.0.0.0:9007`。
- 是否需要在页面中显示 `GET /health` 结果；MVP 建议显示。

## Risks

- 前端构建依赖 Node/Yarn 环境，若本机环境缺失会阻塞验证。
- 后端返回的 ttyd URL 如果与前端访问环境跨主机，可能需要后续引入 `public_base_url` 配置。
- iframe 内嵌 ttyd 可能受 `X-Frame-Options`、CSP 或跨域策略影响，需要验证 ttyd 是否允许嵌入。
- 内嵌终端在移动端、复制粘贴、快捷键处理上可能存在浏览器限制。
- 不引入 Pinia/vue-router 可降低 MVP 复杂度，但未来多页面时需要补架构。

## Alternatives

### 复用现有 `wetty/`

不采用。当前仓库中 `wetty/` 被 `.gitignore` 忽略，且未发现可复用前端工程入口。新增 `web/` 更清晰。

### 新窗口打开 ttyd

不作为主路径。仅保留为辅助入口或 iframe 受限时的降级操作。

### 引入 UI 框架

不采用。只使用 `reka-ui` 作为无样式/低样式基础组件能力，视觉样式由 Tailwind CSS 完成，不引入 Element Plus、Naive UI、Ant Design Vue 等 UI 框架。

### 引入 Pinia/vue-router

暂不采用。MVP 单页面状态足够；后续扩展 Session detail 独立页面时再引入。

## User review notes

- 用户补充：前端使用 `yarn` 管理依赖，集成主流 ESLint 和格式化依赖。
- 用户更新：需要提供终端组件，实现对 session 的可视化管理，而不是只打开 URL。
- 用户更新：前端 UI 基于 `reka-ui`、`tailwindcss`、`@tailwindcss/vite`、`@lucide/vue`，不引入其他框架和样式。
- 待用户 review。若确认规格或要求进入计划阶段，将本规格状态更新为 `Accepted`。
