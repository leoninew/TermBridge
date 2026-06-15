# 后端日志实现改进需求

Review status: Accepted

Flow mode: standard
Stage: Requirement

## Background

当前后端是 Python FastAPI + Uvicorn，入口在 `src/cc_ttyd/main.py`，目前仅使用：

```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
uvicorn.run("cc_ttyd.main:app", host="127.0.0.1", port=9008, reload=False)
```

服务层已有部分参数化业务日志，例如会话创建、重启、删除、端口分配、终端命令解析等集中在 `src/cc_ttyd/services.py`。

当前缺口：

- 日志配置分散在 `main.py`，没有独立 logging module。
- Uvicorn 和应用日志没有统一 `dictConfig` 管理。
- 没有 request logging middleware，API 请求、状态码、耗时无法统一观测。
- 没有明确禁用或替代 `uvicorn.access` 的策略。
- 日志 level 不能通过配置或环境变量调整。
- 异常日志主要依赖服务层和 FastAPI 默认行为，API 层没有统一请求上下文日志。

参考对比项目后，倾向采用 `k12-pubforge` 风格：stdlib `logging.config.dictConfig`、settings 驱动 level、console-only 默认、禁用 `uvicorn.access`、应用级 request middleware。

## Goals

- 新增独立日志配置模块，使用 Python stdlib `logging.config.dictConfig`。
- 统一应用日志与 Uvicorn 日志格式，优先使用 `%(name)s:%(lineno)d` 定位模块。
- 日志格式需要达到正式服务可排查标准：包含秒级时间+毫秒、左对齐 level、pid、logger name、行号和清晰分隔符。
- 完整接管 Uvicorn 日志配置：root/default formatter、`uvicorn`、`uvicorn.error` 使用项目统一 handler/formatter；`uvicorn.access` 明确禁用，由应用 request logging middleware 替代。
- 日志 level 放入现有 settings 体系，并支持通过环境变量调整，默认 `INFO`。
- 禁用 `uvicorn.access`，使用自定义 FastAPI request logging middleware 替代。
- request logging 至少记录 method、path、status、duration。
- 对 2xx/3xx、4xx、5xx 使用合适日志等级：info、warning、error。
- middleware 捕获异常时使用 `logger.exception(...)` 记录，并 re-raise，不在 middleware 中吞异常或改变响应语义。
- 保持现有服务层业务日志，不做大规模改写。
- 本轮仅输出 console，不处理文件日志。
- request path 包含 query string。
- 不隐藏 `/health` 请求日志。

## Non-goals

- 不引入 `loguru`、`structlog` 或其他第三方日志库。
- 不实现 JSON structured logging。
- 不默认记录 request/response body。
- 不新增日志 UI、日志查询、日志文件下载能力。
- 本轮不实现文件日志或文件日志配置。
- 不重构业务服务层日志文本，除非必须适配统一配置。
- 不改变现有 API 响应格式和异常语义。

## User scenarios

- 开发者启动 `TermBridge` 后，可以从控制台看到统一格式的应用日志和请求日志。
- 开发者排查前端请求失败时，可以看到对应 method、path、status 和 duration。
- 开发者可以通过环境变量调整日志等级，例如从 `INFO` 切换到 `DEBUG`。
- 服务发生未处理异常时，日志包含 traceback，同时 FastAPI 仍按原有方式处理响应。

## Acceptance criteria

- 存在独立日志配置模块，例如 `src/cc_ttyd/logging.py` 或 `src/cc_ttyd/infra/logging.py`。
- `main.py` 不再直接调用 `logging.basicConfig(...)`。
- `uvicorn.run(...)` 使用统一 `log_config`。
- log config 定义 root logger、default formatter、console handler，并显式配置 `uvicorn` / `uvicorn.error` / `uvicorn.access`。
- logging 初始化位于 app 初始化路径，确保 `uvicorn cc_ttyd.main:app --reload` / `just dev-backend` 不绕过请求日志配置。
- `create_app()` 或应用初始化流程安装 request logging middleware。
- `uvicorn.access` 被禁用或降噪，避免和自定义 request log 重复。
- 请求日志包含 method、path、status、duration。
- 4xx 请求记录为 warning，5xx 请求记录为 error，正常请求记录为 info。
- middleware 异常路径使用 `logger.exception(...)` 并 re-raise。
- 日志 level 可配置，默认 `INFO`。
- 现有测试通过，并新增或调整必要测试覆盖日志配置和 middleware 行为。

## Open questions

- 无。

## Decisions

- 采用标准模式 / standard。
- 默认参考 `k12-pubforge` 风格，不采用默认文件日志。
- 日志 level 配置放入现有 settings 体系。
- 本轮不处理文件日志。
- request path 包含 query string。
- 不隐藏 `/health` 请求日志。

## User review notes

- 用户确认：日志 level 放在现有 settings；本轮不处理文件日志；request path 包含 query string；不隐藏 `/health`。

## Light scope note: logging_config 简化

Review status: Accepted

Flow mode: light
Stage: Scope note

### Goal

- 在既有日志改进基础上，按“合理为准”简化 `logging_config()`。
- 不对 Uvicorn logger 做深度修改；保留 `uvicorn.error` 作为 Uvicorn 原生 logger name。
- 删除已禁用 `uvicorn.access` 后不再使用的 `access` formatter / handler 死配置。

### Non-goal

- 不实现 `uvicorn.error -> uvicorn` 展示名转换。
- 不新增 custom logging filter / formatter。
- 不 monkeypatch Uvicorn 内部 logger。
- 不引入第三方日志库或 JSON structured logging。

### Acceptance

- `logging_config()` 只保留实际使用的 `default` formatter 和 `console` handler。
- 继续显式配置 `cc_ttyd`、`uvicorn`、`uvicorn.error` 和禁用的 `uvicorn.access`。
- 保留 root logger 作为兜底输出。
- 相关日志测试更新并通过。

### Risk

- `uvicorn.error` 仍会出现在日志 logger name 中；这是 Uvicorn 原生命名，本次接受该行为。
