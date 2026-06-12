# 前端工作台需求 / web Workspace Requirement

Review status: Accepted

## Background

后端 ttyd 会话管理能力已完成并通过验证。项目下一阶段需要实现 Web Terminal Workspace 的前端部分，让用户可以通过浏览器管理后端会话，并打开对应 ttyd 终端页面。

README 中推荐前端技术栈为 Vue 3、TypeScript、Vite，并定位为轻量化本地 Web Terminal Workspace。前端应优先服务 MVP：替代本地终端窗口管理，提供会话列表、会话创建、会话查看和删除能力。

## Goals

- 基于 Vue 3 + TypeScript + Vite 实现前端应用。
- 提供会话列表页面，展示后端返回的 session 信息。
- 提供创建会话入口，允许输入名称、workspace、runtime。
- 支持查看单个会话详情，包括 status、runtime、workspace、port、url、created_at、updated_at。
- 支持停止/删除会话。
- 支持内嵌终端组件，用户可在前端工作台内直接进入和操作 session 对应的终端。
- 支持打开 ttyd 终端 URL 作为辅助操作或降级入口。
- 与已实现后端 API 对接：
  - `GET /health`
  - `POST /api/sessions`
  - `GET /api/sessions`
  - `GET /api/sessions/{session_id}`
  - `DELETE /api/sessions/{session_id}`
- 前端使用 `yarn` 管理依赖，并提交对应 lockfile。
- 前端基于 `reka-ui`、`tailwindcss`、`@tailwindcss/vite`、`@lucide/vue` 实现 UI，不引入其他 UI 框架和样式方案。
- 前端依赖使用固定版本，不使用 `latest` 版本范围。
- 前端集成主流 ESLint 与格式化工具链，提供 lint、format、format check、typecheck、build 等验证命令。

## Non-goals

- 本阶段不实现认证、权限、多用户隔离。
- 本阶段不实现复杂工作流、任务视图、token/cost 统计。
- 本阶段不实现 Git diff、Git 状态、运行日志等 V3/V4 功能。
- 本阶段不实现完整自研终端后端协议；终端组件优先复用后端返回的 ttyd 访问能力进行可视化嵌入或集成。
- 本阶段不实现移动端深度交互优化；但布局应具备基础响应式能力。
- 本阶段不修改后端 API 契约，除非实现中发现必要缺口并更新过程文档。

## User scenarios

1. 用户打开前端页面，可以看到当前 session 列表。
2. 用户点击创建会话，输入 session 名称、workspace 路径和 runtime，然后提交。
3. 创建成功后，新 session 出现在列表中，显示运行状态和访问 URL。
4. 用户在前端工作台中选择某个 session 后，可以在内嵌终端区域直接查看和操作该 session。
5. 用户也可以通过辅助入口打开原始 ttyd URL。
6. 用户点击删除/停止会话，前端调用后端 DELETE API，并从列表中移除或刷新状态。
7. 后端 API 失败时，前端展示明确错误信息，而不是静默失败。

## Acceptance criteria

- 前端工程可以通过项目约定命令安装依赖、启动开发服务、构建。
- 页面包含 session list、create session form、session detail/summary、embedded terminal area、delete action、open terminal fallback action.
- API client 封装后端请求，不在组件中散落 fetch 细节。
- TypeScript 类型覆盖 session request/response。
- 创建、列表、删除流程可通过 UI 操作完成。
- 前端能处理 loading、empty state、error state。
- 基础响应式布局可在窄屏下使用。
- 验证阶段记录实际运行的 lint/typecheck/build/test 命令结果。

## Open questions

- 前端目录应放在仓库根目录的 `web/`，还是复用现有 `wetty/` 或其他目录？
- 是否必须在本阶段引入 Pinia 和 vue-router，还是 MVP 使用单页面组件状态即可？
- 终端组件是通过 iframe 嵌入 ttyd，还是通过 xterm.js + WebSocket 对接后端/ttyd？
- 若使用 iframe，是否接受 ttyd 页面作为内嵌终端的第一版实现？
- 后端和前端开发时的代理配置是否采用 Vite dev server proxy `/api` 到 FastAPI？
- runtime 下拉选项是否固定为 `claude-code`、`codex`、`powershell`、`bash`？

## Decisions

- 流程模式使用严格模式 / strict。
- 前端技术栈基于 README 推荐：Vue 3、TypeScript、Vite。
- 后端 API 以已交付实现为准。
- 本阶段前端优先实现 MVP 会话管理和内嵌终端可视化管理，不扩展认证和高级 Agent 功能。

## User review notes

- 用户补充：前端使用 `yarn` 管理依赖，集成主流 ESLint 和格式化依赖。
- 用户更新：需要提供终端组件，实现对 session 的可视化管理，而不是只打开 URL。
- 用户更新：前端 UI 基于 `reka-ui`、`tailwindcss`、`@tailwindcss/vite`、`@lucide/vue`，不引入其他框架和样式。
