# 全局异常结构与 UI 错误状态处理验证

Review status: Accepted

当前：标准模式 / standard，验证阶段 / Verification

## Requirement alignment

- [x] API 错误响应统一为 `{ "code": string, "error": string }`。
- [x] 不保留 `detail`，前端不再读取旧 `detail` / `message`。
- [x] 错误码使用 `snake_case`。
- [x] 未捕获异常返回结构化 500 响应，并记录后端异常日志。
- [x] 操作级错误通过 toast 展示，不再让 session list 消失。
- [x] `loadSessions()` 失败时如果已有数据，会保留旧列表并显示 error toast。
- [x] Toast 支持 `title` 和 `success` / `error` 主题色。

## Plan alignment

- [x] `src/termbridge/api.py` 注册全局 exception handlers。
- [x] `src/termbridge/services.py` 将 `tmux` 命令超时转换为失败的 `CompletedProcess`，避免刷新检查击穿 API。
- [x] `web/src/api/sessions.ts` 定义 `ApiError` 并只读取 `{ code, error }`。
- [x] `web/src/stores/toast.ts` 与 `web/src/components/AppToast.vue` 支持 toast title 和主题色。
- [x] `web/src/components/AppShell.vue` 将 session 操作失败改为 error toast，并保留会话列表状态。

## Actual diff summary

- 后端错误响应从 FastAPI 默认 `detail` 结构统一为 `{ code, error }`。
- 全局 handler 覆盖 `HTTPException`、`RequestValidationError` 和未捕获异常。
- Request logging middleware 对穿透到 middleware 的异常返回结构化 500 响应，避免纯文本 `Internal Server Error`。
- `tmux` subprocess timeout 不再直接向上抛出，改为 warning 日志和 returncode 124。
- 前端 API 请求失败抛出 `ApiError(status, code, message)`。
- Session 操作失败改用 error toast，成功提示使用 success toast。
- Toast 视觉主题区分成功和错误。

## Planned vs actual changed files

计划内文件：

- `src/termbridge/api.py`：已修改。
- `src/termbridge/services.py`：已修改。
- `tests/test_api.py`：已修改。
- `tests/test_terminal_service.py`：已修改。
- `web/src/api/sessions.ts`：已修改。
- `web/src/stores/toast.ts`：已修改。
- `web/src/components/AppToast.vue`：已修改。
- `web/src/components/AppShell.vue`：已修改。

额外相关文件：

- `src/termbridge/middleware.py`：已修改，用于兜底返回结构化 500 响应。
- `web/src/components/EnvironmentManagement.vue`：已修改 toast 调用以适配新 API。
- `web/src/components/ShortcutManagement.vue`：已修改 toast 调用以适配新 API。

## Acceptance criteria checklist

- [x] 所有 API 错误响应至少统一为 `{ "code": string, "error": string }`。
- [x] FastAPI/Starlette 的 `HTTPException` 响应会被转换为统一结构。
- [x] 未捕获异常有统一兜底响应结构，同时后端日志保留异常堆栈。
- [x] 前端 `readError()` 支持新的 `code` / `error` 响应结构，不保留旧结构兼容逻辑。
- [x] `handleStart()` 等操作失败时使用 toast 展示错误，不再把 session list 替换成错误面板。
- [x] `loadSessions()` 失败时不主动清空已有 `sessions` / `sessionTree`；有旧数据时保留旧数据。
- [x] 添加后端 API 测试，覆盖结构化错误响应。
- [x] 添加 `tmux` timeout 测试，覆盖超时不向上抛出。
- [x] 前端 typecheck/lint 通过。

## Test results

- `uv run pytest tests/test_api.py tests/test_terminal_service.py tests/test_services.py`：通过，61 passed，1 warning。
- `uv run mypy src tests`：通过。
- `uv run ruff check src tests`：通过。
- `yarn --cwd web typecheck`：通过。
- `yarn --cwd web lint`：通过。

## Warnings

- pytest 仍有既有 warning：`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` 本次未处理。

## Remaining risk

- 当前错误码多数仍按 HTTP status 粗粒度映射，例如 `bad_request`、`not_found`、`service_unavailable`；后续可按业务逐步细化为 `session_not_found`、`invalid_terminal_config` 等。
- `RequestLoggingMiddleware` 与 FastAPI exception handler 都具备异常处理能力；当前目标是确保响应结构稳定，后续可进一步收敛重复异常日志。
- 未做真实浏览器交互测试；本次通过 typecheck/lint 验证前端改动。

## Conclusion

本次实现满足已接受需求：API 错误结构稳定为 `{ code, error }`，UI 操作错误不再破坏会话列表展示，toast 支持标题和成功/错误主题色。
