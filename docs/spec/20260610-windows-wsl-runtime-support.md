# Windows/WSL 运行环境支持规格

Review status: Accepted

当前：严格模式 / strict，计划阶段 / Plan

## Requirement basis

基于 `docs/requirement/20260610-windows-wsl-runtime-support.md`：

1. Windows/Cygwin、Windows/WSL、Linux 都是 tmux-backed runtime provider 形态。
2. 本阶段让 Windows/WSL 从“仅检测”推进到“可配置、可选择、可启动”。
3. TermBridge 后端继续运行在 Windows，使用 Windows 原生 ttyd；ttyd command 进入默认 WSL。
4. 不使用 WSL 内 Linux 版 ttyd，不把 TermBridge 整体移动到 WSL。
5. 每个环境都有 readiness，默认 `not ready`；完整检查通过后标记 `ready` 并持久化。
6. 会话主页读取 readiness；有 ready 环境时不自动重检，没有 ready 环境时引导用户去环境配置页检测或手填路径。
7. 配置项需要支持用户切换默认运行环境。
8. Linux host 启动支持不在本阶段完整实现。

## Overview

本规格把“运行环境”从临时检测结果提升为持久化配置实体。后端在 `terminals.json` 中保存：

- 全局 terminal settings：ttyd 配置、默认运行环境。
- 三类环境配置：Windows/Cygwin、Windows/WSL、Linux。
- 每个环境的 readiness 与最近一次检测快照。

前端启动后，主页先读取环境 summary。如果没有 ready 环境，会话列表区域展示引导卡片，提示用户进入环境配置页检测或填写路径；如果存在 ready 环境，则保持当前会话列表和创建会话入口，不主动重新检测。

Windows/WSL session 启动时仍由 Windows 后端创建 Windows 原生 ttyd 进程。ttyd 的 command 使用 `wsl --cd <wsl_workspace> sh -lc <tmux command>` 进入默认 WSL，并在 WSL 内创建或附加 tmux session。

## Design decisions

### 1. 运行环境 readiness 模型

新增统一环境状态：

```python
EnvironmentReadiness = Literal["not_ready", "ready"]
```

每个 provider 设置结构都包含：

- `readiness`
- `checked_at`
- `last_error`
- `last_check` 或 provider-specific check snapshot

默认值：

- `readiness = "not_ready"`
- `checked_at = None`
- `last_error = None`

完整检查全部通过时：

- 写入检测到的路径/version 等快照。
- 将该 provider 标记为 `ready`。
- 保存 `checked_at`。

重新检测失败时：

- 将该 provider 标记为 `not_ready`。
- 保存失败原因。
- 保留或清空旧检测路径需要在 Plan 阶段细化；倾向保留用户手填配置，刷新检测快照。

### 2. TerminalSettings 扩展默认运行环境

扩展 `TerminalSettings`：

```python
class TerminalSettings(BaseModel):
    ttyd_mode: Literal["auto", "explicit"] = "auto"
    ttyd_path: str | None = None
    default_host: ShortcutHost = "windows_cygwin"
```

理由：默认运行环境是用户配置项，不应只保存在前端表单状态。它影响 shortcut 创建默认值和创建会话体验。

### 3. Provider-specific settings

保留现有 `WindowsCygwinSettings`，增加 readiness 和检测快照字段：

```python
class WindowsCygwinSettings(BaseModel):
    readiness: EnvironmentReadiness = "not_ready"
    bash_path: str | None = None
    tmux_path: str | None = None
    checked_at: datetime | None = None
    last_error: str | None = None
```

新增 `WindowsWslSettings`：

```python
class WindowsWslSettings(BaseModel):
    readiness: EnvironmentReadiness = "not_ready"
    wsl_path: str | None = None
    wsl_version: str | None = None
    default_distro: str | None = None
    automount_root: str | None = None
    tmux_path: str | None = None
    tmux_version: str | None = None
    shell_path: str | None = None
    checked_at: datetime | None = None
    last_error: str | None = None
```

新增 `LinuxSettings`：

```python
class LinuxSettings(BaseModel):
    readiness: EnvironmentReadiness = "not_ready"
    shell_path: str | None = None
    tmux_path: str | None = None
    checked_at: datetime | None = None
    last_error: str | None = None
```

Linux 本阶段主要用于统一环境列表和 unavailable 状态，不完整实现 session 启动。

### 4. 环境 summary API

新增统一读取接口：

```text
GET /api/environments
```

返回：

```json
{
  "default_host": "windows_cygwin",
  "environments": [
    {
      "host": "windows_cygwin",
      "label": "Windows/Cygwin",
      "readiness": "ready",
      "available_on_host": true,
      "checked_at": "...",
      "last_error": null
    },
    {
      "host": "windows_wsl",
      "label": "Windows/WSL",
      "readiness": "not_ready",
      "available_on_host": true,
      "checked_at": null,
      "last_error": null
    },
    {
      "host": "linux",
      "label": "Linux",
      "readiness": "not_ready",
      "available_on_host": false,
      "checked_at": null,
      "last_error": "Linux environment is unavailable on this host"
    }
  ]
}
```

用途：

- 主页判断是否有 ready 环境。
- shortcut 创建表单决定默认 host 和可选 host。
- 环境配置页展示 readiness badge。

### 5. 检测接口负责刷新 readiness

现有检测接口保留：

- `GET /api/environment/windows-cygwin/check`
- `GET /api/environment/windows-wsl/check`
- `GET /api/environment/linux/check`
- `GET /api/environment/ttyd/check`

调整语义：

- provider 检测接口不仅返回检测结果，也会更新对应 settings 的 readiness 和检测快照。
- `ttyd` 是全局依赖，不单独作为 provider；provider ready 的判定需要包含 ttyd 可用性。

Windows/Cygwin ready 条件：

1. 当前 host 是 Windows。
2. ttyd 可用。
3. Cygwin bash 可用。
4. Cygwin 内 tmux 可用。

Windows/WSL ready 条件：

1. 当前 host 是 Windows。
2. ttyd 可用。
3. `wsl` 可用。
4. 默认 WSL 可进入 shell。
5. WSL 内 tmux 可用。
6. workspace path conversion 能通过 `wslpath` 或 `wsl --cd` 支持的路径策略完成。

Linux ready 条件：

- 当前阶段在 Windows host 下永远 not ready。
- Linux host 上可检测 shell/tmux，但 session 启动不在本阶段完整实现；是否允许 ready 留到 Linux host 支持阶段。

### 6. Windows/WSL 路径转换

首选策略：

```text
wsl wslpath -a <windows_path>
```

理由：

- 当前常见结果是 `/mnt/<drive>/...`。
- 但 WSL automount root 可以通过 `/etc/wsl.conf` 改变。
- 使用 `wslpath` 可以让 WSL 返回当前环境真实路径，TermBridge 不复刻 WSL 路径规则。

fallback：

- Plan 阶段决定是否提供 `/mnt/<drive>/...` deterministic fallback。
- 如果 fallback 存在，只用于盘符路径，并需要测试路径含空格。

### 7. Windows/WSL 启动命令

目标命令形态：

```text
ttyd --writable --port <port> [--cwd <windows_workspace>] wsl --cd <wsl_workspace> sh -lc '<tmux command>'
```

WSL 内 tmux command：

```sh
exec tmux new-session -A -s '<tmux_session_name>' '<shortcut.command>'
```

`--cwd` 策略：

- `wsl --cd <wsl_workspace>` 是 Linux 侧 cwd 的主路径。
- Windows ttyd 的 `--cwd <windows_workspace>` 是否保留，Plan 阶段通过本地验证决定。
- 如果保留，它只服务 Windows 侧 ttyd 进程，不作为 WSL cwd 语义来源。

### 8. SessionRecord 生命周期字段

现有 `tmux_bash_path` 命名是 Cygwin-specific，不适合 WSL。新增更通用字段，或在计划阶段改名：

```python
class SessionRecord(BaseModel):
    host: ShortcutHost | None = None
    session_persistence: Literal["none", "tmux"] = "none"
    tmux_session_name: str | None = None
    tmux_cleanup_command: list[str] | None = None
```

设计倾向：

- restart 使用原始 `session.command` 替换端口即可，不重新构造 runtime command。
- delete 使用 `tmux_cleanup_command` 执行清理，避免根据 host 分支重新推导 cleanup 方式。

Cygwin cleanup command：

```text
<cygwin_bash> -lc 'tmux kill-session -t <name>'
```

WSL cleanup command：

```text
wsl sh -lc 'tmux kill-session -t <name>'
```

### 9. 删除全局 `use_wsl`

`Settings.use_wsl` 当前会包裹整个 ttyd command，和 provider-based host 语义冲突。

设计：

- 删除 `Settings.use_wsl` 字段。
- 删除 `_build_ttyd_command()` 中根据 `self._settings.use_wsl` 包裹 `wsl` 的逻辑。
- 删除或改写依赖 `use_wsl=True` 的测试。
- 不新增兼容 shim，也不保留 `TERMBRIDGE_USE_WSL` 配置语义。

理由：WSL 支持必须由 shortcut/provider host 显式决定，而不是全局开关影响所有 ttyd command。全局开关会让 Windows/Cygwin、Windows/WSL、Linux 的 provider 语义互相污染。

### 10. 前端 loading 状态

前端涉及环境列表、检测、settings 保存、shortcut 加载和 session 创建等异步操作时，需要提供必要 loading 反馈。

设计：

- 主页加载 sessions 和 environments summary 时显示轻量 spinner。
- 环境配置页执行 provider 检测时，在对应按钮或状态区域显示 spinner，避免用户重复点击。
- 保存 ttyd、Cygwin bash、默认运行环境等配置时显示保存中状态。
- shortcut 管理页加载 settings/environments/shortcuts 时显示 loading 状态。
- session 创建提交时保留当前 submit loading，并在后端返回前禁用提交按钮。

加载反馈使用现有图标体系中的 `Loader2` 或同等 spinner，不引入新的 UI 库。

### 11. 前端主页引导

`App.vue` 启动时同时读取：

- sessions
- environments summary

`SessionList.vue` 增加 prop：

- `environments`
- `hasReadyEnvironment`

当 `sessions.length === 0` 且 `hasReadyEnvironment === false`：

- 展示无可用环境提示。
- 提供按钮跳转 `/environment`。
- 创建会话按钮 disabled 或隐藏。

当有 ready 环境：

- 保持现有空会话提示和创建入口。
- 不自动触发环境检测。

### 11. 环境配置页交互

`EnvironmentManagement.vue` 调整：

- 页面加载时读取 settings、provider settings、environment summary。
- 不再默认自动检测所有 provider。
- 每个 provider tab 展示 readiness badge。
- 用户点击检测后执行完整检查；通过则保存 ready，失败则保存 not ready 和 reason。
- Windows/Cygwin 仍允许手填 Cygwin bash path。
- ttyd 仍允许 auto/explicit path，并作为 provider 检查的共同依赖。
- Windows/WSL 展示检测到的 wsl path/version、default distro、automount root、tmux path/version。

### 12. Shortcut 管理

`ShortcutManagement.vue` 调整：

- 创建表单 host 默认值来自 `TerminalSettings.default_host`。
- host select 展示 Windows/Cygwin 和 Windows/WSL。
- Linux 本阶段可显示 disabled 或不显示；倾向显示 disabled，让环境模型完整但避免误以为可启动。
- shortcut card 使用 `shortcut.host` 显示 label，不再硬编码 Windows/Cygwin。

### 13. Session 创建

`SessionCreateForm.vue` 调整：

- 表单展示所有 host：Windows/Cygwin、Windows/WSL、Linux。
- host 选择项根据 environment readiness 决定是否可用；not ready 或本阶段不可启动的 host 以 disabled 状态展示，不隐藏。
- shortcut 下拉展示 shortcut host label，并与当前 host 选择联动。
- 如果 shortcut host 对应 environment not ready，则禁用或标记该 shortcut。
- 如果没有 ready environment，不进入 create form，而由主页空状态引导。

后端 `create_session` 仍做最终校验：

- shortcut host 必须 ready。
- WSL command 必须可构造。
- 失败返回 400 明确错误。

## Affected components

### Backend

- `src/termbridge/models.py`
  - 新增 readiness、environment summary、WindowsWslSettings、LinuxSettings、检测快照字段。
  - 扩展 `TerminalSettings.default_host`。
  - 泛化 session cleanup 字段。
- `src/termbridge/repositories.py`
  - 继续用 `TerminalState` 存储 settings；无需新增文件。
- `src/termbridge/services.py`
  - provider readiness 管理。
  - WSL 检测增强。
  - WSL path conversion。
  - WSL runtime command 构造。
  - tmux cleanup 泛化。
  - 删除 `Settings.use_wsl` 和对应 command 包裹逻辑。
- `src/termbridge/api.py`
  - 新增 `GET /api/environments`。
  - 可能新增 provider settings endpoints：`GET /api/environment/windows-wsl/settings`。

### Frontend

- `frontend/src/types/sessions.ts`
  - 新增 environment summary、readiness、provider settings/check snapshot 类型。
- `frontend/src/api/sessions.ts`
  - 新增 environment summary/settings API。
- `frontend/src/App.vue`
  - 加载 environments，传递 readiness 给 session list。
- `frontend/src/components/SessionList.vue`
  - 无 ready 环境时展示跳转环境配置页的空状态。
- `frontend/src/components/EnvironmentManagement.vue`
  - readiness badge、手动检测刷新、settings 展示。
- `frontend/src/components/ShortcutManagement.vue`
  - host select 和 host label。
- `frontend/src/components/SessionCreateForm.vue`
  - shortcut host label 和 not-ready shortcut 处理。
- `frontend/src/i18n/locales/*.json`
  - 新增 readiness、环境引导、WSL 检测字段文案。

### Tests

- `tests/test_terminal_service.py`
  - readiness 默认值。
  - Cygwin 检测通过后 ready。
  - WSL 检测通过后 ready。
  - WSL path conversion。
  - unsupported/not-ready host 错误。
- `tests/test_services.py`
  - Windows/WSL session command。
  - WSL cleanup command。
  - restart 使用原 command 替换端口。
- `tests/test_api.py`
  - `/api/environments`。
  - settings/check API readiness 刷新。
- Frontend lint/typecheck 覆盖新增类型。

## Interfaces

### Backend models

```python
EnvironmentReadiness = Literal["not_ready", "ready"]

class EnvironmentSummary(BaseModel):
    host: ShortcutHost
    label: str
    readiness: EnvironmentReadiness
    available_on_host: bool
    checked_at: datetime | None = None
    last_error: str | None = None

class EnvironmentListResponse(BaseModel):
    default_host: ShortcutHost
    environments: list[EnvironmentSummary]
```

### APIs

```text
GET /api/environments
GET /api/terminal-settings
PUT /api/terminal-settings
GET /api/environment/windows-cygwin/settings
PUT /api/environment/windows-cygwin/settings
GET /api/environment/windows-cygwin/check
GET /api/environment/windows-wsl/settings
PUT /api/environment/windows-wsl/settings
GET /api/environment/windows-wsl/check
GET /api/environment/linux/check
```

### Command shapes

Cygwin runtime command remains:

```text
<cygwin_bash> -lc 'cd <cygwin_workspace> && exec tmux new-session -A -s <name> <command>'
```

WSL runtime command:

```text
wsl --cd <wsl_workspace> sh -lc 'exec tmux new-session -A -s <name> <command>'
```

WSL path conversion:

```text
wsl wslpath -a <windows_workspace>
```

## Technical questions

1. `tmux_cleanup_command` 是否直接持久化在 `SessionRecord`，还是按 host 在 delete 时重新构造？
   - 倾向持久化 cleanup command，减少 delete 时 provider 分支。
2. WSL path conversion 是否需要 fallback 到 `/mnt/<drive>/...`？
   - 倾向先只使用 `wslpath`，fallback 需在 Plan 阶段决定。
3. Windows ttyd `--cwd` 在 WSL session 中是否保留？
   - 需要本地验证。
4. Linux provider 是否应该在 Linux host 检测通过后标记 ready？
   - 本阶段不完整支持 Linux 启动，倾向即使检测通过也不在 UI 中作为可启动 host 暴露。
5. `GET /api/environment/windows-wsl/check` 是否应有 `persist=true/false` 参数？
   - 倾向检测页调用默认持久化；纯诊断如未来需要再扩展。

## Risks

1. **readiness 过期**：用户卸载 tmux 或 WSL 状态变化后，主页仍认为 ready。缓解：启动失败时给出重新检测引导；用户可手动重新检测。
2. **路径转换失败**：workspace 不在 WSL 可访问路径内，`wslpath` 失败。缓解：返回明确错误，不创建 running session。
3. **命令 quoting**：workspace、session name、shortcut command 含空格或特殊字符时可能失败。缓解：集中构造 shell command，测试路径含空格。
4. **旧字段命名**：`tmux_bash_path` 与 WSL 不匹配。缓解：计划阶段泛化 cleanup 字段，不继续扩展 Cygwin-specific 命名。
5. **UI 自动检测行为变化**：环境页当前 mounted 会自动检测。新设计不对主页自动重检，但环境页是否自动检测当前 tab 需要谨慎。倾向：环境页可显示状态，检测由按钮触发。
6. **Linux 表达误导**：UI 展示 Linux 但本阶段不可启动。缓解：明确 disabled/unavailable 文案。

## Alternatives

### 方案 A：Windows 原生 ttyd + command 进入 WSL（选定）

优点：复用当前 Windows 端口、PID、URL、session record 生命周期；改动集中在 runtime command 和 cleanup。

缺点：需要处理 Windows path 到 WSL path 转换和 shell quoting。

### 方案 B：Windows 后端启动 WSL 内 Linux ttyd（不选）

优点：WSL 内 cwd、tmux、shell 都是 Linux 原生语义。

不选理由：Windows 后端需要跨边界管理 WSL 内 ttyd 进程、端口、健康检查和 URL；浏览器从 Windows 访问 WSL 端口也受 localhost forwarding、防火墙/VPN、WSL 版本影响。

### 方案 C：TermBridge 整体运行在 WSL（不选）

优点：整体就是 Linux host 语义，路径和 ttyd 都统一。

不选理由：这已经是 Linux host 支持，不是 Windows/WSL provider 支持；会同时改变安装位置、依赖、路径模型、网络模型和用户使用方式。

### 方案 D：每次进入主页都自动检测环境（不选）

优点：状态实时。

不选理由：启动慢、可能反复触发 WSL/Cygwin 子进程、用户已确认 ready 后没有必要每次打扰。选定方案是持久化 readiness，失败后再引导重检。

## User review notes

- 2026-06-10：用户要求从标准模式切换到严格模式，并开始 Spec。
