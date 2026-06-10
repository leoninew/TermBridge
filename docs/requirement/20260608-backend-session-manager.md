# 后端 ttyd 会话管理需求 / Backend ttyd Session Manager Requirement

Review status: Accepted

## Background

项目目标是实现一个 Web Terminal Workspace，用浏览器统一管理多个 CLI 会话。当前 ttyd `1.7.7-40e79c7` 已就绪，需要先实现后端能力，通过 Python、uv、FastAPI 提供 API 来操作 ttyd 并管理会话生命周期。

## Goals

- 基于 Python + uv + FastAPI 实现后端服务骨架。
- 提供会话管理能力，用于创建、查看、删除/停止 ttyd 会话。
- 后端负责为每个会话维护必要元数据，例如 session id、名称、工作目录、runtime、端口、进程状态、创建/更新时间。
- 后端能够启动 ttyd 进程，并将指定 runtime 运行在指定 workspace 下。
- 后端能够停止 ttyd 进程并释放对应会话资源。
- 为未来前端、反向代理、移动端访问预留清晰的 HTTP API 边界。
- 开发过程使用 mypy、ruff 做类型检查、格式化和代码质量检查，使用 pytest 做单元测试。

## Non-goals

- 本阶段不实现前端 UI。
- 本阶段不实现认证、权限、多用户隔离。
- 本阶段不实现 HTTPS、Caddy/Nginx 配置。
- 本阶段不实现持久化数据库；除非后续设计阶段另行确认，MVP 可先使用内存会话注册表。
- 本阶段不实现 WebSocket 终端转发；终端交互由 ttyd 自身提供。
- 本阶段不实现 Claude/Codex/Gemini 等 runtime 的高级集成能力，只负责按配置启动命令。

## User scenarios

1. 用户通过 API 创建一个会话，指定名称、workspace 和 runtime，后端分配端口并启动 ttyd。
2. 用户通过 API 查看当前所有会话及其运行状态。
3. 用户通过 API 查看单个会话详情，包括 ttyd 访问信息和状态。
4. 用户通过 API 停止/删除一个会话，后端终止对应 ttyd 进程并移除注册信息。
5. 开发者可以通过 pytest 验证会话管理逻辑，通过 ruff/mypy 验证代码质量。

## Acceptance criteria

- 项目包含可由 uv 管理的 Python 后端工程配置。
- FastAPI 应用可启动，并暴露基础健康检查接口。
- 提供创建、列表、详情、停止/删除会话的 API。
- 会话创建时能够构造并启动 ttyd 进程，使用已就绪的 ttyd `1.7.7-40e79c7`。
- 会话停止时能够终止对应进程，并更新/移除会话状态。
- 端口分配避免与当前已注册会话冲突。
- 单元测试覆盖核心会话注册、端口分配、启动命令构造、停止流程。
- ruff、mypy、pytest 能在本地运行，并作为验证阶段记录结果。

## Open questions

- 后端代码应放在仓库根目录，还是放在现有子目录中？当前 README 未指定实际工程目录。
- runtime 支持列表和默认命令映射是否只包含 README MVP 中的 Claude Code、Codex、PowerShell，还是也包含 Bash？
- API 路径命名是否采用 `/api/sessions` 前缀？
- 创建会话后返回的 ttyd URL 是直接端口 URL，还是只返回端口并由前端/代理拼装？
- ttyd 可执行文件路径是否假定在 PATH 中，还是需要配置项指定？

## Decisions

- 流程模式使用严格模式 / strict。
- 第一阶段聚焦后端，不实现前端。
- 使用 Python、uv、FastAPI。
- 使用 mypy、ruff、pytest 作为开发质量与验证工具。
- ttyd 版本 `1.7.7-40e79c7` 已就绪，可作为外部依赖使用。

## User review notes

- 待用户 review。若确认需求或要求进入规格阶段，将本需求状态更新为 `Accepted`。
