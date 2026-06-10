# 工作区中心的 tmux 会话模型验证

Review status: Accepted

当前：严格模式 / strict，验证阶段 / Verification

## Requirement alignment

- 已将后端会话模型从用户命名的 flat session 调整为 `运行环境 + 工作目录` 的 workspace，以及 workspace 下的 entry。
- 已避免使用用户输入名称生成 tmux session identity；workspace id 与 tmux session name 由 `host + normalized workspace path` 派生。
- 已将 entry 映射为 managed tmux window，并在记录中保存内部 `tmux_window_id`。
- 已增加 `环境 -> 目录 -> 会话入口` 的左侧树型导航和本地搜索。
- 已实现 stop entry：保留 TermBridge record，终止 ttyd process，并移除对应 managed tmux window。
- 已保持 tmux window id/current window name 不在 UI 显式展示。
- 已按用户要求不兼容旧 flat `SessionRecord`，不做数据迁移。

## Spec alignment

- Workspace identity：实现为稳定 `workspace_id` 与 `tmux_session_name`，区分 host 与路径。
- Managed window：创建 entry 时通过 `tmux new-window -P -F '#{window_id}'` 捕获 window id。
- Stop/delete/restart：后端已区分 entry window、workspace tmux session、ttyd process 和 TermBridge record。
- List API：新增 `/api/session-tree`，返回 environment/workspace/entry 树。
- Frontend navigation：`SessionList` 改为树型渲染，搜索保留树上下文并展开匹配祖先。
- WSL 语义：WSL 命令继续使用 `wsl --cd <Windows path>`；workspace tmux command 内部使用当前目录 `.`，不再把 Windows path 传给 tmux `-c`。

## Plan alignment

- Step 1 backend models：已完成 `WorkspaceRecord`、`SessionEntryRecord`、`SessionState`、tree response 类型。
- Step 2 tmux primitives：已完成 create window、attach command、kill window、kill workspace session 等基础能力。
- Step 3 SessionService lifecycle：已完成 create/list/tree/get/restart/stop/delete 的 workspace/entry 流程。
- Step 4 API semantics：已新增 `/api/session-tree` 与 `/api/sessions/{id}/stop`，保留现有 create/restart/delete endpoint。
- Step 5 frontend tree navigation：已完成 SessionList 树型导航、搜索、stop/restart/delete action wiring。
- Step 6 terminal display/actions：保留现有 terminal iframe 与 stopped restart CTA；stop action 放在左侧 entry/card 操作中。
- Step 7 documentation cleanup：未改旧 spec 文档；本次 verification 记录 supersede 状态，后续如要发布用户文档可再补 README/旧 spec note。

## Actual diff summary

- Backend:
  - `src/termbridge/models.py`：新增 workspace/entry/tree 模型。
  - `src/termbridge/repositories.py`：session registry 改为 workspace/entry state。
  - `src/termbridge/services.py`：SessionService lifecycle 改为 workspace tmux session + managed window；TerminalService 增加 tmux window primitives。
  - `src/termbridge/api.py`：新增 tree list 和 stop endpoint。
- Frontend:
  - `frontend/src/types/sessions.ts`、`frontend/src/api/sessions.ts`：同步 tree/stop API。
  - `frontend/src/App.vue`：以 session tree 作为刷新来源，派生 flat sessions 供现有终端和快捷方式管理使用。
  - `frontend/src/components/SessionList.vue`：改为 environment/workspace/entry 树型导航和搜索。
  - `frontend/src/components/SessionCard.vue`：增加 stop action。
  - locale files：增加搜索、停止和错误文案。
- Tests:
  - `tests/test_services.py`：覆盖 workspace identity、same workspace reuse、stop/delete/restart lifecycle、tree grouping、create 失败清理、运行中 window 丢失刷新、shortcut host mismatch restart 防护。
  - `tests/test_repositories.py`：覆盖 workspace/entry repository，以及旧 flat registry fail-fast。
  - `tests/test_api.py`：覆盖 tree 和 stop API。
  - `tests/test_terminal_service.py`：覆盖 WSL `wsl --cd` 与 tmux window command 行为。

## Planned vs actual changed files

Planned and changed:

- `src/termbridge/models.py`
- `src/termbridge/repositories.py`
- `src/termbridge/services.py`
- `src/termbridge/api.py`
- `tests/test_services.py`
- `tests/test_repositories.py`
- `tests/test_api.py`
- `tests/test_terminal_service.py`
- `frontend/src/types/sessions.ts`
- `frontend/src/api/sessions.ts`
- `frontend/src/App.vue`
- `frontend/src/components/SessionList.vue`
- `frontend/src/components/SessionCard.vue`
- `frontend/src/i18n/locales/zh-CN.json`
- `frontend/src/i18n/locales/en-US.json`

Additional formatter-only changes:

- `frontend/src/components/EnvironmentManagement.vue`
- `frontend/src/components/ShortcutManagement.vue`

Not changed:

- `frontend/src/components/SessionTerminal.vue`：现有 stopped restart UI 足够覆盖本阶段。
- Old spec documents：未在本次实现中追改历史规格文档。

## Acceptance criteria checklist

- [x] 不同工作目录即使显示名称相同，也不会使用同一个 tmux session name。
- [x] 同一 host + workspace 复用同一个 workspace record 和 tmux session name。
- [x] 同一 workspace 下可显示多个 entry。
- [x] 左侧导航按 environment -> workspace -> entry 展示。
- [x] 搜索覆盖 environment、workspace name/path、entry name、shortcut/runtime。
- [x] 用户输入名称只作为 entry display name，不作为 tmux session identity。
- [x] tmux session identity 由稳定 workspace identity 派生。
- [x] workspace 对应 tmux session。
- [x] entry 对应 managed tmux window，并记录稳定 window id。
- [x] 点击/重启 entry 使用 workspace tmux session + window attach command。
- [x] Stop entry 保留 record，并移除 managed tmux window。
- [x] Delete last entry 会清理 workspace tmux session。
- [x] UI 不展示 tmux window id/current window name。
- [x] 手工 tmux window 自动导入不在本阶段范围内。

## Commands

- `python -m pytest tests/test_terminal_service.py -q` — passed, `29 passed`。
- `python -m pytest tests -q` — passed, `83 passed, 1 warning`。
- `python -m ruff check src tests` — passed。
- `python -m mypy src` — not run; current Python environment has no `mypy` module installed。
- `yarn --cwd frontend typecheck` — passed。
- `yarn --cwd frontend lint` — passed。
- `yarn --cwd frontend format:check` — passed。
- `yarn --cwd frontend build` — passed; Vite/Rolldown emitted existing dependency `/* #__PURE__ */` annotation warnings from `node_modules/@vueuse/core`。

## Manual/UI verification

- Browser automation was not available: `agent-browser` was not found in PATH。
- No browser-based interactive UI verification was performed in this environment。
- Code-level UI self-check completed for:
  - SessionList tree hierarchy and search expansion。
  - App refresh and selection flow after create/restart/stop/delete。
  - Create panel closing when selecting an entry。
  - Stop action wiring from SessionCard -> SessionList -> App -> API。

## Review follow-up fixes

只读审查后已修复以下问题：

- Linux/WSL workspace identity 保留路径大小写，只对 Windows/Cygwin 做 case-fold，避免 case-sensitive 路径碰撞。
- 旧 flat `sessions.json` 现在 fail-fast 为 incompatible schema，避免被静默当作空 registry 覆盖。
- create/restart 在 tmux window 已创建但后续启动或持久化失败时会清理 ttyd process 和 managed tmux window。
- refresh running entry 时同时校验 ttyd process 和 managed tmux window；window 丢失会降级为 stopped。
- restart stopped entry 时校验 shortcut host 与 workspace host 一致，避免 shortcut 更新 host 后跨 host 创建 window。
- stopped session 的 terminal UI 先按 status 展示 restart CTA，不再被空 url 提前拦截为 missing URL。

## Missed or expanded scope

- Used custom nested tree buttons rather than Reka UI Tree primitives. This preserves the requested tree semantics and current visual style while avoiding a broader component migration.
- Did not implement explicit reconnect-vs-restart UI state because backend status enum still exposes `starting/running/stopped/failed` only。
- Did not implement startup scan/manual scan for tmux state, per accepted scope。
- Did not implement old flat session registry compatibility or migration, per user instruction。

## Remaining risk

- Real tmux behavior across Windows/Cygwin, Windows/WSL, and Linux still needs manual smoke testing on actual host runtimes, especially quoting and `tmux new-window -P -F '#{window_id}'` output。
- Lazy recovery after backend restart is represented in service semantics but not fully covered by live tmux integration tests。
- Frontend visual verification should be performed manually or with browser tooling when available。

## Conclusion

Implementation matches the accepted Requirement, Spec, and Plan for the workspace-centered tmux session model. Automated backend and frontend checks pass, with only environment/tooling limitations for `mypy` and browser-based UI verification.
