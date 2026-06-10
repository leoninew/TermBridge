# RSPV 环境模型调整规格

Review status: Accepted

当前：严格模式 / strict，计划阶段 / Plan

## Requirement basis

- Requirement: `docs/requirement/20260610-rspv-environment-model.md`
- Requirement status: Accepted

本规格覆盖对环境模型的重新定义：从 `Windows / Cygwin / WSL` 三个同层级环境，调整为三种 tmux-backed 环境形态：

- Windows/Cygwin
- Windows/WSL
- Linux

## Overview

环境管理应围绕“环境形态 + tmux-backed session persistence”建模。Windows 是宿主平台，不是独立 tmux 环境；Cygwin 和 WSL 是 Windows 宿主上的 provider；Linux 是原生 Linux 宿主上的 provider。

当前阶段的目标不是实现所有平台的完整能力，而是让 UI、API、类型和 session 启动模型表达正确：

1. 当前 Windows 宿主下，Windows/Cygwin 和 Windows/WSL 可以检测。
2. 当前 Windows 宿主下，Linux 必须明确 unavailable。
3. Windows/WSL 不保存 distro 名称，只检测默认 WSL。
4. Linux 宿主支持不完整实现，只保留模型和不可用状态语义。
5. `ShortcutHost` 立即收敛到 `windows_cygwin` / `windows_wsl` / `linux`。
6. `screen` 作为未来可选 session persistence backend 的 open question 保留，不进入本阶段实现。

## Design decisions

### 1. Environment shape naming

使用三种环境形态标识：

- `windows_cygwin`
- `windows_wsl`
- `linux`

UI 展示名分别为：

- Windows/Cygwin
- Windows/WSL
- Linux

后端模型、前端类型、shortcut host 和 session runtime 应使用相同语义，避免继续暴露 `windows`、`cygwin`、`wsl` 作为并列环境。

### 2. ShortcutHost migration semantics

`ShortcutHost` 从旧值：

- `windows`
- `cygwin`
- `wsl`
- `cygwin_tmux`

调整为新值：

- `windows_cygwin`
- `windows_wsl`
- `linux`

当前已有默认快捷方式应使用 `windows_cygwin`。现阶段 session persistence 仍固定为 `tmux`，不新增 `screen`。

兼容策略：

- 不做向后兼容和迁移。
- 代码内新建、更新和默认 shortcut 只使用新值。
- 旧 `cygwin_tmux`、`windows`、`cygwin`、`wsl` 不再作为合法公开输入。
- 已持久化的旧 `.termbridge/terminals.json` 可在本阶段失效；后续保存会使用新模型。

### 3. Runtime detection API shape

现有 API 可以保留资源路径，但语义需要改名或新增形态化接口。推荐使用形态化路径：

- `GET /api/environment/ttyd/check`
- `GET /api/environment/windows-cygwin/settings`
- `PUT /api/environment/windows-cygwin/settings`
- `GET /api/environment/windows-cygwin/check`
- `GET /api/environment/windows-wsl/check`
- `GET /api/environment/linux/check`

兼容取舍：

- 不保留旧 `/api/environment/cygwin-*`、`/api/environment/windows/check` 或 `/api/environment/wsl/check` 作为兼容入口。
- 前端迁移到新形态化路径。
- 新文档和新类型不再以 `WindowsCheckResponse` 表达独立 Windows 环境。

### 4. Detection response models

保留通用检测结构：

```python
RuntimeCheckResponse:
  available: bool
  path: str | None
  version: str | None
  reason: str | None
```

新增或重命名形态响应：

```python
WindowsCygwinCheckResponse:
  host: RuntimeCheckResponse
  bash: RuntimeCheckResponse
  tmux: RuntimeCheckResponse | None

WindowsWslCheckResponse:
  host: RuntimeCheckResponse
  wsl: RuntimeCheckResponse
  tmux: RuntimeCheckResponse | None

LinuxCheckResponse:
  host: RuntimeCheckResponse
  shell: RuntimeCheckResponse | None
  tmux: RuntimeCheckResponse | None
```

当前 Windows 宿主下：

- `WindowsCygwinCheckResponse.host.available == true`
- `WindowsWslCheckResponse.host.available == true`
- `LinuxCheckResponse.host.available == false`，reason 说明当前宿主不是 Linux

### 5. Windows/Cygwin behavior

Windows/Cygwin 继续使用现有 Cygwin bash path 设置能力，但名称应随形态收敛：

- 当前 `CygwinSettings` 可重命名为 `WindowsCygwinSettings`。
- 字段保留：`bash_path`、`tmux_path`。
- 检测流程：手动输入路径优先；其次持久化 path；最后尝试常见 Cygwin bash 候选。
- bash 可用后，在 Cygwin 环境内检测 tmux。
- session 启动使用 Cygwin bash 执行 tmux command。

### 6. Windows/WSL behavior

Windows/WSL 本阶段只检测默认 WSL 环境，不保存 distro：

- 检测 Windows host 是否可用。
- 运行默认 `wsl` 检查 WSL 状态或版本。
- 在默认 WSL 中检测 `tmux`，例如通过 `wsl sh -lc 'command -v tmux && tmux -V'`。
- 检测失败返回 unavailable，不抛 500。
- 不提供 distro input、dropdown 或持久化字段。

### 7. Linux behavior

Linux 形态在当前 Windows 宿主下只展示 unavailable：

- 后端检测 `os.name` / `platform.system()`。
- 非 Linux：返回 host unavailable，reason 说明当前宿主不支持 Linux provider。
- Linux 宿主上的完整 shell/tmux 检测可保留接口形态，但本阶段不要求完整验证。

### 8. ttyd remains independent

`ttyd` 仍作为环境导航外的独立配置：

- 自动检测 PATH 中 `ttyd`。
- 用户可填显式路径。
- 检测成功后可持久化并供后续 session 启动使用。
- 不把 ttyd 归属到 Windows/Cygwin、Windows/WSL 或 Linux 任一形态。

### 9. screen remains unresolved

`screen` 只作为 open question 保留：

- 不新增 `session_persistence = "screen"`。
- 不新增 screen 检测 API。
- 不在 UI 中展示 screen 选择。
- 后续如果支持，应先抽象 `tmux-backed` 为 `persistence backend`，再让环境形态选择 backend。

## Affected components

### Backend

- `src/termbridge/models.py`
  - 重命名或替换 `ShortcutHost` 值。
  - 新增/重命名 Windows/Cygwin、Windows/WSL、Linux 检测响应模型。
  - 将 `CygwinSettings` 收敛为 `WindowsCygwinSettings`，或保留内部名但 API 层使用新语义。
- `src/termbridge/services.py`
  - 默认 shortcuts 使用 `windows_cygwin`。
  - shortcut validation 接受新 host 值。
  - session command resolution 以 `windows_cygwin` 为当前可启动实现。
  - 新增默认 WSL tmux 检测。
  - 新增 Linux unavailable 检测。
  - 不兼容旧 `cygwin_tmux` host 值。
- `src/termbridge/api.py`
  - 增加或重命名环境形态 API。
  - 移除前端对独立 Windows check 的依赖。
  - 移除旧 Cygwin/Windows/WSL 环境 API。

### Frontend

- `frontend/src/types/sessions.ts`
  - `ShortcutHost` 改为 `windows_cygwin | windows_wsl | linux`。
  - 新增 Windows/Cygwin、Windows/WSL、Linux 检测响应类型。
- `frontend/src/api/sessions.ts`
  - 新增/改名形态 API client。
- `frontend/src/components/EnvironmentManagement.vue`
  - tabs 改为 Windows/Cygwin、Windows/WSL、Linux。
  - Linux tab 在 Windows 宿主下展示 unavailable。
  - Windows/WSL tab 展示默认 WSL 和 tmux 状态，不展示 distro 配置。
- `frontend/src/i18n/locales/zh-CN.json`
- `frontend/src/i18n/locales/en-US.json`
  - 更新环境形态文案。

### Tests

- `tests/test_terminal_service.py`
  - 默认 shortcut host 从 `cygwin_tmux` 改为 `windows_cygwin`。
  - 覆盖旧 `cygwin_tmux` 不再作为合法 host。
  - 覆盖 Windows/WSL 默认 WSL tmux 检测。
  - 覆盖 Windows 宿主下 Linux unavailable。
- `tests/test_services.py`
  - session runtime / host 期望改为 `windows_cygwin`。
- `tests/test_api.py`
  - 覆盖新环境形态 API。

## Interfaces

### ShortcutHost

```python
ShortcutHost = Literal["windows_cygwin", "windows_wsl", "linux"]
```

当前阶段可启动 host：

- `windows_cygwin`

当前阶段可检测但不一定可启动 host：

- `windows_wsl`
- `linux`

如果 shortcut 创建时选择未实现启动的 host，应返回明确 `InvalidTerminalConfigError`，而不是静默降级到 Windows/Cygwin。

### Environment API

推荐最终前端使用：

```text
GET /api/environment/ttyd/check?path=
GET /api/environment/windows-cygwin/settings
PUT /api/environment/windows-cygwin/settings
GET /api/environment/windows-cygwin/check?bash_path=
GET /api/environment/windows-wsl/check
GET /api/environment/linux/check
POST /api/terminals/tmux/check
```

`POST /api/terminals/tmux/check` 当前仍可保留给 Windows/Cygwin 的手动 tmux 检测；如后续抽象 persistence backend，再统一命名。

## Technical questions

1. `windows_wsl` 是否允许创建 shortcut？
   - 建议：类型允许，但 session 启动如未实现应返回明确错误；若计划阶段决定实现 WSL tmux 启动，则再放开。
2. Linux host 上的完整检测是否要写测试？
   - 本阶段只要求 Windows host 下 Linux unavailable；Linux host 完整检测可以单元测试 mock，但不作为真实环境验证要求。

## Risks

1. `ShortcutHost` 改名会使已有持久化旧 host 值失效；这是本阶段接受的破坏性变化。
2. API 改名会破坏旧前端调用；应同步更新类型、API client 和组件。
3. WSL 默认环境可能不存在、未初始化或命令阻塞；检测必须有 timeout 并返回 unavailable。
4. Linux host 支持不完整，文案必须清楚说明当前阶段只保证 Windows 宿主下不可用状态。
5. 如果过早引入 `screen`，会扩大本阶段范围；本阶段应明确不实现。

## Alternatives considered

1. 继续保留 Windows / Cygwin / WSL tabs。
   - 放弃：这会继续混淆宿主平台和环境 provider。
2. 立即抽象为 environment shape × persistence backend。
   - 放弃：虽然能容纳 `screen`，但会显著扩大范围。
3. 不重命名 `ShortcutHost`，只改 UI 文案。
   - 放弃：用户已明确要求立即重命名，且代码模型需要与需求语义一致。

## User review notes

- 2026-06-10：用户确认不做向后兼容和迁移；旧 `ShortcutHost`、旧环境 API 和旧 terminal state 可破坏。
