# 简化 stopped 会话语义验证

Review status: Accepted

当前：轻量模式 / light，验证 / Verification

## What changed

- `SessionService.stop()` 停止 ttyd process 后会 kill managed tmux window，并将 entry 标记为 `stopped`，清空 `tmux_window_id`、`pid` 和 `url`。
- `SessionService.start()` 取代 restart 语义；`POST /api/sessions/{session_id}/start` 从 stopped 状态启动时优先复用记录 id 对应的 window，其次复用同 workspace session 下的同名 window，最后才创建新的 managed tmux window。
- 前端 API、组件事件、handler 和 i18n key 从 restart 统一改为 start，不保留 `/restart` 或 `restartLabel` 兼容入口。
- running 会话停止操作使用 play-off 语义 icon；stopped 会话启动操作使用 Play icon。
- 更新被覆盖的 20260611 tmux lifecycle spec/plan/verification 文档，明确 stop 保留 window 的旧决策已被本需求覆盖。
- 会话列表 workspace 节点 hover/focus 时在删除按钮左侧展示“新建会话”icon，并使用该目录 host/path 打开现有新建会话流程。
- 启动会话请求期间，左侧列表启动按钮和终端启动 CTA 显示加载动画并禁用重复点击。

## Acceptance

- [x] Stop 后 managed tmux window 被清理，entry 的 `tmux_window_id` 清空。
- [x] Start stopped session 会复用已记录且存在的 managed tmux window；记录 window 缺失时会复用同名 window；都不存在时才创建新 window。
- [x] Close all 保持 records 但清理 tmux windows 和 workspace tmux sessions。
- [x] API/service/frontend/i18n 命名使用 start，不再暴露 restart 语义。
- [x] 前端 stopped action 使用 Play，running stop 使用 play-off。
- [x] workspace 节点可直接触发“在此目录新建会话”，并复用现有创建能力。
- [x] 启动会话耗时时有可见 loading 动画，并阻止重复启动点击。

## Commands

- `python -m pytest tests/test_services.py tests/test_api.py`：通过，24 passed，1 个 FastAPI/TestClient 依赖 warning。
- `python -m pytest tests/test_services.py tests/test_terminal_service.py`：通过，51 passed。
- `python -m pytest`：通过，97 passed，1 个 FastAPI/TestClient 依赖 warning。
- `python -m ruff check src tests`：通过。
- `yarn --cwd frontend lint`：通过；追加 workspace 节点新建会话 icon、启动 loading 状态后重新执行仍通过。
- `yarn --cwd frontend build`：通过；追加 workspace 节点新建会话 icon、启动 loading 状态后重新执行仍通过，仍有既有 `@vueuse/core` PURE annotation warning。

## Remaining risk

- 尚未做真实浏览器点击验证；当前通过 service/API 测试与前端 lint/build 验证。
- Stop 后不保留 tmux window 内容；这是本需求的有意语义。
