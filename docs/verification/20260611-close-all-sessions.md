# 关闭所有会话轻量验证

Review status: Accepted

## What changed

- 在后端新增 `POST /api/sessions/close-all`，批量停止所有会话并返回关闭统计。
- `SessionService.close_all()` 复用单会话 stop 的状态更新和 tmux window 清理语义，并额外关闭每个 workspace 的 tmux session。
- 设置菜单新增“关闭所有会话”危险操作入口。
- 点击入口后显示警告样式确认模态窗；确认后调用批量关闭 API、刷新会话树、关闭前端打开的终端标签并展示 toast。
- 补充中英文文案、前端 API wrapper、类型和后端测试覆盖。
- 设置菜单的环境管理、快捷方式、关闭所有会话入口补充图标；关闭所有会话统一使用警告色。
- 新建会话名称占位文案调整为更贴近日常使用的示例。
- 全局 toast 位置调整为右下角。

## Acceptance

- [x] 设置中有可见的“关闭所有会话”危险操作入口。
- [x] 点击入口后弹出警告/破坏性样式确认模态窗。
- [x] 取消确认不会关闭任何会话。
- [x] 确认后遍历所有环境和会话，复用现有单会话 stop 语义关闭 tmux window/session。
- [x] 操作完成后保留会话管理记录，并刷新前端会话状态。
- [x] 操作成功时展示 toast 反馈；失败时展示错误反馈。

## Commands

- `yarn --cwd frontend build`：通过。Vite/Rolldown 对 `@vueuse/core` 的 PURE annotation 输出既有 warning，但构建成功。
- `yarn --cwd frontend lint`：通过。
- 最新 UI 调整后重新执行 `yarn --cwd frontend lint`：通过。
- 最新 UI 调整后重新执行 `yarn --cwd frontend build`：通过；仍仅有既有 `@vueuse/core` PURE annotation warning。
- `python -m pytest tests/test_services.py tests/test_api.py`：通过，22 passed，1 个 FastAPI/TestClient 依赖 warning。
- `python -m pytest`：通过，89 passed，1 个 FastAPI/TestClient 依赖 warning。
- `python -m ruff check src tests`：通过。
- `python -m mypy src`：未执行成功，当前 Python 环境未安装 `mypy`。

## Remaining risk

- 当前未做真实浏览器点击验证；已通过构建、lint、API/service 测试覆盖主要行为。
- 批量关闭会停止正在运行的终端进程，入口已使用警告确认降低误触风险。
