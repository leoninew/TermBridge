# ttyd 日志处理范围说明

Review status: Accepted

当前：轻量模式 / light，范围说明 / Scope note

## Goal

避免受管理的 `ttyd` 子进程日志默认污染 TermBridge 后端进程的控制台输出，导致主日志被污染或与 TermBridge 日志粘连。新增 `TERMBRIDGE_TTYD_LOG_MODE` 控制该行为，支持 `none`、`console`、`file` 三种模式；默认 `none` 禁用输出。

## Non-goal

- 不在本次实现 UI 日志查看器。
- 不重写 TermBridge 主日志格式。
- 不接入后台线程逐行读取 `ttyd` 输出并转发到 Python logging。
- 不改变 `ttyd` 启动命令、端口分配或 `tmux` 会话生命周期。

## Acceptance

- 新增 `TERMBRIDGE_TTYD_LOG_MODE` 配置项，支持 `none`、`console`、`file`。
- 默认值为 `none`，启动 session 时丢弃 `ttyd` stdout/stderr。
- 当 `TERMBRIDGE_TTYD_LOG_MODE=console` 时，`ttyd` stdout/stderr 继承父进程输出。
- 当 `TERMBRIDGE_TTYD_LOG_MODE=file` 时，启动 session 时 `ttyd` stdout/stderr 写入 `.termbridge/logs/ttyd/<session-id>.log`，不再直接写入 TermBridge 主控制台。
- `.env.sample` 说明相关配置。
- 相关单元测试通过。

## Risk

- 如果日志文件长期累积，后续可能需要日志轮转或清理策略；本次只改变输出位置，不实现轮转。
- 默认 `none` 会丢弃 `ttyd` 输出；排查子进程启动问题时需要临时改为 `file` 或 `console`。
