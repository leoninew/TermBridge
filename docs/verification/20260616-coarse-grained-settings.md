# 粗粒度配置化验证

当前：轻量模式 / light，验证 / Verification。

## What changed

- `Settings` 新增粗粒度运行配置：
  - `api_host` 默认 `localhost`
  - `api_port`
  - `serve_web`
  - `web_dir`
  - `uvicorn_access_log`
  - `terminal_proxy_timeout_seconds`
  - `process_shutdown_timeout_seconds`
  - `ttyd_writable`
- `body_log_limit` 保持在 `Settings`，并通过 `Settings` 对象注入 request logging middleware。
- `create_app(settings, ...)` 改为显式接收 `Settings`，并覆盖 FastAPI `load_settings` dependency，避免 handler 中重新读取默认配置。
- `logging_config(settings)` 改为接收 `Settings` 对象，不再逐项传递 logging level / access log 开关。
- `main.py` 的 CLI 默认 host/port 来自配置；CLI 参数仍可覆盖。
- terminal HTTP proxy timeout 改为读取 `settings.terminal_proxy_timeout_seconds`。
- `TtydProcessAdapter` 改为接收 `Settings`，关闭进程时读取 `settings.process_shutdown_timeout_seconds`。
- ttyd 启动命令根据 `settings.ttyd_writable` 决定是否添加 `--writable`。
- 快捷方式没有引入 unrestricted/full-access 特殊处理；所有快捷方式按同一逻辑保存和展示，用户定义什么启动命令是用户自由。
- `.env.sample` 更新新增配置项；本地 `.env` 也同步补充，但 `.env` 被 git 忽略。

## Acceptance

- [x] `Settings` 包含新增配置项，并支持 `TERMBRIDGE_` 环境变量覆盖。
- [x] `api_host` 默认值为 `localhost`。
- [x] 主要组件通过 `Settings` 对象读取配置，避免逐项参数膨胀。
- [x] 不对快捷方式命令内容做 unrestricted/full-access 特殊分类或过滤。
- [x] terminal HTTP proxy 使用配置化 timeout。
- [x] `TtydProcessAdapter` 使用配置化 shutdown timeout。
- [x] ttyd `--writable` 可配置。
- [x] uvicorn access log 可配置启用/禁用。
- [x] `.env.sample` 和测试同步更新。

## Commands

```text
python -m pytest tests/test_settings.py tests/test_logging.py tests/test_api.py tests/test_services.py tests/test_terminal_service.py tests/test_workspace_browser.py
120 passed, 1 warning
```

```text
python -m ruff check src tests
All checks passed!
```

```text
uv run mypy src
Success: no issues found in 15 source files
```

```text
uv run ruff check src tests
All checks passed!
```

## Remaining risk

- Vite dev proxy 和 Docker 启动命令仍有端口硬编码，本次按需求边界未改，后续可单独处理。
- `.env` 已同步更新但被 git 忽略，不会随提交进入版本库。
- pytest warning 来自 `fastapi.testclient` 的 StarletteDeprecationWarning，非本次变更引入。
