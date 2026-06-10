# 后端日志实现改进验证

Review status: Accepted

Flow mode: standard
Stage: Verification

## Requirement alignment

- [x] 存在独立日志配置模块：`src/cc_ttyd/logging.py`。
- [x] 使用 Python stdlib `logging.config.dictConfig`。
- [x] 日志格式使用正式可排查格式：秒级时间+毫秒、左对齐 level、pid、`%(name)s:%(lineno)d` 和清晰分隔符。
- [x] `main.py` 不再直接调用 `logging.basicConfig(...)`。
- [x] `uvicorn.run(...)` 使用统一 `log_config`。
- [x] log config 定义 root logger、default/access formatter、console/access handler。
- [x] `uvicorn`、`uvicorn.error` 使用项目统一 console handler/formatter。
- [x] `settings.py` 增加 `logging_level`，默认 `INFO`。
- [x] `CC_TTYD_LOGGING_LEVEL` 可通过现有 settings env prefix 覆盖。
- [x] `create_app()` 初始化 logging，确保 `uvicorn cc_ttyd.main:app --reload` / `make backend` 不绕过请求日志配置。
- [x] `create_app()` 安装 request logging middleware。
- [x] 禁用 `uvicorn.access`，避免和自定义 request log 重复。
- [x] 请求日志包含 method、包含 query string 的 path、status、duration。
- [x] 2xx/3xx 使用 info，4xx 使用 warning，5xx 使用 error。
- [x] middleware 异常路径使用 `logger.exception(...)` 并 re-raise。
- [x] 不隐藏 `/health`。
- [x] 不记录 request/response body。
- [x] 本轮未引入文件日志、JSON logging 或第三方日志库。

## Plan alignment

- [x] 新增 `src/cc_ttyd/logging.py`。
- [x] 新增 `src/cc_ttyd/middleware.py`。
- [x] 更新 `src/cc_ttyd/settings.py`。
- [x] 更新 `src/cc_ttyd/main.py`。
- [x] 更新 `src/cc_ttyd/api.py`。
- [x] 新增 `tests/test_logging.py` 覆盖日志配置和 request logging 行为。

## Actual diff summary

- 新增 logging config：统一 root、`cc_ttyd`、`uvicorn`、`uvicorn.error`，禁用 `uvicorn.access`。
- 日志格式升级为 `%(asctime)s.%(msecs)03d | %(levelname)-7s | pid=%(process)d | %(name)s:%(lineno)d | %(message)s`。
- 新增 request logging middleware：记录请求完成和未处理异常。
- settings 增加 `logging_level`。
- FastAPI app 初始化时读取 settings 并调用 `configure_logging(settings)`，覆盖 Uvicorn CLI/reload 启动路径。
- main 启动时读取 settings，并将统一 log config 传给 Uvicorn。
- FastAPI app 初始化时安装 middleware。
- 新增日志相关单元测试。

## Planned vs actual changed files

- [x] `src/cc_ttyd/settings.py`：计划增加 `logging_level`；实际已增加。
- [x] `src/cc_ttyd/logging.py`：计划新增 logging config；实际已新增，并包含 root/default/access formatter、console/access handler、Uvicorn logger 配置。
- [x] `src/cc_ttyd/middleware.py`：计划新增 request logging middleware；实际已新增。
- [x] `src/cc_ttyd/api.py`：计划在 `create_app()` 安装 middleware；实际已安装，并补充 logging 初始化以覆盖 Uvicorn CLI/reload 入口。
- [x] `src/cc_ttyd/main.py`：计划移除 `basicConfig` 并向 Uvicorn 传入 `log_config`；实际已完成。
- [x] `tests/test_logging.py`：计划新增日志配置和 middleware 测试；实际已新增。
- [x] `tests/test_api.py`：计划允许使用或新增 `tests/test_logging.py`；实际选择新增 `tests/test_logging.py`，未改 `tests/test_api.py`。

## Commands

- `uv run ruff check src/cc_ttyd/api.py src/cc_ttyd/main.py src/cc_ttyd/logging.py src/cc_ttyd/middleware.py tests/test_logging.py`：通过。
- `uv run mypy src/cc_ttyd/api.py src/cc_ttyd/main.py src/cc_ttyd/logging.py src/cc_ttyd/middleware.py tests/test_logging.py`：通过。
- `uv run pytest tests/test_logging.py`：通过，8 passed，1 warning。
- `uv run ruff check .`：通过。

## Acceptance criteria checklist

- [x] 独立 logging module。
- [x] main 移除 `basicConfig`。
- [x] Uvicorn 使用统一 `log_config`。
- [x] root/default formatter/console handler 明确配置。
- [x] `uvicorn`、`uvicorn.error` 使用统一 handler/formatter。
- [x] create_app 初始化 logging，覆盖 Uvicorn CLI/reload 入口。
- [x] create_app 安装 request logging middleware。
- [x] 禁用 `uvicorn.access`。
- [x] request log 包含 method/path/status/duration。
- [x] 4xx warning、5xx error、正常请求 info。
- [x] 异常路径记录 traceback 并 re-raise。
- [x] logging level 可配置，默认 `INFO`。
- [x] 本任务相关测试通过。
- [x] 全量 ruff 检查通过。

## Missed or expanded scope

- 未发现本任务范围内遗漏项。
- 未扩展到文件日志、JSON logging、第三方日志库、request/response body logging，符合 non-goals。
- 未重构服务层业务日志文本，符合 non-goals。

## Incomplete items

- 本任务相关实现与测试已完成。

## Remaining risk

- request logging 当前不记录 body，符合本轮范围；如后续需要 body，需要单独设计 prefix、截断和脱敏策略。

## Conclusion

本任务相关日志功能目标已达成；`make backend` / Uvicorn CLI reload 入口也会执行 logging 初始化，请求级别日志应能进入统一 console handler。

## Light verification addendum: logging_config 简化

Review status: Accepted

Flow mode: light
Stage: Verification

### What changed

- 基于 `docs/requirement/20260609-logging-improvements.md` 的轻量范围说明继续改进。
- 简化 `src/cc_ttyd/logging.py`：删除未使用的 `access` formatter 和 `access` handler。
- 保留 `default` formatter、`console` handler、root logger，以及 `cc_ttyd` / `uvicorn` / `uvicorn.error` / `uvicorn.access` 的显式配置。
- 未对 Uvicorn logger name 做展示名转换，接受 `uvicorn.error` 是 Uvicorn 原生命名。
- 更新 `tests/test_logging.py` 中 logging config 的结构断言。

### Acceptance

- [x] `logging_config()` 只保留实际使用的 `default` formatter 和 `console` handler。
- [x] `uvicorn.access` 继续禁用，避免和自定义 request logging 重复。
- [x] `uvicorn` 和 `uvicorn.error` 继续显式接管到统一 console handler / formatter。
- [x] root logger 保留为兜底输出。
- [x] 未新增 custom filter / formatter，也未 monkeypatch Uvicorn。

### Commands

- `uv run pytest tests/test_logging.py`：通过，9 passed，1 warning（FastAPI/Starlette TestClient deprecation warning）。
- `uv run ruff check src/cc_ttyd/logging.py tests/test_logging.py`：通过。

### Remaining risk

- 控制台仍会显示 `uvicorn.error` logger name；这是 Uvicorn 内部 logger 命名，本次明确接受，不做深度改写。
