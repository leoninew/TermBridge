# 全局异常结构与 UI 错误状态处理计划

Review status: Accepted

当前：标准模式 / standard，计划阶段 / Plan

## Requirement basis

基于 `docs/requirement/20260611-global-error-ui-state.md`：

- API 错误响应统一为 `{ "code": string, "error": string }`。
- 不向后兼容旧的 `detail` / `message` 响应结构。
- 错误码使用 `snake_case`。
- 请求级未捕获异常也必须返回结构化错误响应，并在后端日志保留堆栈。
- UI 操作级错误不应让 session list 消失，优先用 toast 展示。
- 操作失败不在按钮附近额外显示错误。
- Toast 添加 `title` 字段，并实现 `success` / `error` 主题色。

## Implementation steps

### 1. 后端新增统一 API 错误模型与 handler

修改 `src/termbridge/api.py` 或新增轻量模块（如 `src/termbridge/errors.py`）：

1. 定义错误响应结构，例如：
   - `code: str`
   - `error: str`
2. 增加 helper：
   - `error_response(status_code, code, error)`
   - 或统一 exception handler 中直接返回 `JSONResponse`。
3. 在 `create_app()` 中注册 exception handlers：
   - `HTTPException`
   - `RequestValidationError`
   - `Exception`
4. 对未捕获异常：
   - 后端 logger 使用 `logger.exception(...)` 记录 traceback。
   - 响应：HTTP 500，`{ "code": "internal_error", "error": "Internal server error" }`。
5. 对 `HTTPException`：
   - 通过 `status_code` 和已有 detail 映射为 `{ code, error }`。
   - 不返回 `detail` 字段。

建议初始状态码到错误码映射：

| HTTP status | code |
| --- | --- |
| 400 | `bad_request` |
| 404 | `not_found` |
| 409 | `conflict` |
| 422 | `validation_error` |
| 500 | `internal_error` |
| 503 | `service_unavailable` |

### 2. 处理 `tmux` 命令超时类问题

避免为每种底层失败新增大量异常类，优先在服务边界做本地处理：

1. 在 `TerminalService._run_tmux_command()` 捕获 `subprocess.TimeoutExpired`。
2. 返回一个失败的 `subprocess.CompletedProcess[str]`，例如：
   - `returncode=124`
   - `stderr="tmux command timed out after 10 seconds"`
3. `tmux_window_exists()` / `find_tmux_window_by_name()` 对失败结果按“不存在/未找到”处理，不向上抛未捕获异常。
4. `create_tmux_window()` 如遇超时结果，继续通过现有 `InvalidTerminalConfigError` 抛出可读错误，API 边界映射为 400 或后续可改为 503。
5. `_refresh_entry()` 不应因为状态刷新检查超时导致整个 session tree/list 请求失败；超时应保持原记录或保守标记，而不是让 UI 无列表可用。

说明：本计划不通过新增专用异常类解决该问题，符合用户反馈。

### 3. 后端 endpoint 错误响应整理

检查 `src/termbridge/api.py` 中现有 endpoint：

1. 保留业务层 `try/except`，但抛出的 `HTTPException(detail=...)` 最终会被全局 handler 转为 `{ code, error }`。
2. 可逐步把常见业务异常映射得更具体：
   - `SessionNotFoundError` -> 404 + `session_not_found`
   - `ShortcutNotFoundError` -> 404 + `shortcut_not_found`
   - `InvalidTerminalConfigError` -> 400 + `invalid_terminal_config`
   - `NoAvailablePortError` -> 503 + `no_available_port`
3. 若为了保持变更小，可以第一步只做 status 级 code；测试覆盖结构即可。

### 4. 前端 API 错误读取改造

修改 `web/src/api/sessions.ts`：

1. 定义 `ApiErrorResponse`：
   - `code: string`
   - `error: string`
2. 定义 `ApiError` 类或等价结构：
   - `status: number`
   - `code: string`
   - `message: string`
3. `request<T>()` 在 `!response.ok` 时只读取 `{ code, error }`。
4. 不兼容 `detail` / `message`。
5. 对非 JSON 或格式异常响应使用 fallback：
   - `code="request_failed"`
   - `message=i18n.global.t('api.requestFailed', { status })`

### 5. Toast store 支持 title

修改 `web/src/stores/toast.ts` 和 `web/src/components/AppToast.vue`：

1. Toast item 增加 `title`。
2. Toast item 增加 `variant: 'success' | 'error'`，并在 UI 中体现主题色。
3. 提供调用方式，例如：
   - `toast.show({ title: 'Start failed', variant: 'error' })`
   - `toast.show({ title: 'Session started', variant: 'success' })`
4. 现有 success toast 调用更新为 `success` variant。
5. 操作失败 toast 使用 `error` variant。
6. 本轮不强制添加按钮附近错误提示。

### 6. 会话页错误状态拆分

修改 `web/src/components/AppShell.vue`：

1. `handleStart()` 失败：
   - 不设置页面级 `error.value`。
   - 调用 error toast。
   - 保持 `sessions`、`sessionTree`、`openTerminalSessionIds`、`activeSessionId` 不变。
2. 同样处理操作级失败：
   - `handleStop()`
   - `confirmRemove()`
   - `confirmRemoveWorkspace()`
   - `confirmCloseAllSessions()`
3. `loadSessions()` 失败：
   - 如果已有 `sessionTree` 或 `sessions`，保留旧数据并 toast。
   - 如果没有任何可展示数据，设置页面级 `error.value`。
4. `refresh()` 需要保证 loading 在异常路径也能恢复，建议使用 `try/finally`。

### 7. 测试更新

后端：

- 修改 `tests/test_api.py`：
  - HTTPException 返回 `{ code, error }`，不包含 `detail`。
  - 增加一个 endpoint/service 抛未捕获异常的测试，确认 500 响应结构为 `{ code: "internal_error", error: "Internal server error" }`。
  - 增加 validation error 测试，确认 422 响应结构为 `{ code: "validation_error", error: ... }`。
- 修改或新增 `tests/test_terminal_service.py`：
  - mock `subprocess.run` 抛 `TimeoutExpired`，确认 `tmux_window_exists()` 不向上抛异常。
  - 如覆盖 `create_tmux_window()`，确认超时转换为现有可读业务错误。

前端：

- 至少运行：
  - `yarn --cwd web typecheck`
  - `yarn --cwd web lint`
- 如果已有前端单元测试基础，再补 API error parsing 测试；当前项目未显式发现前端测试入口，因此先不强制。

## Files to change

预计修改：

- `src/termbridge/api.py`
- `src/termbridge/services.py`
- `tests/test_api.py`
- `tests/test_terminal_service.py`
- `web/src/api/sessions.ts`
- `web/src/stores/toast.ts`
- `web/src/components/AppToast.vue`
- `web/src/components/AppShell.vue`
- 可能涉及 i18n 文案文件（如 error toast title 需要翻译 key）

不计划修改：

- 不新增大量业务异常类。
- 不改变认证/授权模型。
- 不改变主要 session/tmux lifecycle 设计。

## Verification plan

后端：

```bash
uv run pytest tests/test_api.py tests/test_terminal_service.py tests/test_services.py
uv run mypy src tests
uv run ruff check src tests
```

前端：

```bash
yarn --cwd web typecheck
yarn --cwd web lint
```

如变更触及 toast UI 样式较多，可追加：

```bash
yarn --cwd web build
```

## Risks

1. 如果一次性把所有 endpoint 的错误码改得过细，容易扩大范围；建议先统一响应结构，再逐步细化业务 code。
2. 未捕获异常 handler 可能和当前 `RequestLoggingMiddleware` 都记录 traceback，需避免重复日志过多；第一步可接受重复，后续再收敛。
3. 前端只支持新 `{ code, error }` 后，如果后端仍有漏网的非结构化错误，前端会显示 fallback；测试必须覆盖常见失败路径。
4. `tmux` 超时被吞掉后，可能隐藏真实环境问题；需要在日志中 warning 记录超时命令。

## Rollback

1. 移除 FastAPI exception handlers，恢复默认 `detail` 响应。
2. 恢复前端 `readError()` 对旧结构的读取方式。
3. 恢复 AppShell 操作失败时写页面级 `error` 的逻辑。
4. 恢复 `tmux` 超时向上抛出的行为。

## User review notes

- 用户确认：响应体 `{ code, error }`，不加 `detail`，不向后兼容。
- 用户确认：错误码使用 `snake_case`。
- 用户确认：操作失败不在按钮附近额外显示错误。
- 用户要求：toast 添加 `title`。
- 用户要求：toast 实现主题色，至少区分 `success` / `error`。
