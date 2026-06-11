# 全局异常结构与 UI 错误状态处理需求

Review status: Accepted

当前：标准模式 / standard，需求阶段 / Requirement

## Background

当前后端部分异常会以未捕获异常形式冒泡到 ASGI 层，最终表现为 `Internal Server Error`，响应体缺少稳定的 `code` / `error` 结构。前端在部分操作失败后会把错误写入页面级 `error` 状态，导致会话列表等主要内容被错误面板替换，用户无法继续查看现有状态或执行恢复操作。

最近观察到的典型场景：启动 session 时 `tmux` 检查命令超时，后端请求失败，前端会话区域被错误状态覆盖，而不是保留列表并通过 toast 告知启动失败。

## Goals

1. 后端 API 错误响应使用统一、稳定的 JSON 结构，至少包含：
   - `code`：机器可识别错误码
   - `error`：用户/开发者可读错误信息
2. 请求级别未捕获异常也应被统一转换为结构化错误响应，而不是默认 `Internal Server Error` 文本。
3. 后端日志仍应保留异常堆栈，便于诊断；响应体不暴露过多内部堆栈细节。
4. 前端 API 层应能读取统一错误结构，并把 `code` / `error` 转换为合适的 `Error` 或应用错误对象。
5. 会话管理 UI 中，操作级错误（start/stop/delete/close all 等）不应让会话列表消失。
6. 操作级错误优先通过 toast 展示，同时保留当前列表和已打开 session 状态。
7. 页面级加载失败仍可以显示页面级错误，但应尽量避免清空已有可用数据。

## Non-goals

- 本需求不引入复杂错误分类框架或大量自定义异常类。
- 本需求不要求一次性重构所有业务异常来源。
- 本需求不设计国际化后的完整错误文案矩阵；可先保留后端返回 message，前端后续再细化映射。
- 本需求不改变已有 HTTP status 的基本语义，例如 400、404、409、500、503。
- 本需求不处理认证/授权错误模型，因为当前项目还没有内置 auth。

## User scenarios

1. 用户启动一个 stopped session，但底层 `tmux` 命令超时：
   - 后端返回结构化 JSON，例如 `code=terminal_command_timeout`。
   - 前端通过 toast 提示启动失败。
   - 会话列表仍显示，用户可以重试、停止、删除或进入环境管理。

2. 用户打开会话页时 session tree 加载失败：
   - 如果之前已有列表数据，保留旧数据并通过 toast 或轻量提示说明刷新失败。
   - 如果没有可用数据，再显示页面级错误/空状态。

3. 后端发生未预期异常：
   - 日志记录完整 traceback。
   - API 响应仍为统一结构，例如 `code=internal_error`，`error=Internal server error` 或更合适的简短说明。
   - 前端不会把未结构化响应显示为难以理解的默认文本。

## Acceptance criteria

- [ ] 所有 API 错误响应至少统一为 `{ "code": string, "error": string }`。
- [ ] FastAPI/Starlette 的 `HTTPException` 响应也会被转换为统一结构。
- [ ] 未捕获异常有统一兜底 handler，响应结构稳定，同时后端日志保留异常堆栈。
- [ ] 前端 `readError()` 支持新的 `code` / `error` 响应结构，不保留旧的 `detail` / `message` 兼容逻辑。
- [ ] `handleStart()` 等操作失败时使用 toast 展示错误，不再把 session list 替换成错误面板。
- [ ] `loadSessions()` 失败时不主动清空已有 `sessions` / `sessionTree`；有旧数据时保留旧数据。
- [ ] 添加或更新后端 API 测试，覆盖结构化错误响应。
- [ ] 添加或更新前端相关测试/类型检查，至少保证 API 错误读取逻辑和组件类型检查通过。

## Open questions

1. 错误响应是否需要保留 FastAPI 常见的 `detail` 字段以兼容现有前端/调试习惯？
   - Decision: 不向后兼容旧结构，只返回 `{ "code": string, "error": string }`，不保留 `detail`。
2. 前端 toast 是否需要区分 success/error 样式？当前 toast store 只有 title/open，没有 variant。
   - Decision: Toast 要实现主题色，至少区分 `success` 和 `error`。
3. 操作失败是否只 toast，还是同时在局部按钮附近保留短暂错误提示？
   - Decision: 操作失败只通过 toast 展示，不在按钮附近额外显示错误。
4. 后端错误码命名风格采用哪种：`snake_case`（如 `session_not_found`）还是大写枚举（如 `SESSION_NOT_FOUND`）？
   - Decision: 错误码使用 `snake_case`。

## Initial discussion proposal

建议采用较轻的分层方案：

1. 后端新增统一错误响应 helper/handler，而不是继续增加大量异常类。
2. 以现有异常和 HTTP status 为主，补充少量错误码映射：
   - 404：`not_found` 或更具体的 `session_not_found`
   - 400：`bad_request` / `invalid_terminal_config`
   - 409：`conflict`
   - 503：`service_unavailable`
   - 未捕获异常：`internal_error`
3. 对 `subprocess.TimeoutExpired` 这类基础设施异常，在 API 边界或服务边界转换为 503 + `terminal_command_timeout`，但不必为每种异常都创建新 exception class。
4. 前端 API 层定义轻量 `ApiError`，保留 `code`、`message`、`status`。
5. 会话页将操作失败从页面级 `error` 改为 toast；页面级 `error` 只用于初始/无数据加载失败。

## Decisions

- 错误响应不向后兼容旧结构，统一使用 `{ "code": string, "error": string }`。
- 响应体不保留 `detail` 字段。
- Toast 添加 `title` 字段，以支持更明确的提示展示。
- Toast 实现主题色，至少区分 `success` 和 `error` 两种状态。
- 错误码使用 `snake_case`。
- 操作失败只通过 toast 展示，不在按钮附近额外显示错误。

## User review notes

- 用户明确指出这是两个问题：
  1. 请求级别异常没有输出 `code` / `error`。
  2. UI 被异常状态搞没了。
- 用户明确指出：一直添加异常类并不是解决办法。
- 用户明确要求：toast 要实现主题色。
