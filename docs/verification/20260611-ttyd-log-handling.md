# ttyd 日志处理验证

Review status: Accepted

当前：轻量模式 / light，验证阶段 / Verification

## What changed

- 新增 `TERMBRIDGE_TTYD_LOG_MODE` 设置，支持 `none`、`console`、`file`，默认值为 `none`。
- `ProcessAdapter.start()` 支持可选 `log_file` 和 `suppress_output` 参数。
- `TtydProcessAdapter` 在 `file` 模式下将 `ttyd` stdout/stderr 写入指定日志文件，并在进程终止或刷新检测到进程退出时关闭文件句柄。
- `TtydProcessAdapter` 在 `none` 模式下将 `ttyd` stdout/stderr 重定向到 `subprocess.DEVNULL`。
- `SessionService` 根据 `TERMBRIDGE_TTYD_LOG_MODE` 选择丢弃输出、继承控制台输出或写入 `.termbridge/logs/ttyd/<session-id>.log`。
- `.env.sample` 增加三种模式说明。
- 单元测试覆盖默认 `none`、`console` 和 `file` 模式。

## Acceptance

- [x] 新增 `TERMBRIDGE_TTYD_LOG_MODE`，支持 `none`、`console`、`file`。
- [x] 默认值为 `none`，启动 session 时丢弃 `ttyd` stdout/stderr。
- [x] `console` 模式下保持继承父进程输出行为。
- [x] `file` 模式下将 `ttyd` stdout/stderr 写入 `.termbridge/logs/ttyd/<session-id>.log`。
- [x] `.env.sample` 说明相关配置。
- [x] 相关测试通过。

## Commands

- `uv run pytest tests/test_services.py`：通过，22 passed。
- `uv run mypy src tests`：通过。
- `uv run ruff check src/termbridge/process.py src/termbridge/services.py src/termbridge/settings.py tests/test_services.py`：通过。

## Remaining risk

- 默认 `none` 会丢弃 `ttyd` 输出；排查子进程启动问题时需要临时改为 `file` 或 `console`。
- `file` 模式会持续保留 `ttyd` 日志文件；本次未实现日志轮转或自动清理。
- 当前只通过单元测试验证三种模式的参数传递和类型检查，未启动真实 `ttyd` 进程做端到端验证。
