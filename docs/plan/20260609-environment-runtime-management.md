# 环境运行时管理实施计划

Review status: Accepted

当前：严格模式 / strict，实现 / Implementation

## Requirement basis

- Requirement: `docs/requirement/20260609-environment-runtime-management.md`
- Requirement status: Accepted

本计划按用户要求跳过独立 Spec 文档，直接进入 Plan。未决策 Open questions 已按建议采纳：

- `ttyd`：自动检测优先；不向用户暴露 auto/explicit 模式；检测成功后写入文本框并即时持久化；失败后用户可手动填写路径再检测。
- Cygwin bash：自动检测优先；失败或需要覆盖时允许手动指定路径并持久化。
- tmux：Cygwin 专属，只在 Cygwin tab 检测和展示。
- WSL：本阶段只做基础可用性检测，不管理具体 distro。
- Windows：本阶段只展示 host 基础可用性和 shell 候选状态，不做复杂配置。

## Implementation approach

新增一个环境运行时配置/检测层，放在现有 `TerminalService` 和 terminal state 持久化附近，避免引入新的存储文件。环境管理页负责：

1. 独立展示并管理 `ttyd` 检测路径：不向用户暴露 auto/explicit 模式；检测成功后把路径写入文本框并即时持久化。
2. 用 tabs 展示 Windows / Cygwin / WSL。
3. Cygwin tab 自动检测 bash 和 tmux，并允许保存 Cygwin bash path。
4. Windows/WSL tab 做最小基础检测展示。

## fastapi implementation steps

### 1. Models

文件：`src/cc_ttyd/models.py`

新增或扩展：

- 通用检测响应：
  - `RuntimeCheckResponse`
    - `available: bool`
    - `path: str | None`
    - `version: str | None`
    - `reason: str | None`
- Cygwin 设置：
  - `CygwinSettings`
    - `bash_mode: Literal["auto", "explicit"] = "auto"`
    - `bash_path: str | None = None`
- 环境设置：
  - `EnvironmentSettings`
    - `ttyd: TerminalSettings`
    - `cygwin: CygwinSettings`
- 检测响应：
  - `TtydCheckResponse` 可复用 `RuntimeCheckResponse`，或单独命名但字段相同。
  - `CygwinCheckResponse`
    - `bash: RuntimeCheckResponse`
    - `tmux: RuntimeCheckResponse | None`
  - `WindowsCheckResponse`
    - `host: RuntimeCheckResponse`
    - `shells: list[RuntimeCheckResponse]`
  - `WslCheckResponse`
    - `wsl: RuntimeCheckResponse`

扩展 `TerminalState`：

- `cygwin_settings: CygwinSettings = Field(default_factory=CygwinSettings)`
- 保留现有 `settings: TerminalSettings` 作为 ttyd settings，避免迁移破坏。

### 2. TerminalService detection methods

文件：`src/cc_ttyd/services.py`

新增方法：

- `check_ttyd(ttyd_path: str | None = None) -> RuntimeCheckResponse`
  - path provided：直接执行该 path 的版本命令。
  - no path：使用 `shutil.which("ttyd")`，找不到返回 unavailable。
  - 版本命令优先用 `--version`；如当前项目历史显示 ttyd 支持不同输出，可兼容 `-v`。
  - 失败/timeout/OSError 返回 `available=false` 和 reason，不抛 500。
- `get_cygwin_settings() -> CygwinSettings`
- `update_cygwin_settings(request: CygwinSettings) -> CygwinSettings`
  - `explicit` 模式要求 `bash_path` 非空。
- `check_cygwin(bash_path: str | None = None) -> CygwinCheckResponse`
  - explicit path 优先。
  - 否则优先使用持久化 Cygwin settings。
  - 如果仍是 auto，则尝试候选：
    - `shutil.which("bash")`
    - Windows 常见路径如 `D:/ProgramFiles/Cygwin64/bin/bash.exe`、`C:/cygwin64/bin/bash.exe`、`C:/cygwin/bin/bash.exe`
  - bash 检测命令：`[bash_path, "-lc", "command -v bash && bash --version | head -n 1"]`；实现时不要通过 shell pipe 在 Python 外拼危险输入，只把固定命令传给 bash `-lc`。
  - bash 可用后调用现有 `check_tmux(bash_path)`。
- `check_windows() -> WindowsCheckResponse`
  - 返回当前 host available；shell candidates 检查 `cmd`、`powershell`、`pwsh` 是否可找到。
- `check_wsl() -> WslCheckResponse`
  - 执行 `wsl --status`，失败再尝试 `wsl --version`；失败返回 unavailable。

调整现有逻辑：

- `resolve_terminal_command()` 中 Cygwin terminal 如果自身没有 `cygwin_bash_path`，可回退到持久化 Cygwin settings explicit path。
- `_validate_terminal()` 中 Cygwin terminal 的 bash path 要求改为：terminal 自身 path 或持久化 Cygwin settings path 至少一个可用。
- `resolve_ttyd_executable()` 的 explicit mode 保持使用 `TerminalSettings.ttyd_path`；auto mode 继续现有行为。

### 3. fastapi API

文件：`src/cc_ttyd/api.py`

新增 API：

- `GET /api/environment/ttyd/check`
  - query: `path?: string`
  - response: `RuntimeCheckResponse`
- `GET /api/environment/cygwin-settings`
  - response: `CygwinSettings`
- `PUT /api/environment/cygwin-settings`
  - body: `CygwinSettings`
  - response: `CygwinSettings`
- `GET /api/environment/cygwin/check`
  - query: `bash_path?: string`
  - response: `CygwinCheckResponse`
- `GET /api/environment/windows/check`
  - response: `WindowsCheckResponse`
- `GET /api/environment/wsl/check`
  - response: `WslCheckResponse`

保留现有：

- `GET /api/terminal-settings`
- `PUT /api/terminal-settings`
- `POST /api/terminals/tmux/check`

可在前端环境页继续复用 terminal settings API 来保存 ttyd settings。

### 4. fastapi tests

文件：`tests/test_terminal_service.py`

新增覆盖：

- ttyd auto 检测成功。
- ttyd auto 未找到。
- ttyd explicit path 检测成功。
- ttyd explicit path OSError/timeout 返回 unavailable。
- Cygwin auto 检测成功并触发 tmux 检测。
- Cygwin explicit path 检测成功。
- Cygwin unavailable 时 tmux 为 `None` 或 unavailable，不抛异常。
- Cygwin settings 持久化。
- Cygwin terminal resolution 回退到持久化 bash path。
- Windows check 返回 host/shell candidates。
- WSL check success/failure。

文件：`tests/test_api.py`

新增 API tests：

- ttyd check API。
- cygwin settings get/put。
- cygwin/windows/wsl check API。

## web implementation steps

### 1. Types and API

文件：

- `web/src/types/sessions.ts`
- `web/src/api/sessions.ts`

新增类型：

- `RuntimeCheckResponse`
- `CygwinSettings`
- `CygwinCheckResponse`
- `WindowsCheckResponse`
- `WslCheckResponse`

新增 API 函数：

- `checkTtyd(path?: string)`
- `getCygwinSettings()`
- `updateCygwinSettings(payload)`
- `checkCygwin(bashPath?: string)`
- `checkWindows()`
- `checkWsl()`

### 2. EnvironmentManagement layout

文件：`web/src/components/EnvironmentManagement.vue`

重构为：

1. 页面标题/说明。
2. 独立 `ttyd` panel：
   - 当前模式 `auto` / `explicit`。
   - 自动检测状态。
   - explicit path input。
   - 检测按钮。
   - 保存按钮。
   - path/version/reason 状态展示。
3. Tabs：Windows / Cygwin / WSL。
   - 可用原生 button tab，不必引入新组件。
   - tab state：`activeTab: 'windows' | 'cygwin' | 'wsl'`。

### 3. Cygwin tab

Cygwin tab 行为：

- on mount 或首次进入 tab：加载 Cygwin settings 并自动 check。
- 显示：
  - bash status/path/version/reason。
  - tmux status/path/version/reason。
- 输入：
  - bash mode auto/explicit。
  - explicit bash path。
- 操作：
  - 检测。
  - 保存。
- 保存后再次检测。

### 4. Windows / WSL tabs

Windows tab：

- 首次进入 tab 调用 `checkWindows()`。
- 展示 host status 和 shell candidates。

WSL tab：

- 首次进入 tab 调用 `checkWsl()`。
- 展示 available/path/version/reason。
- 不做 distro 管理。

### 5. i18n

文件：

- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`

新增文案：

- tabs labels。
- detection status。
- ttyd check/save/path/version/reason。
- Cygwin bash check/save/path/version/reason。
- tmux Cygwin-only label。
- Windows/WSL check status。
- error messages。

## Verification plan

fastapi:

- `uv run pytest tests/test_terminal_service.py tests/test_api.py`
- `uv run ruff format --check src/cc_ttyd/models.py src/cc_ttyd/services.py src/cc_ttyd/api.py tests/test_terminal_service.py tests/test_api.py`

web:

- `yarn --cwd web typecheck`
- `yarn --cwd web lint`
- `yarn --cwd web prettier --check web/src/components/EnvironmentManagement.vue web/src/api/sessions.ts web/src/types/sessions.ts web/src/i18n/locales/zh-CN.json web/src/i18n/locales/en-US.json`

Manual/browser:

1. 打开 `/environment`。
2. 验证 ttyd panel 自动检测并展示状态。
3. 输入 explicit ttyd path，检测并保存。
4. 切换 Cygwin tab，验证 bash/tmux 自动检测。
5. 输入 explicit Cygwin bash path，检测并保存。
6. 切换 Windows / WSL tab，验证基础检测展示。
7. 创建/启动 Cygwin terminal，确认未因 Cygwin settings 回退改动破坏。

## Risks and assumptions

- 不同 ttyd 版本的 version flag 可能不一致；实现需要兼容 `--version` / `-v`。
- Windows 上 `bash` 可能指向 Git Bash 而不是 Cygwin bash；自动检测需尽量识别路径或版本，但本阶段以用户可手动指定路径作为兜底。
- `head -n 1` 在 bash 内固定命令中可用；如果极端环境缺少 coreutils，version 解析可能失败但应返回 reason。
- 持久化 Cygwin bash path 后，会影响没有单独设置 bash path 的 Cygwin terminal；这是需求要求的后续使用语义。
- WSL check 只做基础可用性，不代表具体 distro 可用于 terminal 启动。

## Rollback

- 后端新增 API 可保留但前端隐藏入口。
- 若 Cygwin settings 回退影响 terminal 启动，可临时恢复 terminal 必须显式配置 `cygwin_bash_path` 的校验。
- `ttyd` explicit settings 已有旧 API 支持，保持向后兼容。
