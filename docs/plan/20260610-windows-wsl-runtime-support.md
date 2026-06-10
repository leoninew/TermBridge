# Windows/WSL 运行环境支持计划

Review status: Accepted

当前：严格模式 / strict，实现阶段 / Implementation

## Requirement / Spec basis

- Requirement: `docs/requirement/20260610-windows-wsl-runtime-support.md`，Review status: Accepted。
- Spec: `docs/spec/20260610-windows-wsl-runtime-support.md`，Review status: Accepted。

本计划实现严格模式下的 Windows/WSL runtime provider 支持，重点包括：环境 readiness、默认运行环境配置、Windows 原生 ttyd 进入 WSL、主页无 ready 环境引导、Session 创建展示所有 host 且不可用禁用、删除 `Settings.use_wsl`。

## Implementation steps

### 1. 后端模型扩展

修改 `src/termbridge/models.py`：

1. 新增：
   - `EnvironmentReadiness = Literal["not_ready", "ready"]`
   - `EnvironmentSummary`
   - `EnvironmentListResponse`
   - `WindowsWslSettings`
   - `LinuxSettings`
2. 扩展 `TerminalSettings`：
   - 增加 `default_host: ShortcutHost = "windows_cygwin"`
3. 扩展 `UpdateTerminalSettingsRequest`：
   - 增加同样的 `default_host` 字段
4. 扩展 `WindowsCygwinSettings`：
   - `readiness`
   - `checked_at`
   - `last_error`
5. 扩展 `TerminalState`：
   - `windows_wsl_settings: WindowsWslSettings`
   - `linux_settings: LinuxSettings`
6. 泛化 `SessionRecord`：
   - 新增 `tmux_cleanup_command: list[str] | None = None`
   - 保留旧 `tmux_bash_path` 只到迁移实现必要时使用；新逻辑优先写 `tmux_cleanup_command`

不新增旧字段兼容层；现有 Pydantic 默认值负责缺字段时补默认。

### 2. 删除全局 `use_wsl`

修改：

- `src/termbridge/settings.py`
- `src/termbridge/services.py`
- `tests/test_services.py`

步骤：

1. 从 `Settings` 删除 `use_wsl` 字段。
2. 从 `SessionService._build_ttyd_command()` 删除：
   - `if self._settings.use_wsl: return ["wsl", *ttyd_command]`
3. 删除或改写 `test_service_wraps_ttyd_command_with_wsl_when_enabled`。
4. 测试构造 `Settings(...)` 时移除 `use_wsl` 参数。

### 3. 环境 summary API

修改 `src/termbridge/services.py`：

1. 新增 `TerminalService.list_environments() -> EnvironmentListResponse`。
2. 返回三类环境：
   - Windows/Cygwin
   - Windows/WSL
   - Linux
3. `available_on_host` 基于当前平台：
   - Windows host：Windows/Cygwin、Windows/WSL 为 true；Linux 为 false。
   - Linux host：Linux 为 true；Windows/Cygwin、Windows/WSL 为 false。
4. readiness 从持久化 settings 读取。
5. default_host 从 `TerminalSettings.default_host` 读取。

修改 `src/termbridge/api.py`：

1. 新增 `GET /api/environments`。
2. 返回 `EnvironmentListResponse`。

### 4. settings 更新逻辑

修改 `TerminalService.update_settings()`：

1. 保留 `ttyd_mode=explicit` 时必须有 `ttyd_path` 的校验。
2. 校验 `default_host` 是允许值。
3. 保存 `TerminalSettings(ttyd_mode, ttyd_path, default_host)`。

注意：默认运行环境可以选 `linux`，但前端会 disabled；后端创建 session 时仍需校验 host ready 和 supported。

### 5. provider 检测刷新 readiness

修改 `TerminalService.check_windows_cygwin()`：

1. 继续执行 host、bash、tmux 检测。
2. 如果 host、ttyd、bash、tmux 全部可用：
   - 保存 bash path、tmux path。
   - `readiness = "ready"`
   - `checked_at = utc_now()`
   - `last_error = None`
3. 如果任一关键项失败：
   - `readiness = "not_ready"`
   - `checked_at = utc_now()`
   - `last_error` 写入失败原因。
4. 用户手填 bash path 仍优先参与检测。

修改 `TerminalService.check_windows_wsl()`：

1. 检查 Windows host。
2. 检查 ttyd 可用。
3. 检查 `wsl` 可用。
4. 检查默认 WSL shell 可进入。
5. 检查 WSL 内 tmux：`command -v tmux && tmux -V`。
6. 尝试收集：
   - `wsl_path`
   - `wsl_version`
   - `default_distro`（如可通过命令稳定取得）
   - `automount_root`（可选，plan 实施时若命令复杂可先留空）
   - `tmux_path`
   - `tmux_version`
   - `shell_path`
7. 全部关键检查通过后写 `windows_wsl_settings.readiness = "ready"`。
8. 失败时写 `not_ready` 和 `last_error`。

修改 `TerminalService.check_linux()`：

1. Windows host 下返回 unavailable，并保持/写入 Linux `not_ready`。
2. Linux host 检测 shell/tmux，但本阶段不完整实现启动；是否标记 ready 以 spec 倾向为准：不作为可启动 host 暴露。

### 6. WSL path conversion

在 `TerminalService` 新增方法：

```python
def resolve_wsl_workspace_path(self, workspace: Path) -> str:
    ...
```

实现策略：

1. 首选执行：
   - `wsl wslpath -a <windows_workspace>`
2. 成功返回 stdout 第一行。
3. 失败抛出 `InvalidTerminalConfigError`，提示 workspace 无法转换到 WSL。
4. 本轮不实现 `/mnt/<drive>/...` fallback，避免猜测 WSL automount 配置。

### 7. provider runtime command 构造

重构 `TerminalService.resolve_shortcut_command()`：

1. 保留返回 shortcut 和 cleanup 上下文，但需要扩展返回值。
2. 建议新增内部模型或 tuple：

```python
ResolvedShortcutCommand = tuple[list[str], Shortcut, list[str] | None]
```

或在实现中先保持 tuple，但第三项改成 cleanup command；同步修改 `SessionService.create()`。

Windows/Cygwin：

1. 要求 `windows_cygwin_settings.readiness == "ready"`。
2. 继续使用 Cygwin bash：
   - `<bash> -lc 'cd <workspace> && exec tmux new-session -A -s <name> <command>'`
3. cleanup command：
   - `<bash> -lc 'tmux kill-session -t <name>'`

Windows/WSL：

1. 要求 `windows_wsl_settings.readiness == "ready"`。
2. 调用 `resolve_wsl_workspace_path(workspace)`。
3. runtime command：
   - `wsl --cd <wsl_workspace> sh -lc 'exec tmux new-session -A -s <name> <shortcut.command>'`
4. cleanup command：
   - `wsl sh -lc 'tmux kill-session -t <name>'`

Linux：

- 本阶段返回 `InvalidTerminalConfigError("Linux runtime is not supported yet")`。

### 8. SessionService 生命周期调整

修改 `SessionService.create()`：

1. 接收新的 resolved runtime command 和 cleanup command。
2. `ttyd_executable` 仍由 `TerminalService.resolve_ttyd_executable(shortcut.host, ...)` 返回。
3. 写入 `SessionRecord.tmux_cleanup_command`。
4. 如果仍保留 `tmux_bash_path`，只为 Cygwin 旧测试或过渡使用；新 cleanup 逻辑优先使用 `tmux_cleanup_command`。

修改 `_cleanup_tmux_session()`：

1. 如果 `session.tmux_cleanup_command` 存在，直接执行。
2. 否则 fallback 到旧 `tmux_bash_path` 逻辑，避免当前会话在开发期间无法删除。

修改 `_build_ttyd_command()`：

1. 删除 `use_wsl` 分支。
2. 暂时保留 `--cwd <windows_workspace>`。
3. WSL cwd 由 runtime command 的 `wsl --cd <wsl_workspace>` 负责。

### 9. 前端 API 和类型

修改 `frontend/src/types/sessions.ts`：

1. 新增：
   - `EnvironmentReadiness`
   - `EnvironmentSummary`
   - `EnvironmentListResponse`
   - `WindowsWslSettings`
   - `LinuxSettings`
2. 扩展 `TerminalSettings`：
   - `default_host: ShortcutHost`
3. 扩展 `WindowsCygwinSettings` readiness 字段。

修改 `frontend/src/api/sessions.ts`：

1. 新增 `listEnvironments()`。
2. 新增 `getWindowsWslSettings()` / `updateWindowsWslSettings()`，如果后端实现 settings endpoints。
3. 保持 check APIs。

### 10. 前端主页 readiness 引导

修改 `frontend/src/App.vue`：

1. 启动时并行加载 sessions 和 environments summary。
2. 保存 `environments` 状态。
3. 计算 `hasReadyEnvironment`。
4. 传给 `SessionList`。
5. 当从环境页检测成功后，返回主页需要刷新 environments；简单实现可在导航回 `/` 时调用刷新，或环境页检测成功 emit 事件。

修改 `frontend/src/components/SessionList.vue`：

1. 增加 props：
   - `environments`
   - `hasReadyEnvironment`
2. 如果没有 ready environment：
   - 创建按钮 disabled。
   - 空状态展示跳转环境配置页按钮。
3. 如果有 ready environment：
   - 现有 create 行为不变。
4. 加载 environments 时展示 spinner。

### 11. EnvironmentManagement 调整

修改 `frontend/src/components/EnvironmentManagement.vue`：

1. 页面加载时读取 settings、Windows/Cygwin settings、environment summary。
2. 不在主页自动检测；环境页可保留打开当前 tab 后检测，或改成手动按钮。按需求“跳过去检测”，倾向改为用户点击检测按钮。
3. 每个 tab 显示 readiness badge。
4. 检测按钮显示 spinner 并 disabled。
5. 检测成功后刷新 settings/environment summary。
6. ttyd path 保存时显示 loading。
7. Windows/WSL 展示 WSL/tmux 检测快照字段。

### 12. ShortcutManagement 调整

修改 `frontend/src/components/ShortcutManagement.vue`：

1. 加载 shortcuts 时同时加载 terminal settings 和 environments。
2. 新建 shortcut 默认 host = `settings.default_host`。
3. host select 展示：
   - Windows/Cygwin
   - Windows/WSL
   - Linux disabled
4. card label 使用 `shortcut.host` 映射。
5. loading 时显示 spinner。

### 13. SessionCreateForm 调整

修改 `frontend/src/components/SessionCreateForm.vue`：

1. 接收 environments 或自行加载 environments。
2. 展示所有 host：Windows/Cygwin、Windows/WSL、Linux。
3. not ready 或 unsupported host disabled。
4. shortcut 下拉按当前 host 过滤或标记 host：
   - 建议先按 host 过滤，只显示当前 host 的 shortcuts。
   - 如果当前 host 没有 shortcuts，显示提示去 shortcut 管理页创建。
5. submit loading 保持，后端返回前禁用按钮。

### 14. i18n 文案

修改：

- `frontend/src/i18n/locales/zh-CN.json`
- `frontend/src/i18n/locales/en-US.json`

新增文案：

- readiness: ready/not ready
- no ready environment empty state
- go to environment settings
- host labels
- disabled host reason
- checking/saving/loading
- WSL fields: wsl path/version/default distro/automount root/tmux path/version

### 15. README / 文档

修改 `README.md`：

1. 支持矩阵说明：
   - Windows/Cygwin：支持启动。
   - Windows/WSL：支持默认 WSL 启动。
   - Linux：本阶段检测/模型存在，但启动支持未完整实现。
2. 说明 Windows/WSL 使用 Windows 原生 ttyd，通过 `wsl --cd ... sh -lc ...` 进入默认 WSL。
3. 删除任何 `TERMBRIDGE_USE_WSL` 相关说明（如果存在）。

## Files to change

Backend:

- `src/termbridge/models.py`
- `src/termbridge/settings.py`
- `src/termbridge/services.py`
- `src/termbridge/api.py`
- `tests/test_terminal_service.py`
- `tests/test_services.py`
- `tests/test_api.py`

Frontend:

- `frontend/src/types/sessions.ts`
- `frontend/src/api/sessions.ts`
- `frontend/src/App.vue`
- `frontend/src/components/SessionList.vue`
- `frontend/src/components/EnvironmentManagement.vue`
- `frontend/src/components/ShortcutManagement.vue`
- `frontend/src/components/SessionCreateForm.vue`
- `frontend/src/i18n/locales/zh-CN.json`
- `frontend/src/i18n/locales/en-US.json`

Docs:

- `README.md`
- `docs/verification/20260610-windows-wsl-runtime-support.md`（Verification 阶段创建）

## Verification plan

Backend commands:

```bash
uv run ruff check .
uv run python -m mypy src tests
uv run python -m pytest tests/test_terminal_service.py tests/test_services.py tests/test_api.py
uv run python -m pytest
```

Frontend commands:

```bash
yarn --cwd frontend lint
yarn --cwd frontend typecheck
yarn --cwd frontend build
```

Manual/browser verification:

1. 启动 backend/frontend。
2. 首次进入主页，确认无 ready 环境时显示环境配置引导。
3. 进入环境页，确认 Windows/Cygwin、Windows/WSL、Linux readiness 初始为 not ready。
4. 检测 Windows/Cygwin，通过后 ready 并持久化。
5. 回主页，确认不自动重检且可创建 session。
6. 检测 Windows/WSL，通过后 ready，并展示 WSL/tmux 快照。
7. Session 创建表单展示所有 host，不可用 host disabled。
8. 创建 Windows/WSL session，确认 ttyd command 使用 Windows 原生 ttyd + `wsl --cd ... sh -lc ...`。
9. 删除 Windows/WSL session，确认执行 WSL tmux cleanup。
10. restart stopped Windows/WSL session，确认端口替换和原命令复用。

## Blockers

1. 本机 WSL/tmux 是否可用于手动验证未知；如果不可用，WSL runtime 只能通过单元测试验证命令构造。
2. `wsl --cd <path>` 对 Windows 侧启动参数和路径 quoting 的实际行为需要本机验证。

## Assumptions

1. 本阶段不支持 WSL distro 选择，使用默认 WSL。
2. 本阶段不完整实现 Linux runtime 启动。
3. `wslpath` 可用于真实路径转换；如果本机不可用，启动失败并提示重新检测/配置。
4. 不做旧 `use_wsl` 配置兼容。

## Risks

1. readiness 可能过期：通过启动失败后的重新检测引导缓解。
2. WSL path quoting 出错：用单元测试覆盖路径含空格。
3. Frontend 状态传播复杂：优先由 App 统一加载 environment summary 并下传。
4. SessionRecord 字段调整影响旧 session 删除：保留旧 `tmux_bash_path` fallback 以避免开发期旧会话无法删除。

## Rollback

1. 后端模型新增字段都有默认值，可通过恢复服务逻辑回到 Cygwin-only。
2. 若 WSL 启动不稳定，可以保留 readiness/API/UI，但暂时在后端拒绝 `windows_wsl` 启动。
3. 若前端改动风险过大，可以先保留环境页检测和 summary API，仅隐藏 WSL create 路径。

## User review notes

- 2026-06-10：用户在 Spec 阶段确认 Session 创建表单应展示所有 host，不可用 host 为 disabled 状态，而不是隐藏。
- 2026-06-10：用户要求开始 Plan。
