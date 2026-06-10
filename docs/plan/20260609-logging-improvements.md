# 后端日志实现改进计划

Review status: Accepted

Flow mode: standard
Stage: Plan

## Requirement basis

- Requirement: `docs/requirement/20260609-logging-improvements.md`
- Requirement status: Accepted

## Implementation steps

1. 新增日志配置模块
   - 新建 `src/cc_ttyd/logging.py`。
   - 提供 `logging_config(level: str) -> dict[str, object]`。
   - 提供 `configure_logging(settings: Settings) -> None`。
   - 使用 `logging.config.dictConfig`。
   - 格式达到正式服务可排查标准：`%(asctime)s.%(msecs)03d | %(levelname)-7s | pid=%(process)d | %(name)s:%(lineno)d | %(message)s`。
   - 定义 root logger、default formatter、console handler，确保应用日志和框架日志走统一格式。
   - 显式配置 `cc_ttyd`、`uvicorn`、`uvicorn.error`、`uvicorn.access`。
   - `uvicorn`、`uvicorn.error` 使用项目统一 console handler/formatter，避免保留 Uvicorn 默认格式。
   - 禁用 `uvicorn.access`，由自定义 request logging middleware 替代，避免重复请求日志。

2. 扩展 settings
   - 在 `src/cc_ttyd/settings.py` 增加 `logging_level: str = "INFO"`。
   - 通过现有 `CC_TTYD_` env prefix 支持 `CC_TTYD_LOGGING_LEVEL`。
   - 不新增文件日志配置。

3. 新增 request logging middleware
   - 新建或放入现有 API 相关模块，例如 `src/cc_ttyd/middleware.py`。
   - 记录 method、包含 query string 的 path、status、duration。
   - 正常响应：2xx/3xx 使用 `logger.info`。
   - 4xx 使用 `logger.warning`。
   - 5xx 使用 `logger.error`。
   - 异常路径使用 `logger.exception(...)` 并 re-raise。
   - 不过滤 `/health`。
   - 不记录 request/response body。

4. 接入 app 初始化
   - `src/cc_ttyd/api.py:create_app()` 读取 settings 并调用 `configure_logging(settings)`。
   - `src/cc_ttyd/api.py:create_app()` 安装 request logging middleware。
   - 保证 `uvicorn cc_ttyd.main:app --reload` / `make backend` 这种 Uvicorn CLI 入口不会绕过 logging 初始化。

5. 接入 main 启动
   - `src/cc_ttyd/main.py` 移除 `logging.basicConfig(...)`。
   - 使用 `settings = load_settings()`。
   - `uvicorn.run(..., log_config=logging_config(settings.logging_level))`。

6. 测试覆盖
   - 增加 settings 测试：默认 `logging_level == "INFO"`。
   - 增加 logging config 测试：固定正式日志格式、root/default formatter/console handler，并断言 `uvicorn`、`uvicorn.error` 使用统一 handler，`uvicorn.access` 被禁用。
   - 增加 middleware 测试：请求日志包含 query string、status、duration；4xx/5xx 使用对应等级。
   - 如测试中 TestClient 自动触发 middleware，避免对现有 API 测试造成副作用。

## Files to change

- `src/cc_ttyd/settings.py`
- `src/cc_ttyd/logging.py`（新增）
- `src/cc_ttyd/middleware.py`（新增）
- `src/cc_ttyd/api.py`
- `src/cc_ttyd/main.py`
- `tests/test_api.py` 或新增 `tests/test_logging.py`

## Verification plan

- `uv run ruff check .`
- `uv run mypy src tests`
- `uv run pytest`

如本地环境不使用 `uv`，则改用项目可用的等价命令：

- `ruff check .`
- `mypy src tests`
- `pytest`

## Assumptions

- `cc-ttyd` 当前 settings 体系由 `pydantic-settings` 管理，新增 `logging_level` 可直接通过 `CC_TTYD_LOGGING_LEVEL` 生效。
- request logging middleware 不记录 body，因此不涉及敏感信息脱敏。
- 本轮不处理文件日志，也不引入 JSON 日志。

## Risks

- TestClient 请求也会经过 middleware，可能使日志测试和现有 API 测试互相影响；测试应使用 `caplog` 精确限定 logger。
- Uvicorn log config 与 `configure_logging` 同时存在，需要保持两者格式一致。
- 如果 `create_app()` 中读取 cached settings，测试修改环境变量时需要清理 `load_settings.cache_clear()`。

## Rollback

- 移除新增 logging/middleware 模块。
- `main.py` 恢复 `logging.basicConfig(...)`。
- `api.py:create_app()` 移除 middleware 注册。
- `settings.py` 移除 `logging_level`。

## User review notes

- 待用户 review。
