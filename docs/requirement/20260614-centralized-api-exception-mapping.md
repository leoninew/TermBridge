# 集中封装 API 业务异常映射

Review status: Accepted

## Goal

将后端业务异常到 HTTP status/code/error 的转换逻辑集中封装，减少各个 API handler 中重复的 `try/except` 映射逻辑，并保持现有 API 错误响应格式。

## Non-goal

- 不重构 service 层业务异常类型体系。
- 不改变前端 API 调用协议。
- 不引入新的错误响应 envelope 格式。
- 不处理表单字段级错误协议设计。

## Acceptance

- API 业务异常映射集中定义在统一位置。
- 可删除主要 endpoint 中仅用于异常映射的重复 `try/except`。
- 保持错误响应结构为 `{ "code": string, "error": string }`。
- 保持请求校验错误、HTTPException 和未处理异常的统一处理逻辑。
- 现有后端测试通过，必要时补充或调整测试覆盖集中异常映射。

## Risk

- 部分接口原本对同一异常类型可能有不同错误文案；集中映射时需避免破坏前端或测试对错误文案的依赖。
- FastAPI exception handler 注册顺序和异常类型匹配需要验证，避免业务异常落入通用 500 handler。
