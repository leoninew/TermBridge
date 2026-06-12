# tmux window 与会话存储生命周期修复验证

Review status: Accepted

## What changed

- 修正 workspace tmux session 首次创建逻辑：首个 managed window 直接由 `tmux new-session -d -P` 创建，不再额外留下默认 `bash` window。
- 后续简化 stopped 语义已覆盖 stop/restart 决策：手动 stop 清理 managed window 并清空 `tmux_window_id`；start stopped session 优先复用记录 id 或同名 window，都不存在时才创建新的 managed window，不保留 restart API 命名。
- delete entry 仍会清理 managed window，但删除最后一个会话时保留目录 workspace 节点。
- 新增目录 workspace 删除能力，删除二级目录节点时清理该 workspace 下的 windows 和 tmux session。
- `.termbridge/sessions.json` 写出为 `environments -> workspace path -> session name` 三级结构；旧 `workspaces` schema 不兼容且不会迁移。
- 前端 session tree 的目录节点 hover 时显示删除 icon；点击后先展示确认弹窗，空目录使用轻量确认，含会话目录使用警告确认，确认后再删除目录节点；新建会话上下文改为由树节点显式选择提供。
- 当前没有会话但仍有目录节点时继续展示目录树；只有没有会话且没有目录节点时才展示“暂无会话”空态。
- 更新 workspace tmux session 模型文档，使 stop/start/delete 语义与最新实现一致。

## Acceptance

- [x] 新建 workspace tmux session 时不会保留默认空 `bash` window。
- [x] 每个 TermBridge 会话对应一个 managed tmux window。
- [x] Stop 保留 `tmux_window_id`，停止 ttyd process，清空 URL 并将 entry 标记为 stopped。
- [x] Restart stopped entry 时如果原 window 仍存在，则复用原 window 并启动新的 ttyd attach。
- [x] Restart stopped entry 时如果原 window 不存在，则按同一个 entry 重建 window 并更新 `tmux_window_id`。
- [x] Delete entry 仍会 kill managed window，但不删除目录节点。
- [x] Close all sessions 关闭所有 managed windows 和 workspace tmux sessions，并保留 records 与目录节点。
- [x] 目录节点 hover 时展示删除 icon，并在确认后调用目录删除 API 删除对应二级目录节点；空目录确认不使用高影响警告语气。
- [x] 当前没有会话但仍有目录节点时继续展示目录树；只有没有会话且没有目录节点时展示空态提示。
- [x] 从目录节点新建会话时，创建表单显式使用该环境和目录作为初始值。
- [x] `.termbridge/sessions.json` 写出为环境、标准化目录完整路径、会话名称三级结构。
- [x] 旧 `workspaces` hash schema 不兼容，读取时明确报 incompatible schema。
- [x] 后端测试覆盖新建、停止、恢复、删除、close all、新 schema 写读和旧 schema 拒绝。

## Commands

- `python -m pytest tests/test_terminal_service.py::test_terminal_service_creates_wsl_tmux_window_from_wsl_cd_workspace tests/test_services.py tests/test_session_repository.py tests/test_api.py`：通过，29 passed，1 个 FastAPI/TestClient 依赖 warning。
- 切换为不兼容旧 schema 后执行 `python -m pytest tests/test_session_repository.py tests/test_repositories.py`：通过，10 passed。
- `yarn --cwd web lint`：通过；空目录树空态和目录删除确认调整后均重新执行通过。
- `yarn --cwd web build`：通过；空目录树空态和目录删除确认调整后均重新执行通过，仍仅有既有 `@vueuse/core` PURE annotation warning。
- 切换为不兼容旧 schema 后重新执行 `python -m pytest`：通过，95 passed，1 个 FastAPI/TestClient 依赖 warning。
- `python -m ruff check src tests`：通过。
- `python -m mypy src`：未执行成功，当前 Python 环境未安装 `mypy`。

## Remaining risk

- 当前未做真实浏览器点击验证；前端已通过 lint/build，后端 API 和 service 行为有测试覆盖。
- sessions schema 改为三层结构后，同一环境同一目录下会话名称必须唯一；当前实现会拒绝重名创建。
- 工作区目录 path 作为 JSON key 使用标准化路径，跨平台路径展示仍依赖后端标准化逻辑。
- 旧 sessions schema 不兼容且不迁移；现有历史 `.termbridge/sessions.json` 需要用户清理或重新生成。
