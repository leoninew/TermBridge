# RSPV 环境模型调整验证

Review status: Accepted

当前：严格模式 / strict，验证阶段 / Verification

## Requirement alignment

- 环境形态已收敛为 Windows/Cygwin、Windows/WSL、Linux。
- `ttyd` 保持为独立配置区域。
- `ShortcutHost` 已改为 `windows_cygwin` / `windows_wsl` / `linux`。
- Windows/Cygwin 保留 bash path 与 tmux 检测能力。
- Windows/WSL 只检测默认 WSL 与其中的 tmux，不保存 distro。
- Linux 在非 Linux 宿主返回 unavailable。
- 不实现 `screen`，继续作为 open question。
- 不保留旧 host/API/state 的兼容迁移。

## Spec alignment

- 后端模型新增/使用 `WindowsCygwinCheckResponse`、`WindowsWslCheckResponse`、`LinuxCheckResponse`。
- 后端 API 使用形态化 endpoint：
  - `/api/environment/windows-cygwin/settings`
  - `/api/environment/windows-cygwin/check`
  - `/api/environment/windows-wsl/check`
  - `/api/environment/linux/check`
- 前端类型、API client、环境管理页和快捷方式 host 文案已迁移到新命名。
- `windows_cygwin` 是当前唯一可启动 host；`windows_wsl` / `linux` 可建模和检测，但未实现 session startup。

## Plan alignment

实际改动覆盖计划中的后端模型、服务、API、前端类型、API client、环境页面、i18n 和测试。

## What changed

- 后端环境模型从旧 `cygwin_tmux` / standalone Windows-Cygwin-WSL 语义迁移到 `windows_cygwin` / `windows_wsl` / `linux`。
- 新增默认 WSL tmux 检测和 Linux unavailable 检测。
- 环境管理 UI 改为三类环境形态 tab。
- 快捷方式 UI 默认 host 改为 Windows/Cygwin。
- 测试迁移到新模型和新 endpoint，并覆盖 WSL/Linux 检测形态。

## Acceptance

- [x] 环境管理页使用 Windows/Cygwin、Windows/WSL、Linux 导航。
- [x] ttyd 配置保持在环境导航外。
- [x] Windows/Cygwin 展示 bash/tmux 检测和设置。
- [x] Windows/WSL 展示默认 WSL/tmux 检测，不包含 distro 设置。
- [x] Linux 在非 Linux 宿主返回 unavailable。
- [x] API 不再使用旧环境 endpoint。
- [x] `ShortcutHost` 使用新值。
- [x] `screen` 未进入实现范围。

## Commands

- `uv run pytest tests/test_terminal_service.py tests/test_services.py tests/test_api.py`
  - 结果：失败于 Windows/Cygwin 下的 `uv trampoline failed to canonicalize script path`。
- `uv run python -m pytest tests/test_terminal_service.py tests/test_services.py tests/test_api.py`
  - 结果：37 passed, 1 warning。
- `uv run python -m ruff format src/termbridge/services.py tests/test_terminal_service.py tests/test_api.py`
  - 结果：3 files reformatted。
- `uv run python -m ruff format --check src/termbridge/models.py src/termbridge/services.py src/termbridge/api.py tests/test_terminal_service.py tests/test_services.py tests/test_api.py`
  - 结果：6 files already formatted。
- `yarn --cwd web typecheck`
  - 结果：通过。
- `yarn --cwd web lint`
  - 结果：通过。
- `yarn --cwd web prettier --check src/components/EnvironmentManagement.vue src/api/sessions.ts src/types/sessions.ts src/i18n/locales/zh-CN.json src/i18n/locales/en-US.json`
  - 结果：通过。
- `yarn --cwd web build`
  - 结果：通过；构建输出第三方依赖 `@vueuse/core` 的 Rolldown pure annotation warning。

## Remaining risk

- 未启动 dev server 做浏览器手工验证；本轮完成了类型、lint、格式、单元测试和生产构建验证。
- `uv run pytest ...` 在当前 Windows/Cygwin 环境有 trampoline 路径问题，已用 `uv run python -m pytest ...` 验证同一测试集合。
- 旧 `.termbridge/terminals.json` 中的旧 host 值不会迁移，这是需求确认的破坏性变化。
