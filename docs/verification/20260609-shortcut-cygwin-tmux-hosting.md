# 快捷方式 Cygwin tmux 托管验证

Review status: Accepted

当前：严格模式 / strict，验证 / Verification

## Requirement alignment

- [x] 数据模型和 API 已迁移为 shortcut 语义，用于表达入口命令配置。
- [x] Shortcut 包含 `id`、`name`、`command`、`host`、`description`、`icon`。
- [x] 第一阶段 create/update/start 只允许 `cygwin_tmux` host。
- [x] Cygwin bash path 继续来自环境配置，不写入每个 shortcut。
- [x] ttyd path 继续来自全局 terminal settings / environment settings，不写入每个 shortcut。
- [x] 使用 shortcut 创建 session 时，后端构造 Cygwin bash + tmux 命令，并由 ttyd 承载。
- [x] session record / response 保存 `shortcut_id`、`shortcut_name`、`host`、`tmux_session_name` 等信息。
- [x] 默认提供 Claude Code shortcut：`claude`。
- [x] 默认提供 Codex shortcut：`codex`。
- [x] 默认 shortcuts 不区分 system/user，也不限制修改或删除。
- [x] 新建会话 UI 改为选择 shortcut + workspace。
- [x] 环境管理页继续承担 Cygwin/tmux/ttyd 检测和路径配置职责。

## Spec and plan alignment

- 后端模型移除了入口配置主路径上的 `TerminalDefinition` / `CreateTerminalRequest` / `UpdateTerminalRequest` / `TerminalListResponse`，新增 `Shortcut`、`CreateShortcutRequest`、`UpdateShortcutRequest`、`ShortcutListResponse`。
- API 主路径迁移为 `/api/shortcuts` CRUD；`/api/sessions` 使用 `shortcut_id` 创建 session。
- `TerminalService` 类名按计划保留用于 ttyd/Cygwin/tmux 环境能力管理，但入口配置方法和用户可见错误迁移为 shortcut。
- repository state 使用 `shortcuts`，旧 terminal definitions state 不迁移。
- 前端新增 `ShortcutManagement.vue`，删除 `TerminalManagement.vue`，导航从 `/terminals` 改为 `/shortcuts`。
- i18n 和 session 创建表单已切换到“快捷方式 / shortcut”语义。
- `/api/terminals/tmux/check` 仍保留，因为当前环境管理页仍通过该接口执行 tmux check；这符合 plan 中“仅保留环境管理仍需要的 tmux check 能力”的分支。

## Actual diff summary

Shortcut 相关主要改动：

- fastapi
  - `src/cc_ttyd/models.py`
  - `src/cc_ttyd/api.py`
  - `src/cc_ttyd/services.py`
  - `src/cc_ttyd/exceptions.py`
  - `src/cc_ttyd/repositories.py`
- web
  - `web/src/App.vue`
  - `web/src/api/sessions.ts`
  - `web/src/types/sessions.ts`
  - `web/src/components/ShortcutManagement.vue`
  - `web/src/components/TerminalManagement.vue`
  - `web/src/components/SessionCreateForm.vue`
  - `web/src/components/SessionCard.vue`
  - `web/src/components/AppStatus.vue`
  - `web/src/components/SessionList.vue`
  - `web/src/i18n/locales/en-US.json`
  - `web/src/i18n/locales/zh-CN.json`
- Tests
  - `tests/test_api.py`
  - `tests/test_services.py`
  - `tests/test_terminal_service.py`
- SDD docs
  - `docs/requirement/20260609-shortcut-cygwin-tmux-hosting.md`
  - `docs/spec/20260609-shortcut-cygwin-tmux-hosting.md`
  - `docs/plan/20260609-shortcut-cygwin-tmux-hosting.md`
  - `docs/verification/20260609-shortcut-cygwin-tmux-hosting.md`

当前工作树还包含 logging 相关未提交改动，例如 `src/cc_ttyd/logging.py`、`src/cc_ttyd/middleware.py`、`tests/test_logging.py` 和对应 SDD 文档；这些不是本 shortcut verification 的范围。

## Commands

### fastapi tests

```text
uv run pytest tests/test_terminal_service.py tests/test_services.py tests/test_api.py
```

Result:

```text
33 passed, 1 warning in 0.60s
```

Warning:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

### Python format

```text
uv run ruff format --check src/cc_ttyd/models.py src/cc_ttyd/api.py src/cc_ttyd/services.py src/cc_ttyd/exceptions.py src/cc_ttyd/repositories.py tests/test_api.py tests/test_services.py tests/test_terminal_service.py
```

Result:

```text
8 files already formatted
```

Full-repo format was not used for this pass because the user requested verifying this task's related functionality only.

### web checks

```text
yarn --cwd web typecheck
```

Result:

```text
vue-tsc --noEmit
Done
```

```text
yarn --cwd web lint
```

Result:

```text
eslint .
Done
```

```text
yarn --cwd web prettier --check src/components/ShortcutManagement.vue src/components/SessionCreateForm.vue src/components/SessionCard.vue src/components/AppStatus.vue src/components/SessionList.vue src/api/sessions.ts src/types/sessions.ts src/i18n/locales/zh-CN.json src/i18n/locales/en-US.json src/App.vue
```

Result:

```text
All matched files use Prettier code style!
```

## UI verification without playwright-cli

The user explicitly requested not to use `playwright-cli` for this verification pass.

Verified through web typecheck/lint/Prettier and source-level checks:

- `web/src/App.vue` routes `/shortcuts` to `ShortcutManagement` instead of `/terminals` to `TerminalManagement`.
- `web/src/components/ShortcutManagement.vue` loads shortcuts with `listShortcuts()`, supports create/edit/delete, and exposes `name`、`command`、`host`、`description`、`icon` fields.
- `web/src/components/SessionCreateForm.vue` loads shortcuts with `listShortcuts()` and submits `name + workspace + shortcut_id`.
- `web/src/components/SessionCard.vue` displays `shortcut_name` with fallback to `runtime`.
- `web/src/components/AppStatus.vue` and `web/src/components/SessionList.vue` navigate to `/shortcuts`.
- `web/src/i18n/locales/zh-CN.json` and `web/src/i18n/locales/en-US.json` contain `shortcutManagement` and `app.nav.shortcuts` wording.
- `web/src/components/EnvironmentManagement.vue` still contains the ttyd panel and Windows/Cygwin/WSL tabs, so environment management remains separate from shortcut management.

## Residual terminology search

Product-code search patterns:

```text
TerminalDefinition|terminal definition|terminalManagement|listTerminals|createTerminal|updateTerminal|deleteTerminal|terminal_id|terminal_command|CreateTerminal|UpdateTerminal|TerminalList
```

Searched under:

```text
src
web/src
tests
```

Relevant findings:

- Shortcut implementation files no longer expose terminal definition models, web `terminalManagement` namespace, `terminal_id`, or terminal CRUD client functions.
- Remaining product-code occurrences are expected runtime/environment concepts:
  - `UpdateTerminalSettingsRequest` / `updateTerminalSettings`, because ttyd settings remain a global terminal runtime setting.
  - `RuntimeRegistry.resolve(..., terminal_command)` remains in `src/cc_ttyd/runtime.py`, but `CreateSessionRequest` no longer exposes `terminal_command`, and `SessionService.create()` now uses `shortcut_id`.
  - `/api/terminals/tmux/check` remains covered by tests because environment management still uses it for tmux checking.
- Historical SDD documents still mention terminal definitions and `/terminals`; they are documentation history and were not migrated.

## Acceptance checklist

- [x] Shortcut CRUD API exists and is covered by tests.
- [x] Session creation uses `shortcut_id` and is covered by API/service tests.
- [x] Default Claude Code and Codex shortcuts are covered by tests.
- [x] Default shortcuts can be deleted, covered by tests.
- [x] Blank shortcut command is rejected, covered by tests.
- [x] Unsupported host is rejected in first-stage shortcut creation/update, covered by tests.
- [x] Old terminal definitions state is ignored, covered by tests.
- [x] Session delete uses stored `tmux_session_name`, covered by tests.
- [x] Session restart reuses stored ttyd/tmux command, covered by tests.
- [x] web shortcut API/types/UI typecheck and lint pass.
- [x] web shortcut UI formatting passes Prettier.
- [x] Source-level UI verification confirms shortcut management, session create, navigation, card display, and environment page separation.
- [x] Product-code search confirms old terminal definition naming is removed from shortcut main paths.

## Remaining risk

- `resolve_shortcut_command()` quotes the full shortcut command before passing it to `tmux new-session`; automated tests cover the constructed command shape, but a live Cygwin/tmux launch with real Claude/Codex binaries was not executed in this verification.
- No browser/manual UI run was performed in this pass because the user requested not to use `playwright-cli`; UI validation is limited to typecheck/lint/format and source-level checks.
- The working tree contains unrelated logging changes, but they were excluded from this task-scoped verification.

## Conclusion

Shortcut Cygwin tmux hosting implementation aligns with the accepted requirement, spec, and plan for the task-scoped verification pass. fastapi shortcut/session behavior is covered by 33 passing related tests, shortcut-related Python files are formatted, web typecheck/lint/Prettier pass, and source-level UI checks confirm the planned shortcut management and session creation paths without using `playwright-cli`.
