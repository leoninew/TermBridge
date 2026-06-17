# ttyd 日志处理验证
最后修改时间: 2026-06-17 10:35:00

Review status: Accepted

当前：轻量模式 / light，验证阶段 / Verification

## What changed

- 新增 `TERMBRIDGE_TTYD_LOG_MODE` 设置，支持 `none`、`console`、`file`，默认值为 `none`。
- `ProcessAdapter.start()` 支持可选 `log_file` 和 `suppress_output` 参数。
- `TtydProcessAdapter` 在 `file` 模式下将 `ttyd` stdout/stderr 写入指定日志文件，并在进程终止或刷新检测到进程退出时关闭文件句柄。
- `TtydProcessAdapter` 在 `none` 模式下将 `ttyd` stdout/stderr 重定向到 `subprocess.DEVNULL`。
- `SessionService` 根据 `TERMBRIDGE_TTYD_LOG_MODE` 选择丢弃输出、继承控制台输出或写入 ttyd 日志文件；源码 checkout / `pip install -e .` editable 模式默认写入项目目录 `logs/ttyd/<session-id>.log`，wheel / 普通安装后运行默认写入用户目录 `.termbridge/logs/ttyd/<session-id>.log`。
- file 模式日志文件会先写入 TermBridge 启动诊断 header，再继续接收 ttyd stdout/stderr；ttyd 自身输出可能因运行时缓冲延迟落盘，需要实时上屏时使用 console 模式。
- `.env.sample` 增加三种模式说明。
- 单元测试覆盖默认 `none`、`console` 和 `file` 模式。

## Acceptance

- [x] 新增 `TERMBRIDGE_TTYD_LOG_MODE`，支持 `none`、`console`、`file`。
- [x] 默认值为 `none`，启动 session 时丢弃 `ttyd` stdout/stderr。
- [x] `console` 模式下保持继承父进程输出行为。
- [x] `file` 模式下将 `ttyd` stdout/stderr 写入按运行形态选择的日志目录，并写入启动诊断 header。
- [x] `.env.sample` 说明相关配置。
- [x] 相关测试通过。

## Commands

- `uv run pytest tests/test_services.py`：通过，22 passed。
- `uv run mypy src tests`：通过。
- `uv run ruff check src/termbridge/process.py src/termbridge/services.py src/termbridge/settings.py tests/test_services.py`：通过。

## Remaining risk

- 默认 `none` 会丢弃 `ttyd` 输出；排查子进程启动问题时需要临时改为 `file` 或 `console`。
- `file` 模式会持续保留 `ttyd` 日志文件；本次未实现日志轮转或自动清理。
- file 模式 header 通过单元测试验证，未启动真实 `ttyd` 进程做端到端验证；如果 ttyd 在 Windows/Cygwin 下对非控制台 stdout/stderr 做块缓冲，header 可保证文件非空，但 ttyd 自身输出仍可能延迟刷入。
