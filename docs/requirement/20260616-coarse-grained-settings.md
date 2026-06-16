# 粗粒度配置化

Review status: Accepted

当前：轻量模式 / light，需求 / Requirement。

## Background

`BODY_LOG_LIMIT` 已迁移到 `Settings`，但调用点不应逐项传递配置项，否则配置增长后会产生参数膨胀。当前任务继续把运行环境、部署、安全策略、超时和日志相关的硬编码值收敛到粗粒度 `Settings` 管理。

## Goal

- 采用传递 `Settings` 对象的方式接线，避免 `foo=settings.foo` 形式在多个调用点扩散。
- 增加粗粒度配置项：API 监听地址/端口、terminal HTTP proxy 超时、进程关闭超时、ttyd 是否 writable、是否服务 Web、Web 目录、uvicorn access log 开关。
- 更新 `.env.sample` 和相关测试。

## Non-goal

- 不把所有协议常量、路由路径、错误码、UI 细节都配置化。
- 不引入复杂的嵌套配置对象或外部配置文件格式。
- 不实现前端 Vite proxy/env 配置化；本次聚焦后端 `Settings` 和运行时接线。
- 不修改 Docker 启动策略；后续可基于新增 API host/port 配置再调整。

## User scenarios

- 本地开发或部署时，API 默认监听 `localhost:9008`，也可通过 `.env` 调整 API 服务监听地址/端口，而不改代码。
- 慢环境中，可通过 `.env` 调整 terminal proxy 和进程关闭超时。
- 安全敏感环境中，可关闭 ttyd writable；快捷方式只保存用户定义的启动命令，不按命令内容做特殊分类。
- 生产排障时，可启用 uvicorn access log。

## Acceptance

- `Settings` 包含新增配置项，并支持 `TERMBRIDGE_` 环境变量覆盖。
- `main.py` CLI 默认值来自 `Settings`，CLI 参数仍可覆盖配置。
- `RequestLoggingMiddleware` 和其他需要配置的组件通过 `Settings` 对象读取配置，而不是逐项传参。
- terminal HTTP proxy 使用配置化 timeout。
- `TtydProcessAdapter` 使用配置化 shutdown timeout。
- 快捷方式不引入 unrestricted/full-access 特殊处理，所有快捷方式按同一逻辑保存和展示。
- ttyd 启动是否包含 `--writable` 可配置。
- `create_app()` 使用配置化 `serve_web` / `web_dir` 默认值。
- logging config 可根据配置启用/禁用 uvicorn access log。
- `.env.sample` 和测试同步更新。

## Open questions

暂无需要用户确认的未决事项；本次按用户指定“轻量模式，直接实现”推进。

## Decisions

- 粗粒度配置进入现有 `Settings`，保持 `TERMBRIDGE_` env prefix。
- 调用点传 `Settings` 对象，避免单项配置参数膨胀。
- 本次不把 Vite/Docker 一并改掉，避免扩大范围。

## Risk

- API host/port 从 CLI 默认值改为 Settings 默认值后，需要保证 CLI 覆盖语义不破坏现有命令行使用方式。
- 快捷方式命令属于用户自由定义内容，不应因命令参数名称被额外过滤或分类。
