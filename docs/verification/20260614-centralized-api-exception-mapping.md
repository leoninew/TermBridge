# 集中封装 API 业务异常映射验证

## What changed

- 在 `src/termbridge/api.py` 中新增 `DomainErrorMapping` 和 `DOMAIN_ERROR_MAPPINGS`，集中声明业务异常到 HTTP status/code/error message 的映射。
- 新增 `domain_exception_handler`，在 `create_app()` 中按映射表注册业务异常 handler。
- 移除主要 API endpoint 中仅用于业务异常转换的重复 `try/except`，保留 HTTP proxy 上游请求失败、WebSocket 关闭等非业务异常处理。
- 新增更明确的业务异常：
  - `ShortcutInUseError`
  - `SessionWorkspaceNotFoundError`
  - `SessionTerminalUnavailableError`
- `SessionTerminalUnavailableError` 继承 `InvalidTerminalConfigError`，保持 service 层已有测试和调用方兼容。
- `SessionService.delete_workspace()` 将 repository 层的 `SessionNotFoundError` 转成 workspace 语义更明确的 `SessionWorkspaceNotFoundError`。

## Acceptance

- [x] API 业务异常映射集中定义在统一位置。
- [x] 主要 endpoint 中重复的异常映射 `try/except` 已删除。
- [x] 错误响应结构保持 `{ "code": string, "error": string }`。
- [x] 保持请求校验错误、HTTPException 和未处理异常的统一处理逻辑。
- [x] 保持既有公开错误 code 语义，例如 `bad_request`、`not_found`、`conflict`、`internal_error`、`service_unavailable`，避免前端兼容性风险。

## Commands

```bash
uv run pytest
```

结果：117 passed, 1 warning。

```bash
uv run ruff check . && uv run mypy src
```

结果：All checks passed；mypy Success。

## Remaining risk

- 目前集中映射仍放在 `api.py`，后续如果映射继续增长，可以进一步拆到独立模块，例如 `termbridge.api_errors`。
- WebSocket 握手失败仍按 WebSocket close code 处理，没有纳入 HTTP JSON 错误映射；这符合当前协议形态。
