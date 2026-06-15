# 后端日志实践

本文记录 `TermBridge` 后端日志配置约定，目标是让 FastAPI、Uvicorn 和应用日志在开发环境中保持统一、可排查、不过度设计。

## 核心原则

- 使用 Python 标准库 `logging` / `logging.config.dictConfig`。
- 默认只输出 console，不实现文件日志。
- 不引入 `loguru`、`structlog` 或其他第三方日志库。
- 不默认使用 JSON structured logging。
- 不默认记录 request / response body。
- Uvicorn 日志使用项目统一 formatter / handler，但不 monkeypatch Uvicorn 内部 logger。
- `uvicorn.access` 禁用，由应用级 request logging middleware 替代。

## 日志格式

当前统一格式：

```python
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FORMAT = "%(asctime)s [%(levelname).5s] %(name)s:%(lineno)d %(message)s"
```

示例：

```text
2026-06-09 14:38:40 [INFO] uvicorn.error:582 Uvicorn running on http://127.0.0.1:9008 (Press CTRL+C to quit)
2026-06-09 14:38:42 [INFO] termbridge.middleware:37 Request completed method=GET path=/health status=200 duration_ms=1.23
```

字段含义：

- `%(asctime)s`：秒级时间，便于人工阅读。
- `%(levelname).5s`：固定宽度 level，和参考项目风格一致。
- `%(name)s:%(lineno)d`：logger name + 源码行号，用于定位来源。
- `%(message)s`：业务或框架日志正文。

不要为了局部偏好继续加入 `pid=`、大量竖线分隔符、展示名转换等额外格式噪音。除非后续有明确运维需求，否则保持当前格式稳定。

## logging_config 结构

`logging_config()` 应保持简洁，只保留实际使用的 formatter / handler：

```python
def logging_config(level: str = "INFO") -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": LOG_FORMAT,
                "datefmt": LOG_DATE_FORMAT,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
        "loggers": {
            "termbridge": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": [],
                "level": "CRITICAL",
                "propagate": False,
            },
        },
    }
```

约定：

- `default` formatter 是唯一 console formatter。
- `console` handler 是唯一默认 handler。
- 保留 `root` logger，作为第三方库或未来非 `termbridge` logger 的兜底输出。
- 显式配置 `termbridge`，避免应用日志依赖 root 的隐式行为。
- 显式配置 `uvicorn` 和 `uvicorn.error`，确保 Uvicorn 启动、reload、lifespan 日志走项目格式。
- 显式禁用 `uvicorn.access`，避免和自定义 request logging 重复。

不要保留没有实际使用的 `access` formatter / handler。既然 `uvicorn.access` 被禁用，请求日志由 middleware 负责，额外的 access handler 只会增加配置噪音。

## 关于 `uvicorn.error`

日志中出现：

```text
[INFO] uvicorn.error:328 Will watch for changes...
```

不表示这是 error 级别日志。真正的日志级别是 `[INFO]`。

`uvicorn.error` 是 Uvicorn 内部用于服务端运行日志的 logger name，启动、reload、lifespan 等日志都会使用它。这是 Uvicorn 的原生命名和兼容约定。

本项目约定：

- 接受 `uvicorn.error` 作为 logger name。
- 不做 `uvicorn.error -> uvicorn` 的展示名转换。
- 不新增 custom logging filter / formatter 只为隐藏这个名字。
- 不 monkeypatch Uvicorn 内部 logger。

我们只接管它的 handler、formatter 和 level，保持行为透明。

## Uvicorn 启动入口

为了让 reload 进程的早期日志也使用项目配置，开发启动应通过项目入口启动 Uvicorn：

```just
dev-backend:
    uv run python -m termbridge.main --host 127.0.0.1 --port 9008 --reload
```

不要在 `just dev-backend` 中直接使用：

```bash
uv run uvicorn termbridge.main:app --host 127.0.0.1 --port 9008 --reload
```

原因是 Uvicorn CLI 会先初始化自己的默认日志配置，reloader 早期日志可能出现未统一格式：

```text
INFO:     Will watch for changes in these directories: ...
```

项目入口 `termbridge.main` 应负责：

- 解析 `--host`、`--port`、`--reload`。
- 读取 settings 中的 `logging_level`。
- 调用 `uvicorn.run(..., log_config=logging_config(settings.logging_level))`。
- reload 模式下使用明确的 `reload_dirs=["src"]`。

## Request logging

HTTP access log 不使用 `uvicorn.access`，而由 `RequestLoggingMiddleware` 统一记录。

请求完成日志至少包含：

- method
- path，包含 query string
- status
- duration_ms

示例：

```text
Request completed method=GET path=/api/sessions?state=running status=200 duration_ms=2.35
```

日志级别约定：

- `2xx` / `3xx`：`INFO`
- `4xx`：`WARNING`
- `5xx`：`ERROR`
- 未处理异常：`logger.exception(...)`，记录 traceback 后 re-raise

middleware 不应吞异常，不应改变 FastAPI 原有响应语义。

## Settings

日志等级从现有 settings 体系读取：

```python
logging_level: str = "INFO"
```

环境变量使用项目 prefix：

```bash
TERMBRIDGE_LOGGING_LEVEL=DEBUG
```

默认保持 `INFO`。不要在代码中散落 `logging.basicConfig(...)` 或硬编码多个 logger level。

## 不推荐做法

不要重新引入：

```python
logging.basicConfig(...)
```

不要为已禁用的 `uvicorn.access` 保留死配置：

```python
"access": {
    "format": LOG_FORMAT,
    "datefmt": LOG_DATE_FORMAT,
}
```

```python
"access": {
    "class": "logging.StreamHandler",
    "formatter": "access",
}
```

不要为了隐藏 `uvicorn.error` 增加展示名 filter：

```python
record.display_name = "uvicorn"
```

除非后续有明确的日志平台字段规范，否则这类转换会让真实 logger name 和输出不一致，增加排查成本。

不要同时启用 `uvicorn.access` 和自定义 request logging middleware，否则同一个请求会出现重复日志。

## 修改检查清单

调整后端日志时，至少检查：

- [ ] 是否仍使用 `logging.config.dictConfig`。
- [ ] 是否没有重新引入 `logging.basicConfig(...)`。
- [ ] `LOG_FORMAT` 是否保持统一、简洁、可定位。
- [ ] `logging_config()` 是否只保留实际使用的 formatter / handler。
- [ ] `termbridge`、`uvicorn`、`uvicorn.error` 是否显式接管。
- [ ] `uvicorn.access` 是否仍禁用。
- [ ] request logging 是否仍包含 method、path、status、duration。
- [ ] 4xx / 5xx / exception 日志等级是否符合约定。
- [ ] `just dev-backend` 是否通过 `python -m termbridge.main --reload` 启动。

建议运行：

```bash
uv run pytest tests/test_logging.py
uv run ruff check src/termbridge/logging.py src/termbridge/main.py tests/test_logging.py
```

如果修改了启动入口，也建议短暂启动检查 reload 日志：

```bash
timeout 5s uv run python -m termbridge.main --host 127.0.0.1 --port 9011 --reload
```

期望最早的 reload 日志也使用统一格式：

```text
2026-06-09 14:38:40 [INFO] uvicorn.error:328 Will watch for changes in these directories: ['...\\src']
```

## 当前约定背景

本约定来自 2026-06-09 的后端日志改进：

- 从分散的 `basicConfig` 收敛为独立 `termbridge.logging` 模块。
- 使用 stdlib `dictConfig` 统一应用日志和 Uvicorn 日志。
- 禁用 `uvicorn.access`，由应用 middleware 记录请求日志。
- 参考 `D:/SourceCodes/k12-pubforge/fastapi` 的简洁 console logging 风格，但不完全照搬；以当前项目合理性为准。
- 接受 `uvicorn.error` 原生命名，不做深度改写。
- 删除未使用的 `access` formatter / handler，保持配置干净。
