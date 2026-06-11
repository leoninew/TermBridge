# 会话创建与导航 UI 调整验证

Review status: Accepted

当前：轻量模式 / light，验证 / Verification

## What changed

- 创建 session 从左侧常驻表单调整为会话管理卡片内原地切换：点击加号后平滑替换为创建表单，创建成功或取消后还原。
- 左侧会话管理仍负责 session 列表、选择、删除和外部打开。
- 创建表单将 `Runtime` 文案改为「终端」。
- 创建表单支持内置终端和自定义终端命令。
- 后端 `CreateSessionRequest` 支持 `terminal_command`，自定义终端命令使用 `shlex.split` 拆分后传给 ttyd，不经过 shell 解析。
- 新增后端 workspace browser API：`/api/workspaces/roots` 和 `/api/workspaces/tree`，用于前端选择后端可见的真实本机目录。
- Workspace 选择器改为可复用 `WorkspaceBrowser` 组件，并作为表单字段内嵌控件使用。
- Workspace 选择器默认不展示隐藏目录；后端预留 `show_hidden` 参数，前端暂不实现 checkbox。
- 已选 workspace 再次展开目录树时，会自动展开并定位到该目录。
- 后端关键步骤日志已添加。
- 后端自定义异常已提取到 `src/cc_ttyd/exceptions.py`，避免异常定义和业务逻辑混在一起。
- `make backend` 已改为 uvicorn reload 启动，开发时后端热更新生效。

## Acceptance

- [x] 左侧导航/侧栏以会话管理为主，创建入口不再是常驻大表单。
- [x] 点击创建入口后，创建内容在会话管理卡片内原地平滑切换。
- [x] 创建表单中 `Runtime` 文案改为「终端」。
- [x] 用户可以选择内置终端，也可以输入自定义终端命令。
- [x] Workspace 支持手输真实路径，也支持从后端目录树选择真实路径。
- [x] 目录树默认隐藏隐藏目录，后端已预留控制参数。
- [x] 现有 session 列表、选择、删除、iframe 打开终端能力保持可用。
- [x] 后端异常和模型/业务逻辑分离：模型在 `models.py`，异常在 `exceptions.py`。

## Commands

- `cd /d/Projects/TermBridge && uv run pytest`：28 passed, 1 warning（FastAPI/Starlette TestClient deprecation warning）
- `cd /d/Projects/TermBridge && uv run ruff check .`：passed
- `cd /d/Projects/TermBridge && uv run ruff format --check .`：passed，18 files already formatted
- `cd /d/Projects/TermBridge/frontend && yarn lint`：passed
- `cd /d/Projects/TermBridge/frontend && yarn format:check`：passed
- `cd /d/Projects/TermBridge/frontend && yarn typecheck`：passed
- `cd /d/Projects/TermBridge/frontend && yarn build`：passed；Rolldown 对 `node_modules/@vueuse/core` 的 `/* #__PURE__ */` 注释有 warning，不影响构建产物生成

## Remaining risk

- Workspace 目录树枚举的是后端进程可见路径；跨 WSL/Cygwin/Windows 路径表达仍可能需要后续根据实际使用细化。
- 自定义终端命令按 shell-like 语法拆分，但不经 shell 执行；复杂命令组合需要显式传可执行程序和参数。
