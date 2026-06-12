# 前端工作台计划 / web Workspace Plan

Review status: Accepted

## Basis

- Requirement: `docs/requirement/20260608-web-workspace.md`，因终端组件需求变更回到 `Draft`。
- Spec: `docs/spec/20260608-web-workspace.md`，因终端组件设计变更回到 `Draft`。
- 流程模式：严格模式 / strict。

## Implementation steps

1. 创建 `web/` Vue 3 + TypeScript + Vite 工程骨架。
   - 新增 `package.json`、`index.html`、`vite.config.ts`、TypeScript 配置。
   - 使用 `yarn` 管理依赖并生成/提交 `web/yarn.lock`。
2. 集成代码质量和 UI 工具链。
   - 配置 ESLint flat config。
   - 集成 `eslint`、`@eslint/js`、`typescript-eslint`、`eslint-plugin-vue`、`eslint-config-prettier`。
   - 配置 Prettier，提供 `format` 和 `format:check` 脚本。
   - 集成 `reka-ui`、`tailwindcss`、`@tailwindcss/vite`、`@lucide/vue`。
   - 增加显式 `tailwind.config.ts`，并将 Tailwind 配置纳入 TypeScript node 配置范围。
   - 依赖使用固定版本，不使用 `latest`。
   - UI 只使用 reka-ui 基础能力、Tailwind CSS 工具类和 lucide 图标，不引入其他 UI 框架或样式方案。
3. 实现 API 与类型层。
   - 在 `src/types/sessions.ts` 定义 session status、session response、create payload 类型。
   - 在 `src/api/sessions.ts` 封装 `GET /health`、`GET /api/sessions`、`POST /api/sessions`、`GET /api/sessions/{session_id}`、`DELETE /api/sessions/{session_id}`。
   - API client 统一处理非 2xx 响应并抛出用户可读错误。
4. 实现单页 UI 和终端可视化管理。
   - `App.vue` 负责页面状态、加载 session、创建 session、删除 session、刷新、健康检查和 active session 选择。
   - `AppStatus.vue` 展示后端健康状态和刷新入口。
   - `SessionCreateForm.vue` 负责名称、workspace、runtime 输入。
   - `SessionList.vue` 负责 loading、empty、error 和列表渲染。
   - `SessionCard.vue` 展示详情字段并提供选择、打开外部终端、删除操作。
   - `SessionTerminal.vue` 内嵌展示当前 active session 的 ttyd 页面，并处理未选择、非 running、缺少 URL 等状态。
5. 实现 Tailwind 响应式样式。
   - 使用 Tailwind CSS 工具类，不维护独立传统 CSS 样式体系。
   - 桌面端保持表单、列表、终端分区清晰；窄屏下表单和操作按钮纵向排列。
6. 运行验证并记录结果。
   - 安装依赖。
   - 运行 lint、format check、typecheck、build。
   - 如项目包含可用测试入口，再运行相关测试。

## Files to change

计划新增：

- `Makefile`
- `web/package.json`
- `web/yarn.lock`
- `web/index.html`
- `web/vite.config.ts`
- `web/tsconfig.json`
- `web/tsconfig.node.json`
- `web/tailwind.config.ts`
- `web/eslint.config.js`
- `web/.prettierrc.json`
- `web/src/main.ts`
- `web/src/App.vue`
- `web/src/api/sessions.ts`
- `web/src/types/sessions.ts`
- `web/src/components/AppStatus.vue`
- `web/src/components/SessionCreateForm.vue`
- `web/src/components/SessionList.vue`
- `web/src/components/SessionCard.vue`
- `web/src/components/SessionTerminal.vue`
- `web/src/styles.css`：仅保留 Tailwind CSS 入口。

计划更新：

- `docs/verification/20260608-web-workspace.md`：验证阶段创建或更新。

不计划修改：

- 后端 API 实现。
- 仓库根目录现有 fastapi、cc-switch、preflight 相关代码。
- 认证、权限、复杂路由、状态管理、自研终端后端协议或 `xterm.js` 直连实现。

## Verification plan

优先在 `web/` 内执行：

1. `yarn install`
2. `yarn lint`
3. `yarn format:check`
4. `yarn typecheck`
5. `yarn build`

如果环境缺少 `yarn`：

- 先检查是否可用 Corepack 启用 yarn。
- 若仍不可用，将阻塞项记录到 verification，并向用户说明需要安装/启用 yarn。

验证阶段还需对照 diff 检查：

- 是否只新增/修改计划范围内文件。
- 是否满足 requirement acceptance criteria。
- 是否符合 spec 中的 yarn、ESLint、Prettier、reka-ui、Tailwind CSS、@lucide/vue、单页 MVP、Vite proxy、内嵌终端组件、外部打开辅助入口。

## Blockers

- 本机 Node/Yarn 环境可能缺失或版本不兼容。
- 依赖安装需要网络访问；若环境无法访问 registry，会阻塞 lockfile 生成与命令验证。

## Assumptions

- 前端目录使用根目录 `web/`。
- 后端 ttyd 启动命令加入 `--writable`，确保前端内嵌终端可输入。
- 前端开发服务固定使用 `0.0.0.0:9007`，后端 API 固定使用 `127.0.0.1:9008`，Vite dev proxy 将 `/api` 和 `/health` 转发到后端。
- Runtime 下拉固定为 `claude-code`、`codex`、`powershell`、`bash`。
- MVP 不引入 Pinia、vue-router、Element Plus、Naive UI、Ant Design Vue 或其他 UI 框架；样式只使用 Tailwind CSS。
- 内嵌终端第一版使用 iframe 嵌入 ttyd URL；外部打开仅作为辅助入口。
- 健康检查用于页面状态展示，但不阻止用户查看已有 session 列表。

## Risks

- 后端 session 字段若与文档示例不一致，前端类型或显示逻辑可能需要微调，并应同步更新过程文档。
- iframe 内嵌 ttyd 可能受 `X-Frame-Options`、CSP 或跨域策略影响，需要验证 ttyd 是否允许嵌入。
- iframe 方案只能管理 session 容器层，无法像 `xterm.js` 直连方案一样精细控制终端 buffer、输入输出流、快捷键、复制粘贴和多 pane 行为。
- Vite proxy 只覆盖本地开发；生产部署路径和后端地址可能需要后续配置。

## Rollback

- 若实现需要回退，可删除新增 `web/` 目录，并保留/更新过程文档说明未实施。
- 若仅依赖或 lint 配置有问题，可回退对应 `package.json`、`yarn.lock`、`eslint.config.js`、`.prettierrc.json` 变更。
- 不涉及数据库迁移或后端状态变更。

## User review notes

- 用户补充：前端使用 `yarn` 管理依赖，集成主流 ESLint 和格式化依赖。
- 用户要求：开始 Plan。
- 用户更新：需要提供终端组件，实现对 session 的可视化管理，而不是只打开 URL。
- 用户更新：前端 UI 基于 `reka-ui`、`tailwindcss`、`@tailwindcss/vite`、`@lucide/vue`，不引入其他框架和样式。
- 待用户 review。若确认计划或要求开始实现，将本计划状态更新为 `Accepted`。
