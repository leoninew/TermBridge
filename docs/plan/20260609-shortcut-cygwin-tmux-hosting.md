# 快捷方式 Cygwin tmux 托管实施计划

Review status: Accepted

当前：严格模式 / strict，实现 / Implementation

## Requirement and spec basis

- Requirement: `docs/requirement/20260609-shortcut-cygwin-tmux-hosting.md`
- Requirement status: Accepted
- Spec: `docs/spec/20260609-shortcut-cygwin-tmux-hosting.md`
- Spec status: Accepted

目标是一次性将“终端定义 / terminal definition”入口配置迁移为“快捷方式 / shortcut”，第一阶段只实现 `cygwin_tmux` host，通过 Cygwin bash + tmux + ttyd 托管 Claude Code 和 Codex 等入口命令。

## Implementation decisions for this plan

1. API 直接迁移到 `/api/shortcuts`，前端不再调用 `/api/terminals`。
2. 后端服务类可保留 `TerminalService` 名称用于 ttyd/Cygwin/tmux 环境能力管理，但入口配置模型、方法、API 和前端命名迁移为 shortcut。
3. `ShortcutHost` 模型保留 `windows`、`cygwin`、`wsl`、`cygwin_tmux`，但 create/update/start 第一阶段只允许 `cygwin_tmux`。
4. 创建 session 时只走 shortcut 路径：`shortcut_id + workspace + name`。移除 UI 中 custom terminal command 入口。
5. Shortcut 不存工作目录；workspace 仍保存在 session record。
6. tmux session name 使用应用 session id 作为稳定默认值；如果用户 session name 适合 tmux，可记录 display name 但不依赖它作为唯一 tmux id。
7. 启动前 host ready check 只校验配置：Cygwin bash path 可解析、ttyd executable 可解析；不做 tmux 版本/进程检测。
8. 旧 terminal definitions state 不迁移：新 state 字段使用 shortcuts，读取旧 `user_terminals` / `system_overrides` 时忽略。

## Backend implementation steps

### 1. Models

文件：`src/cc_ttyd/models.py`

变更：

- 新增：
  - `ShortcutHost = Literal["windows", "cygwin", "wsl", "cygwin_tmux"]`
  - `Shortcut`
    - `id: str`
    - `name: str`
    - `command: str`
    - `host: ShortcutHost`
    - `description: str | None = None`
    - `icon: str | None = None`
  - `ShortcutListResponse`
  - `CreateShortcutRequest`
  - `UpdateShortcutRequest`
- 删除或停止使用：
  - `TerminalDefinition`
  - `TerminalListResponse`
  - `CreateTerminalRequest`
  - `UpdateTerminalRequest`
  - system/user/source/enabled/hidden/deletable/detected 入口配置语义。
- 调整 `TerminalState`：
  - `shortcuts: list[Shortcut] = Field(default_factory=list)`
  - 保留 `settings: TerminalSettings`
  - 保留 `cygwin_settings: CygwinSettings`
  - 不再保留 `user_terminals` / `system_overrides` 作为新模型字段；如兼容旧 JSON 读取需要，使用 Pydantic ignore extra 或默认忽略旧字段。
- 调整 `CreateSessionRequest`：
  - `name: str = Field(min_length=1)`
  - `workspace: Path`
  - `shortcut_id: str = Field(min_length=1)`
  - 移除 `runtime`、`terminal_command`、`terminal_id` 的主路径。
- 调整 `SessionRecord`：
  - `shortcut_id: str`
  - `shortcut_name: str`
  - `host: ShortcutHost`
  - `tmux_session_name: str | None = None`
  - 保留 `workspace`、`command`、`port`、`pid`、`session_persistence`。
  - 移除或停止使用 `terminal_id`。
- 调整 `SessionResponse` 输出同样包含 shortcut 和 tmux 信息。

### 2. Repository/state

文件：`src/cc_ttyd/repositories.py`

变更：

- 可保留类名 `FileTerminalRepository`，也可重命名为 `FileShortcutRepository`；如果重命名，更新 DI。
- `get_state()` 读取旧 state 时忽略旧 terminal definitions，不做迁移。
- 首次无 shortcuts 时由 service 初始化默认 shortcuts，而不是 repository 内写业务默认值。

### 3. Service: shortcut management

文件：`src/cc_ttyd/services.py`

变更：

- 在现有环境能力服务中增加/替换 shortcut 方法：
  - `list_shortcuts() -> ShortcutListResponse`
  - `create_shortcut(request: CreateShortcutRequest) -> Shortcut`
  - `update_shortcut(shortcut_id: str, request: UpdateShortcutRequest) -> Shortcut`
  - `delete_shortcut(shortcut_id: str) -> None`
  - `_find_shortcut(shortcut_id: str) -> Shortcut`
- 删除旧 system terminal 自动检测/override 逻辑。
- 默认 shortcuts 初始化：
  - `claude-code`: Claude Code / `claude` / `cygwin_tmux`
  - `codex`: Codex / `codex` / `cygwin_tmux`
  - 默认项与用户项一致，可修改、删除。
- Validation：
  - `name.strip()` 非空。
  - `command.strip()` 非空。
  - `host == "cygwin_tmux"`，其他 host 第一阶段返回 `InvalidTerminalConfigError` 或新增更通用异常。

### 4. Service: cygwin_tmux session command

文件：`src/cc_ttyd/services.py`

新增或替换：

- `resolve_shortcut_command(shortcut_id: str, workspace: Path, tmux_session_name: str) -> tuple[list[str], Shortcut]`
- `_ensure_shortcut_host_ready(shortcut: Shortcut) -> None`
- `_build_cygwin_tmux_command(shortcut: Shortcut, workspace: Path, tmux_session_name: str) -> list[str]`
- `_normalize_tmux_session_name(name: str) -> str`

建议命令结构：

```text
bash -lc "cd <workspace> && tmux new-session -A -s <tmux_session_name> <shortcut.command>"
```

或沿用现有实现拆成 ttyd 执行：

```text
bash -lc "cd <workspace> && exec tmux new-session -A -s <tmux_session_name> <shortcut.command>"
```

实现时继续使用 `shlex.quote` 包裹 workspace、tmux session name 和 command，避免外层 shell 注入。注意 command 本身按需求允许任意非空白字符串，因此 quote 策略需要保证它作为 tmux shell command 执行，而不是被拆坏。

Host ready check：

- `cygwin_settings.bash_path` 或已配置 Cygwin bash 可解析。
- `resolve_ttyd_executable("cygwin", bash_path)` 可返回路径或 `ttyd`。
- 不调用 `check_tmux()` 做版本/进程检测。

### 5. SessionService

文件：`src/cc_ttyd/services.py`

变更：

- `create()` 改为必需 `request.shortcut_id`。
- 生成 `session_id` 后，以 `session_id` 或规范化 `request.name` 生成 `tmux_session_name`。
- 调用 shortcut service 解析 runtime command 和 shortcut。
- `runtime` 字段可改为 `host` 或保留为兼容内部字段但输出 shortcut host；优先按模型迁移。
- `ttyd_executable` 使用全局 ttyd settings / Cygwin resolution。
- `SessionRecord` 保存：
  - shortcut id/name
  - workspace
  - host
  - tmux session name
  - session_persistence=`tmux`
  - tmux bash path
- `restart()` 沿用现有语义：如果 ttyd 进程停止，使用存储的 command 重新启动 ttyd attach；不 kill/recreate tmux session。
- `delete()` 继续 terminate ttyd 进程，并按 `tmux_session_name` kill tmux session。

### 6. API

文件：`src/cc_ttyd/api.py`

变更：

- 替换 `/api/terminals` routes 为：
  - `GET /api/shortcuts`
  - `POST /api/shortcuts`
  - `PUT /api/shortcuts/{shortcut_id}`
  - `DELETE /api/shortcuts/{shortcut_id}`
- 删除 `/api/terminals/tmux/check` 或仅保留环境管理仍需要的 tmux check 能力；当前环境页已有 `/api/environment/cygwin/check`，优先删除旧 terminal tmux check API。
- 保留：
  - `/api/terminal-settings`，因为它现在实际表达 ttyd settings；是否后续改名另开需求。
  - `/api/environment/*`
  - `/api/sessions*`
- `POST /api/sessions` 使用 `shortcut_id + workspace + name`。
- 错误消息从 “Terminal not found” 改为 “Shortcut not found”。

### 7. Exceptions and DI

文件：

- `src/cc_ttyd/exceptions.py`
- `src/cc_ttyd/di.py`

变更：

- 新增或重命名：
  - `ShortcutNotFoundError`
  - `ShortcutRepositoryError` 如需更清晰命名。
- 如果保留 repository/service 类名，可至少更新 API 层和用户可见错误文案为 shortcut。
- DI 中注入服务的语义可以暂时保留，Plan 允许实现时决定是否重命名类，避免一次改动过大。

## Frontend implementation steps

### 1. Types

文件：`frontend/src/types/sessions.ts`

变更：

- 新增：
  - `ShortcutHost`
  - `Shortcut`
  - `ShortcutListResponse`
  - `CreateShortcutPayload`
  - `UpdateShortcutPayload`
- 删除或停止导出 terminal definition 相关类型。
- 调整 `CreateSessionPayload`：
  - `name`
  - `workspace`
  - `shortcut_id`
  - 移除 `terminal_id`、`runtime`、`terminal_command`。
- 调整 `SessionResponse` 增加 shortcut/tmux 字段。

### 2. API client

文件：`frontend/src/api/sessions.ts`

变更：

- 替换：
  - `listTerminals` -> `listShortcuts`
  - `createTerminal` -> `createShortcut`
  - `updateTerminal` -> `updateShortcut`
  - `deleteTerminal` -> `deleteShortcut`
- Endpoint 改为 `/api/shortcuts`。
- `createSession` payload 使用 `shortcut_id`。
- 删除旧 tmux terminal check client；保留 environment check clients。

### 3. Shortcut management UI

文件：

- `frontend/src/components/TerminalManagement.vue`

变更选项：

- 直接重命名为 `ShortcutManagement.vue`，并更新 import；或保留文件名但组件内容改为 shortcut。推荐重命名，符合需求。
- UI 内容：
  - 标题：快捷方式。
  - 描述：管理在 host 环境中启动的入口命令。
  - 卡片展示 name、host、command、description/icon。
  - 操作：编辑、删除。
  - 不显示 system/user、enabled/hidden/deletable。
  - 默认 Claude/Codex 与其他 shortcuts 同等编辑删除。
- 表单：
  - name
  - command
  - host（第一阶段固定/只允许 `cygwin_tmux`）
  - description
  - icon

### 4. Session create UI

文件：`frontend/src/components/SessionCreateForm.vue`

变更：

- `listTerminals()` 改为 `listShortcuts()`。
- 选择字段从 terminal 改为 shortcut。
- 删除 custom terminal command 选项。
- payload 提交 `shortcut_id` + `workspace` + `name`。
- 文案改为“选择快捷方式”和“选择工作空间”。

### 5. App navigation and labels

文件：

- `frontend/src/App.vue`
- `frontend/src/components/AppStatus.vue`
- `frontend/src/components/SessionList.vue`
- `frontend/src/components/SessionCard.vue`
- `frontend/src/i18n/locales/zh-CN.json`
- `frontend/src/i18n/locales/en-US.json`

变更：

- 导航项“终端管理”改为“快捷方式”。
- 替换 `terminalManagement` i18n namespace 为 `shortcutManagement`，或至少用户可见文案全部改为快捷方式。
- Session list/card 展示 shortcut name/host，不展示 terminal id。
- 移除旧“终端定义”用户可见文案。

## Tests

### Backend tests

文件：

- `tests/test_terminal_service.py` 可重命名为 `tests/test_shortcut_service.py`，或先在原文件中迁移内容。
- `tests/test_api.py`

覆盖：

1. 默认 shortcuts 初始化包含 Claude Code 和 Codex。
2. 创建 shortcut 成功，host 为 `cygwin_tmux`。
3. 创建 shortcut 时 name/command 空白失败。
4. 第一阶段创建非 `cygwin_tmux` host 失败。
5. 更新 shortcut 成功。
6. 删除默认 shortcut 成功，不受 system/user 限制。
7. 旧 terminal definitions state 不迁移到 shortcuts。
8. session create 使用 shortcut + workspace。
9. cygwin_tmux host 配置未就绪时 session create 失败且错误可理解。
10. session record 保存 shortcut_id、shortcut_name、host、tmux_session_name、workspace。
11. delete session 使用 tmux_session_name kill tmux session。
12. restart stopped session 复用已存 command attach tmux。
13. `/api/shortcuts` CRUD。
14. `/api/sessions` request/response 使用 shortcut 字段。
15. 旧 `/api/terminals` 如删除，则不再测试；如保留 404/410，则测试对应行为。

### Frontend checks

- `yarn --cwd frontend typecheck`
- `yarn --cwd frontend lint`
- `yarn --cwd frontend prettier --check frontend/src/components/ShortcutManagement.vue frontend/src/components/SessionCreateForm.vue frontend/src/api/sessions.ts frontend/src/types/sessions.ts frontend/src/i18n/locales/zh-CN.json frontend/src/i18n/locales/en-US.json frontend/src/App.vue`

### Backend checks

- `uv run pytest tests/test_terminal_service.py tests/test_api.py`
- 如测试文件重命名，改为对应新文件。
- `uv run ruff format --check src/cc_ttyd/models.py src/cc_ttyd/services.py src/cc_ttyd/api.py src/cc_ttyd/repositories.py tests/test_terminal_service.py tests/test_api.py`

## Manual verification

如果执行 UI 验证：

1. 打开应用，导航显示“快捷方式”。
2. 快捷方式列表默认显示 Claude Code 和 Codex。
3. 新建/编辑/删除快捷方式正常。
4. 新建 session 时选择 shortcut + workspace。
5. Cygwin host 配置就绪时启动后进入 tmux-backed ttyd 页面。
6. Cygwin host 配置未就绪时显示明确错误。
7. 删除 session 后对应 tmux session 被清理。

如用户只要求 lint/test/format，可在 Verification 中记录未执行浏览器手工验证。

## Files to change

Backend:

- `src/cc_ttyd/models.py`
- `src/cc_ttyd/services.py`
- `src/cc_ttyd/api.py`
- `src/cc_ttyd/repositories.py`
- `src/cc_ttyd/exceptions.py`
- `src/cc_ttyd/di.py`
- `tests/test_terminal_service.py` 或重命名后的 shortcut service test
- `tests/test_api.py`

Frontend:

- `frontend/src/types/sessions.ts`
- `frontend/src/api/sessions.ts`
- `frontend/src/components/TerminalManagement.vue` -> `ShortcutManagement.vue`
- `frontend/src/components/SessionCreateForm.vue`
- `frontend/src/components/SessionList.vue`
- `frontend/src/components/SessionCard.vue`
- `frontend/src/components/AppStatus.vue`
- `frontend/src/App.vue`
- `frontend/src/i18n/locales/zh-CN.json`
- `frontend/src/i18n/locales/en-US.json`

Docs:

- `docs/verification/20260609-shortcut-cygwin-tmux-hosting.md` 在 Verification 阶段创建。

## Blockers

无当前已知 blocker。

## Assumptions

- 已有环境运行时管理改动会先或同时落地，Cygwin settings 和 ttyd settings 可用。
- 用户接受旧 terminal definitions 数据直接删除，不做迁移。
- 第一阶段不需要 Windows/WSL shortcut 实际启动。
- Shortcut command 是本机命令入口，允许任意非空白字符串。

## Risks

- 一次性命名迁移改动面大，容易遗漏前端文案或测试引用。
- 旧 session registry 中包含 `terminal_id` 的记录可能无法按新模型读取；实现时需要决定是否清空、兼容读取或给出 repository error。建议兼容读取旧 session 字段为可选，但新 session 只写 shortcut 字段。
- tmux command quoting 需要谨慎，既要允许用户 command 字符串，又不能把 workspace/session name 拼接成外层 shell 注入点。
- Cygwin workspace path 可能需要转换为 Cygwin 可识别路径；现有 `_to_forward_slash` 可能足够，但实现后需测试。

## Rollback

- 如果 shortcut UI/API 迁移风险过大，可以回滚本需求改动，恢复 `/api/terminals` 与 `TerminalManagement.vue`。
- 环境管理相关 ttyd/Cygwin/tmux API 不在本需求中删除，回滚 shortcut 不应影响环境检测。
- 如 tmux hosting 启动逻辑异常，可先保留 shortcuts CRUD，暂时禁用 session create 的 `cygwin_tmux` 启动入口并显示配置错误。

## User review notes

待补充。
