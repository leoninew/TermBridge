# RSPV 环境模型调整实施计划

Review status: Accepted

当前：严格模式 / strict，实现阶段 / Implementation

## Requirement basis

- Requirement: `docs/requirement/20260610-rspv-environment-model.md`
- Requirement status: Accepted

核心决策：

- 环境形态是 Windows/Cygwin、Windows/WSL、Linux，不再是 Windows、Cygwin、WSL 三个并列环境。
- 三类环境形态均以 tmux-backed session persistence 为核心能力。
- 当前 Windows 宿主下，Linux 明确 unavailable。
- Windows/WSL 不保存 distro，只检测默认 WSL。
- `ShortcutHost` 立即重命名为 `windows_cygwin` / `windows_wsl` / `linux`。
- 不做向后兼容和迁移。
- `screen` 保留为 open question，不进入本阶段实现。

## Spec basis

- Spec: `docs/spec/20260610-rspv-environment-model.md`
- Spec status: Accepted

本计划按 spec 执行破坏性重命名和 API 语义收敛，不保留旧环境 API、旧 `ShortcutHost` 输入或旧 terminal state 迁移。

## Implementation approach

分三层实施：

1. 后端模型和服务先收敛到环境形态：`windows_cygwin` / `windows_wsl` / `linux`。
2. API 改为形态化 endpoint，删除旧 Cygwin/Windows/WSL 并列环境接口。
3. 前端环境管理页改为三种环境形态 tab，并同步类型、API client、i18n 和测试。

当前阶段只保证 `windows_cygwin` 可用于 session 启动；`windows_wsl` 和 `linux` 先作为检测形态存在。若用户通过 shortcut 选择尚未实现启动的 host，应返回明确错误。

## Files to change

### Backend

- `src/termbridge/models.py`
- `src/termbridge/services.py`
- `src/termbridge/api.py`
- `tests/test_terminal_service.py`
- `tests/test_services.py`
- `tests/test_api.py`

### Frontend

- `frontend/src/types/sessions.ts`
- `frontend/src/api/sessions.ts`
- `frontend/src/components/EnvironmentManagement.vue`
- `frontend/src/i18n/locales/zh-CN.json`
- `frontend/src/i18n/locales/en-US.json`

### Documentation

- `docs/verification/20260610-rspv-environment-model.md`

## Implementation steps

### 1. Backend model updates

1. Replace `ShortcutHost` values with:

   ```python
   ShortcutHost = Literal["windows_cygwin", "windows_wsl", "linux"]
   ```

2. Replace or rename environment response models:
   - `CygwinCheckResponse` → `WindowsCygwinCheckResponse`
   - `WslCheckResponse` → `WindowsWslCheckResponse`
   - add `LinuxCheckResponse`
   - remove `WindowsCheckResponse` as independent environment response

3. Rename settings model if practical:
   - `CygwinSettings` → `WindowsCygwinSettings`
   - keep fields `bash_path` and `tmux_path`

4. Keep `RuntimeCheckResponse` and `TmuxAvailabilityResponse` unchanged.

5. Do not add compatibility aliases for old `ShortcutHost` values.

### 2. Backend service updates

1. Update default shortcuts to use `host="windows_cygwin"`.
2. Update shortcut validation:
   - accept only `windows_cygwin`, `windows_wsl`, `linux`
   - allow only `windows_cygwin` for session startup in this stage
   - return clear `InvalidTerminalConfigError` for unimplemented startup hosts
3. Rename Cygwin-specific methods to Windows/Cygwin semantic names where useful:
   - `get_windows_cygwin_settings`
   - `update_windows_cygwin_settings`
   - `check_windows_cygwin`
4. Keep implementation behavior for Windows/Cygwin:
   - explicit bash path first
   - persisted bash path second
   - common Cygwin paths third
   - detect tmux through Cygwin bash
5. Add `check_windows_wsl`:
   - host available only on Windows
   - run default `wsl --status`, fallback to `wsl --version`
   - detect tmux inside default WSL with timeout
   - return unavailable reason instead of raising for missing WSL/tmux
   - do not read or write distro settings
6. Add `check_linux`:
   - on current Windows host, return host unavailable with clear reason
   - do not attempt Linux shell/tmux config on Windows
7. Update `resolve_shortcut_command` and `resolve_ttyd_executable` to use `windows_cygwin` host semantics.
8. Remove service methods that represent standalone Windows environment detection if no longer used.
9. Do not implement `screen` detection or persistence.

### 3. Backend API updates

1. Keep:
   - `GET /api/environment/ttyd/check`
   - `GET /api/terminal-settings`
   - `PUT /api/terminal-settings`
   - `POST /api/terminals/tmux/check`
2. Add shape-based endpoints:
   - `GET /api/environment/windows-cygwin/settings`
   - `PUT /api/environment/windows-cygwin/settings`
   - `GET /api/environment/windows-cygwin/check`
   - `GET /api/environment/windows-wsl/check`
   - `GET /api/environment/linux/check`
3. Remove or stop exposing old shape-confused endpoints:
   - `GET /api/environment/cygwin-settings`
   - `PUT /api/environment/cygwin-settings`
   - `GET /api/environment/cygwin/check`
   - `GET /api/environment/windows/check`
   - `GET /api/environment/wsl/check`
4. Ensure detection failures still return `200` with `available=false` inside response models unless request validation itself is invalid.

### 4. Frontend type and API updates

1. Update `ShortcutHost` type:

   ```ts
   export type ShortcutHost = 'windows_cygwin' | 'windows_wsl' | 'linux'
   ```

2. Rename or add response interfaces:
   - `WindowsCygwinSettings`
   - `WindowsCygwinCheckResponse`
   - `WindowsWslCheckResponse`
   - `LinuxCheckResponse`
3. Replace API client functions:
   - `getWindowsCygwinSettings`
   - `updateWindowsCygwinSettings`
   - `checkWindowsCygwin`
   - `checkWindowsWsl`
   - `checkLinux`
4. Remove frontend use of old `checkWindows`, `checkWsl`, `checkCygwin`, `getCygwinSettings`, `updateCygwinSettings` names.

### 5. EnvironmentManagement UI updates

1. Change tab model:

   ```ts
   type EnvironmentTab = 'windows_cygwin' | 'windows_wsl' | 'linux'
   ```

2. Default active tab: `windows_cygwin`.
3. Tab labels:
   - Windows/Cygwin
   - Windows/WSL
   - Linux
4. Keep `ttyd` panel outside tabs.
5. Windows/Cygwin tab:
   - show bash path input
   - show Cygwin bash status
   - show tmux status
   - persist Windows/Cygwin bash/tmux settings through new API
6. Windows/WSL tab:
   - show default WSL status
   - show WSL tmux status
   - no distro selector/input
7. Linux tab:
   - show unavailable on current Windows host
   - no Linux path/config inputs in this stage
8. Update disabled/enabled behavior:
   - Windows/Cygwin enabled
   - Windows/WSL enabled for detection
   - Linux enabled for status display, but unavailable on Windows
9. Update i18n keys and remove text implying standalone Windows environment.

### 6. Tests

1. Backend service tests:
   - default shortcuts use `windows_cygwin`
   - old `cygwin_tmux` is invalid as input
   - `windows_cygwin` command resolution still builds Cygwin tmux command
   - `windows_wsl` check returns WSL and tmux status
   - missing WSL or missing tmux returns unavailable, not exception
   - `linux` check returns unavailable on Windows host
   - unimplemented shortcut startup hosts return clear error
2. API tests:
   - new Windows/Cygwin settings get/put endpoints
   - new Windows/Cygwin check endpoint
   - new Windows/WSL check endpoint
   - new Linux check endpoint
   - old shape-confused endpoints are removed or no longer asserted
3. Session service tests:
   - session runtime / host is `windows_cygwin`
4. Frontend checks:
   - TypeScript typecheck catches old API/type names
   - lint catches unused old imports

## Verification plan

Run project-specific commands after implementation:

```text
uv run pytest tests/test_terminal_service.py tests/test_services.py tests/test_api.py
uv run ruff format --check src/termbridge/models.py src/termbridge/services.py src/termbridge/api.py tests/test_terminal_service.py tests/test_services.py tests/test_api.py
yarn --cwd frontend typecheck
yarn --cwd frontend lint
yarn --cwd frontend prettier --check src/components/EnvironmentManagement.vue src/api/sessions.ts src/types/sessions.ts src/i18n/locales/zh-CN.json src/i18n/locales/en-US.json
```

If frontend UI is changed, start the dev server and manually verify:

1. Environment page loads.
2. ttyd panel remains outside tabs.
3. Windows/Cygwin tab detects or reports bash/tmux status.
4. Windows/WSL tab reports default WSL/tmux status without distro UI.
5. Linux tab reports unavailable on Windows.

## Rollback

Because this intentionally breaks old API and old host values, rollback should be a code revert of this feature change rather than compatibility shims.

If implementation proves too broad, rollback to the current accepted requirement/spec and split into:

1. `ShortcutHost` rename and API shape cleanup.
2. Windows/WSL default tmux detection.
3. EnvironmentManagement UI reshape.

## Assumptions

- The current development host is Windows.
- `windows_cygwin` remains the only fully supported session startup path in this stage.
- WSL detection uses the default WSL distribution and no distro-specific settings.
- Existing persisted old terminal state may break; this is accepted.
- `screen` is not implemented in this stage.

## Risks

1. Breaking old `ShortcutHost` values may require users to recreate shortcuts or terminal state.
2. Removing old API endpoints will break any unupdated frontend calls.
3. WSL command behavior varies by installation state; timeout and unavailable responses are required.
4. Renaming models and API functions touches many tests and frontend imports.
5. Linux host support is intentionally incomplete and must not be presented as fully supported.

## Blockers

No blockers. The remaining open question about `screen` is explicitly out of scope for this plan.

## User review notes

- 2026-06-10：用户要求不做向后兼容和迁移，并进入计划阶段。
- 2026-06-10：用户指出原 `20260609-environment-runtime-management.md` 是旧设计，应保留；当前决策变更新开 rspv 文件承载。
