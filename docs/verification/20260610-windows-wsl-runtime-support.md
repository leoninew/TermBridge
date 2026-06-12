# Windows/WSL 运行环境支持验证

Review status: Draft

当前：严格模式 / strict，验证阶段 / Verification

## Requirement alignment

- Windows/Cygwin、Windows/WSL、Linux 都有 readiness，默认 `not_ready`。
- 环境检查通过后会持久化 readiness 和检测快照；主页读取持久化环境列表。
- 没有 ready 环境时，会话主页展示跳转环境配置页的引导。
- Windows/WSL shortcut 可进入 session 创建流程，启动命令使用 Windows 原生 ttyd 调用 `wsl --cd ... sh -lc ...`。
- Windows workspace 会通过 `wsl wslpath -a` 转换为 WSL 路径。
- session record 记录 host、tmux session name、tmux cleanup command，delete/restart 可复用这些上下文。
- 删除了全局 `Settings.use_wsl` / `TERMBRIDGE_USE_WSL` 语义。
- Linux 没有特殊硬编码禁用；是否可用统一由 readiness 和 `available_on_host` 决定。
- 后续用户决策移除了“默认运行环境”概念：创建 shortcut 时必须显式选择运行环境，不再由全局 default host 决定。
- 后续用户决策统一检测行为：检测接口使用 POST，环境摘要使用 GET；Cygwin 与 WSL 都只暴露环境级组合检测入口。

## Spec alignment

- 后端提供环境 summary API：`GET /api/environments`。
- 后端模型包含 `EnvironmentReadiness`、`EnvironmentSummary`、`EnvironmentListResponse`、`WindowsWslSettings`、`LinuxSettings`。
- Windows/Cygwin、Windows/WSL、Linux 检测接口刷新 readiness。
- Windows/Cygwin 组合检测按 bash -> tmux 顺序执行，并复用内部 bash/tmux 检测逻辑。
- Windows/WSL 组合检测按 wsl -> tmux 顺序执行，并复用内部 wsl/tmux 检测逻辑。
- Windows/WSL 检测保存 WSL/tmux path/version 等快照字段。
- 前端类型、API client、环境管理页、shortcut 管理、session 创建表单和 i18n 使用同一组 host 语义。
- Session 创建表单展示所有 host；不可用或 not ready 的 host disabled，不隐藏。
- 与早期 spec 不一致但符合后续用户决策：未保留 `TerminalSettings.default_host`，未保留默认运行环境 UI。

## Plan alignment

实际改动覆盖计划中的后端模型、settings、service、API、测试、前端类型、API client、App、SessionList、EnvironmentManagement、ShortcutManagement、SessionCreateForm、i18n 和 README。

计划中关于默认运行环境的步骤被后续用户决策替换为“shortcut 创建必须显式选择运行环境”。验证按该后续决策判断。

## Actual diff summary

- 后端：新增 readiness-driven environment list、WSL settings endpoint、WSL path conversion、WSL/Linux runtime command 构造、泛化 tmux cleanup command。
- 后端：环境检测接口统一为 POST；环境摘要保留 GET。
- 后端：移除公开 tmux 单项检测 API；Cygwin/WSL 组合检测内部复用私有 helper。
- 前端：主页加载环境 summary；无 ready 环境展示配置引导。
- 前端：环境页打开后检测 `ttyd`，再检测当前 tab；切换 tab 后检测对应环境。
- 前端：Cygwin 和 WSL tab 各只保留一个环境级检查按钮；Cygwin 显示 bash/tmux 结果，WSL 显示 wsl/tmux 结果。
- 前端：shortcut 创建必须显式选择 host；移除默认运行环境 UI 和相关类型。
- 文档：README 增加运行环境支持矩阵和 Windows/WSL 启动方式说明。
- 测试：覆盖 WSL command 构造、not-ready 错误、path conversion、cleanup/restart、Cygwin 回归和环境 summary。

## Planned vs actual changed files

- 计划内已改：
  - `src/termbridge/models.py`
  - `src/termbridge/settings.py`
  - `src/termbridge/services.py`
  - `src/termbridge/api.py`
  - `tests/test_terminal_service.py`
  - `tests/test_services.py`
  - `tests/test_api.py`
  - `web/src/types/sessions.ts`
  - `web/src/api/sessions.ts`
  - `web/src/App.vue`
  - `web/src/components/SessionList.vue`
  - `web/src/components/EnvironmentManagement.vue`
  - `web/src/components/ShortcutManagement.vue`
  - `web/src/components/SessionCreateForm.vue`
  - `web/src/i18n/locales/zh-CN.json`
  - `web/src/i18n/locales/en-US.json`
  - `README.md`
- 相关文档改动：
  - `docs/requirement/20260610-windows-wsl-runtime-support.md`
  - `docs/spec/20260610-windows-wsl-runtime-support.md`
  - `docs/plan/20260610-windows-wsl-runtime-support.md`
  - `docs/verification/20260610-windows-wsl-runtime-support.md`
- 计划外但相关：
  - `docs/llms.txt` 移动到 `docs/guides/llms.txt`，用于 Reka UI Tabs 参考。
  - `uv.lock` 有同步更新。

## Acceptance criteria checklist

- [x] 三类环境都有 readiness，默认 not ready。
- [x] 完整检查通过后持久化 ready。
- [x] 主页读取持久化 readiness。
- [x] 无 ready 环境时展示环境配置引导。
- [x] 手动重新检测会刷新 readiness 和检测快照。
- [x] 创建 shortcut 可选择 Windows/WSL。
- [x] 创建 shortcut 必须显式选择运行环境。
- [x] Session 创建表单展示所有 host，不可用 host disabled。
- [x] shortcut 列表和编辑表单使用统一 host label。
- [x] 后端允许 `windows_wsl` 进入 session 创建流程。
- [x] Windows/WSL 启动前检查 readiness 和必要运行信息。
- [x] Windows/WSL runtime command 使用默认 WSL 内 tmux `new-session -A`。
- [x] Windows workspace 使用 `wslpath` 转换并保留空格路径参数。
- [x] Windows/WSL 检测保存 WSL/tmux 可用性和版本/path 信息。
- [x] session record 记录 restart/delete 所需 host、tmux session 和 cleanup command。
- [x] 删除 Windows/WSL session 使用 WSL cleanup command。
- [x] restart 复用 stored command 并替换 ttyd port。
- [x] Windows/Cygwin 创建、删除、restart 回归路径有测试覆盖。
- [x] API、前端类型和 UI 文案使用统一 host 语义。
- [x] README 更新运行环境支持矩阵。
- [x] 前端异步操作有 loading/spinner 或 disabled 防重复提交。
- [x] 检测接口统一使用 POST，环境摘要使用 GET。
- [x] `/environment` 打开后检测 `ttyd` 和当前 tab。
- [x] Cygwin 环境检测只暴露 `windows-cygwin/check` 组合入口，内部检测 bash 和 tmux。
- [x] WSL 环境检测只暴露 `windows-wsl/check` 组合入口，内部检测 wsl 和 tmux。
- [x] 不再保留 Cygwin bash/tmux 或 WSL wsl/tmux 的拆分 UI 检测按钮和拆分 API 测试。
- [x] 相关单元测试覆盖计划中的关键路径。
- [x] 已按后续用户决策移除默认运行环境概念；因此早期“默认运行环境选择可持久化 / shortcut 默认跟随配置”验收项不再适用。

## Test results

- `uv run ruff check .`
  - 结果：通过。
- `uv run python -m mypy src tests`
  - 结果：通过，无类型错误。
- `uv run python -m pytest`
  - 结果：71 passed, 1 warning。
  - warning：`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`
- `yarn --cwd web typecheck`
  - 结果：通过。
- `yarn --cwd web lint`
  - 结果：通过。
- `yarn --cwd web build`
  - 结果：通过；仍有第三方 `@vueuse/core` pure annotation warning，不影响构建产物。

## Missed or expanded scope

- 扩展：按用户反馈补齐 Linux readiness-driven runtime command，避免前端或后端把 Linux 写死为特殊不可用。
- 扩展：按用户反馈移除默认运行环境概念，改为 shortcut 创建时必须显式选择运行环境。
- 扩展：按用户反馈将环境检测统一为 POST，并让 Cygwin/WSL 只暴露环境级组合检测入口。
- 未做：没有实现 WSL distro 选择、WSL/tmux 自动安装或 `/mnt/<drive>` fallback，符合 non-goals 和 plan。

## Risks

- 未启动 dev server 做浏览器手工验证；本轮完成了类型、lint、单元测试和生产构建验证。
- 本机 WSL/tmux 真实可用性未验证；Windows/WSL 启动路径通过单元测试覆盖命令构造和错误分支。
- readiness 是持久化快照，可能因用户卸载 WSL/tmux 而过期；启动失败时后端会返回明确错误并引导重新检测。
- `yarn --cwd web build` 仍输出第三方 `@vueuse/core` pure annotation warning，这是依赖包注释位置导致的构建警告，不是本次实现引入的错误。

## Incomplete items

- 浏览器手动验证仍可补做：无 ready 环境空状态、环境页打开自动检测 ttyd + 当前 tab、Cygwin/WSL tab 组合检测按钮、shortcut 必选 host、session 创建 host disabled 状态、WSL session 启动/delete/restart。

## Conclusion

实现与已接受的 requirement/spec/plan 主体对齐；默认运行环境相关内容已按后续用户决策替换为显式 host 选择。自动化验证通过，剩余风险主要是未在当前机器做真实浏览器和 WSL runtime 手工验证。
