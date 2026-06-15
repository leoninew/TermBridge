# 前端操作按钮加载与防重入

Review status: Accepted

## Background

当前已发现会话删除确认按钮缺少加载/spin 状态，删除请求进行中仍可能重复触发。用户进一步要求检查前端其他新建、编辑、删除按钮，确保异步操作期间有明确加载反馈，并阻止重复提交或重复点击。

## Goal

- 盘点前端中涉及新建、编辑、删除的用户操作按钮。
- 对会触发异步请求或持久化变更的按钮，补齐 loading/spinner 或等价的进行中反馈。
- 对同类按钮补齐防重入保护：请求进行中时禁用按钮、在 handler 中 guard，或使用现有提交状态阻止重复执行。
- 尽量复用现有 `Loader2`、`animate-spin`、`disabled` 样式和组件内已有状态命名模式。

## Non-goal

- 不重构整体状态管理或引入新的全局请求队列。
- 不改变后端 API 行为或接口契约。
- 不改变创建、编辑、删除操作的业务语义。
- 不扩大到纯本地 UI 展开/折叠、选择、搜索、导航等非持久化操作。

## User scenarios

- 用户在创建会话、保存配置或删除条目时，点击后能看到操作正在进行。
- 用户快速重复点击同一个新建/编辑/删除按钮时，不会发出重复请求。
- 某个操作失败后，按钮状态能恢复，用户可修正或重试。

## Button inventory

### 会话 / Sessions

- `web/src/components/SessionList.vue`：空列表创建链接 `session.list.emptyCreateLink`，打开创建表单；本身非异步。
- `web/src/components/SessionList.vue`：侧栏顶部创建按钮 `session.terminal.createTab`，打开创建表单；本身非异步。
- `web/src/components/SessionList.vue`：工作区行创建按钮 `session.workspace.createLabel`，带工作区上下文打开创建表单；本身非异步。
- `web/src/components/SessionTerminal.vue`：终端 tab `+` 创建入口，打开创建表单；本身非异步。
- `web/src/components/SessionTerminal.vue`：空终端创建链接 `session.terminal.createLink`，打开创建表单；本身非异步。
- `web/src/components/SessionCreateForm.vue`：创建会话提交按钮 `session.create.submit`，触发 `AppShell.handleCreate()` / `createSession()`；已有 `submitting` 禁用与 `Loader2`，实现阶段需确认 handler 层防重入。
- `web/src/components/SessionList.vue`：会话行删除按钮 `session.card.deleteLabel`，打开删除确认；本身非异步。
- `web/src/components/AppShell.vue`：会话删除确认按钮 `app.actions.delete`，触发 `confirmRemove()` / `deleteSession()`；已在当前改动中补充 `deletingSessionId`、禁用与 `Loader2`，实现阶段需纳入最终确认。
- `web/src/components/SessionList.vue`：工作区删除按钮 `session.workspace.deleteLabel`，打开工作区删除确认；本身非异步。
- `web/src/components/AppShell.vue`：工作区删除确认按钮 `app.deleteWorkspace.confirm`，触发 `confirmRemoveWorkspace()` / `deleteSessionWorkspace()`；当前缺少加载/spin 与 handler 防重入，需要修复。
- `web/src/components/SessionCard.vue`：会话卡片删除按钮 `session.card.deleteLabel`，触发 `remove`；当前看起来不是主路径引用组件，若仍保留应保持与会话列表行为一致。

### 快捷方式 / Shortcuts

- `web/src/components/ShortcutManagement.vue`：顶部新建快捷方式按钮 `shortcutManagement.actions.create`，打开创建/编辑弹窗；本身非异步。
- `web/src/components/ShortcutManagement.vue`：快捷方式卡片编辑按钮 `app.actions.edit`，打开创建/编辑弹窗；本身非异步。
- `web/src/components/ShortcutManagement.vue`：创建/编辑弹窗保存按钮 `app.actions.save`，触发 `saveShortcut()` / `createShortcut()` / `updateShortcut()`；已有 `saving` 禁用与 `Loader2`，实现阶段需补 handler 层防重入。
- `web/src/components/ShortcutManagement.vue`：快捷方式卡片删除按钮 `app.actions.delete`，打开删除确认；被使用中的快捷方式已有禁用，本身非异步。
- `web/src/components/ShortcutManagement.vue`：快捷方式删除确认按钮 `app.actions.delete`，触发 `confirmRemoveShortcut()` / `deleteShortcut()`；当前缺少加载/spin 与 handler 防重入，需要修复。
- `web/src/components/ShortcutManagement.vue`：快捷方式创建会话按钮 `shortcutManagement.actions.createSession`，带快捷方式上下文打开创建会话表单；本身非异步。

### 相邻高风险异步操作 / Adjacent high-risk async actions

- `web/src/components/AppShell.vue`：关闭全部会话确认按钮 `app.closeAllSessions.confirm`，触发 `confirmCloseAllSessions()` / `closeAllSessions()`；已有禁用状态但无 spinner，handler 层防重入需确认或补齐。
- `web/src/components/SessionList.vue`、`web/src/components/SessionTerminal.vue`、`web/src/components/SessionCard.vue`：启动会话按钮，触发 `handleStart()` / `startSession()`；已有 `startingSessionId`、禁用和 spinner，主 handler 已有防重入。
- `web/src/components/SessionList.vue`、`web/src/components/SessionCard.vue`：停止会话按钮，触发 `handleStop()` / `stopSession()`；当前缺少加载/spin 与 handler 防重入。虽然不是新建/编辑/删除，但属于高风险异步操作，默认纳入检查。

### 待定是否纳入 / Pending scope decision

- `web/src/components/SessionList.vue`：工作区拖拽排序 `reorderEnvironmentWorkspaces()` 和会话拖拽排序 `reorderWorkspaceSessions()`，属于隐式编辑；默认记录但不作为本次必须修复项，除非用户确认“编辑”包含排序。
- `web/src/components/SessionTerminal.vue`：终端 tab 拖拽排序，仅更新本地打开 tab 顺序；默认不纳入。
- `web/src/components/EnvironmentManagement.vue`：环境检查按钮会触发检查并可能保存路径设置；已有旋转图标和禁用状态，但按钮语义是“检查”而非新建/编辑/删除，默认不纳入。

## Acceptance

- 前端所有相关新建、编辑、删除按钮完成一次检查，并记录覆盖范围。
- 缺失 loading/spinner 或防重入的异步操作被修复。
- 已有 loading/spinner 和防重入的操作不做不必要改动。
- 至少运行前端类型检查；如有合适入口，再运行相关 lint/test。
- 不回退本轮之前已做的 `just install` 与会话删除按钮改动，除非发现冲突并另行说明。

## Open questions

- “编辑”范围暂按前端中保存/更新配置类操作处理；如果用户希望包含排序、拖拽重排等隐式编辑，需要后续确认。
- 是否要求工作区删除、关闭全部会话、停止会话等非严格 CRUD 的破坏性操作也纳入本次同类防重入检查？本需求默认将删除类和高风险异步按钮一并检查。

## Decisions

- 使用轻量模式 / light。
- 本阶段只产出 Requirement 草稿，不继续实现或验证；进入实现需用户接受需求或明确要求开始实现。

## Risk

- 一些按钮可能已经有禁用状态但无视觉 spinner；需要判断是否足以满足“加载/spin”的体验要求。
- 某些操作可能共用全局状态，补充 per-item loading 时需避免造成 UI 状态不一致。
- 如果当前工作区存在未完成改动，实现阶段需避免覆盖用户或前序改动。
