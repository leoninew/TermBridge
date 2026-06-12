# ttyd WebSocket 安全加固需求

Review status: Accepted

当前：严格模式 / strict，需求 / Requirement

## 背景

当前 TermBridge 启动受管理的 `ttyd` 子进程时未显式传入 `--interface`。本地验证的 `ttyd 1.7.7-40e79c7` 在未指定 interface 时监听 `0.0.0.0`，会让每个 session 的 ttyd 端口默认暴露到所有 IPv4 网卡。TermBridge 当前又需要把 terminal 嵌入前端 iframe 使用，因此默认暴露 ttyd 端口和缺少认证都不合适。

本需求最初只计划加固 ttyd 子进程自身：显式绑定本地回环地址，并开启 ttyd Basic credential 认证；当时明确暂不实现 TermBridge 后端 WebSocket 代理或统一认证入口。

实施和浏览器验证后发现：虽然 ttyd Basic Authentication 支持标准 HTTP `Authorization: Basic ...` 请求头，且 URL userinfo 在普通 HTTP 客户端里可用，但 Chrome 会阻止 iframe/subresource 加载包含 embedded credentials 的 URL，例如 `http://user:pass@host/`。这使“前端 iframe 直接访问带 credential 的 ttyd URL”不可行。为保留嵌入式 terminal workflow，本需求修订为：在保留 ttyd Basic credential 与本地绑定的前提下，引入 FastAPI HTTP/WebSocket proxy，由后端向本地 ttyd 注入 `Authorization: Basic ...`。

## 目标

- 新增 `TERMBRIDGE_TTYD_INTERFACE` 配置，用于填充 ttyd 启动参数 `--interface`。
- `TERMBRIDGE_TTYD_INTERFACE` 默认值为 `127.0.0.1`，使受管理的 ttyd 子进程默认只监听本机回环地址。
- 新增 `TERMBRIDGE_TTYD_CREDENTIAL_MODE` 配置，用于控制是否给 ttyd 添加 Basic credential 认证。
- `TERMBRIDGE_TTYD_CREDENTIAL_MODE` 默认值为 `basic`，允许使用 `none` 覆盖关闭。
- 新增 `TERMBRIDGE_TTYD_CREDENTIAL_USERNAME`，默认值为 `termbridge`。
- 新增 `TERMBRIDGE_TTYD_CREDENTIAL_PASSWORD`，默认值为空；为空时使用常规安全随机算法生成不少于 12 位的随机密码。
- 随机生成的 ttyd credential 密码需要持久化到 `.termbridge/sessions.json` 以供后续使用。
- ttyd Basic Authentication 支持标准 HTTP `Authorization: Basic ...` 请求头；本地已验证未授权请求返回 401，带正确 Authorization 头返回 200。
- 浏览器不直接访问带 credential 的 ttyd URL；`SessionResponse.url` 指向 TermBridge 同源 `/terminal/<session_id>/`。
- FastAPI HTTP proxy 代理 ttyd HTML、静态资源和 `/token`，并在 upstream 请求中添加 Basic Authorization header。
- FastAPI WebSocket proxy 代理 `/terminal/<session_id>/ws` 到 ttyd `/ws`，并在 upstream 握手中添加 Basic Authorization header。
- FastAPI WebSocket proxy 需要协商 ttyd 前端要求的 `tty` WebSocket subprotocol：浏览器侧 `accept(subprotocol="tty")`，upstream 侧 `websockets.connect(..., subprotocols=["tty"])`。
- Vite 开发服务器需要支持 `/terminal` HTTP 与 WebSocket proxy。
- 本任务面向本地使用场景，不要求对日志、进程参数或状态文件中的 ttyd credential 做脱敏；API 响应不应返回 credential。
- 本任务不要求向后兼容旧的 `.termbridge/sessions.json` 数据结构。

## 非目标

- 不实现统一用户登录、授权、多用户隔离或 session ownership 模型。
- 不引入 HTTPS/WSS、证书管理、反向代理配置或公网部署加固。
- 不实现 credential 脱敏、密钥轮换、加密存储或 secret manager 集成。
- 不保持旧 session 状态文件格式的向后兼容。
- 不改变 `tmux` session/window 生命周期策略。
- FastAPI proxy 是本地加固和 iframe 嵌入兼容层，不作为公网多用户安全边界。

## 用户场景

1. **默认本地安全启动**
   - 用户不设置任何新增环境变量。
   - TermBridge 启动 session 时，ttyd 命令包含 `--interface 127.0.0.1`。
   - TermBridge 启动 session 时，ttyd 命令包含 Basic credential 参数，用户名为 `termbridge`，密码为空配置触发随机生成并持久化。
   - 前端 iframe 使用 `/terminal/<session_id>/` 访问 terminal，不接触 credential。

2. **关闭 ttyd credential**
   - 用户设置 `TERMBRIDGE_TTYD_CREDENTIAL_MODE=none`。
   - TermBridge 启动 session 时不向 ttyd 传入 `--credential`。
   - `--interface` 仍按 `TERMBRIDGE_TTYD_INTERFACE` 生效。
   - FastAPI proxy 仍提供同源 `/terminal/<session_id>/` 入口，但不会向 upstream 添加 Authorization header。

3. **显式配置 ttyd credential**
   - 用户设置 `TERMBRIDGE_TTYD_CREDENTIAL_MODE=basic`、`TERMBRIDGE_TTYD_CREDENTIAL_USERNAME=<user>`、`TERMBRIDGE_TTYD_CREDENTIAL_PASSWORD=<password>`。
   - TermBridge 启动 session 时向 ttyd 传入 `<user>:<password>` 形式的 Basic credential。
   - FastAPI proxy 使用该 credential 访问本地 ttyd，前端 iframe 不需要也不会收到 credential。

4. **显式修改 ttyd 监听地址**
   - 用户设置 `TERMBRIDGE_TTYD_INTERFACE=<interface-or-address>`。
   - TermBridge 启动 session 时把该值传给 ttyd `--interface`。
   - FastAPI proxy target 使用相同 interface 和分配端口构造内部 ttyd base URL。

## 验收标准

- `Settings` 支持：
  - `ttyd_interface`，环境变量 `TERMBRIDGE_TTYD_INTERFACE`，默认 `127.0.0.1`。
  - `ttyd_credential_mode`，环境变量 `TERMBRIDGE_TTYD_CREDENTIAL_MODE`，默认 `basic`，支持 `basic` 和 `none`。
  - `ttyd_credential_username`，环境变量 `TERMBRIDGE_TTYD_CREDENTIAL_USERNAME`，默认 `termbridge`。
  - `ttyd_credential_password`，环境变量 `TERMBRIDGE_TTYD_CREDENTIAL_PASSWORD`，默认空字符串。
- ttyd 启动命令始终包含 `--interface <configured-interface>`，除非后续规格阶段发现当前 ttyd 版本对某些 host 不支持该参数并记录调整。
- 当 credential mode 为 `basic` 时，ttyd 启动命令包含 `--credential <username>:<password>`。
- 当 credential mode 为 `none` 时，ttyd 启动命令不包含 `--credential`。
- 当 credential mode 为 `basic` 且配置密码为空时，系统使用常规安全随机算法生成不少于 12 位的随机密码，并持久化到 `.termbridge/sessions.json`。
- 已生成并持久化的随机密码在 session 状态需要复用时可被读取使用。
- `SessionResponse.url` 不包含 embedded credential，指向 `/terminal/<session_id>/` 或 `<public_base_url>/terminal/<session_id>/`。
- FastAPI HTTP proxy 能访问受 Basic Auth 保护的 ttyd HTML、静态资源和 `/token`，并向 upstream 添加 `Authorization: Basic ...`。
- FastAPI WebSocket proxy 能访问受 Basic Auth 保护的 ttyd `/ws`，并向 upstream 添加 `Authorization: Basic ...`。
- FastAPI WebSocket proxy 能协商并转发 ttyd 需要的 `tty` subprotocol，避免浏览器 1006 异常断开。
- `.env.sample` 记录新增配置项和默认值。
- 相关单元测试覆盖：默认 interface、credential basic 默认行为、credential none 覆盖、显式 credential、空密码随机生成不少于 12 位并持久化、proxy URL、proxy target、HTTP proxy Authorization header。
- 当前任务不要求旧 sessions 文件无迁移即可继续读取；测试可以按新的模型断言。

## 决策

- 流程模式使用严格模式 / strict。
- ttyd interface 默认固定为 `127.0.0.1`，不直接复用 `TERMBRIDGE_HOST`。
- ttyd Basic credential 默认开启，使用 `TERMBRIDGE_TTYD_CREDENTIAL_MODE=none` 才关闭。
- 早期“不做 WebSocket proxy”的决策已被浏览器验证推翻；最终决策是实现 FastAPI HTTP/WebSocket proxy，以避免 Chrome embedded credential blocking。
- 本地使用场景下，credential 可以出现在命令、状态文件和日志相关输出中，不做脱敏要求；但 API 响应不返回 credential。
- 不向后兼容旧的 `.termbridge/sessions.json` 数据结构。

## 假设

- 随机密码按 session entry 生成并保存，以便该 session 后续启动/重启继续使用。
- `ttyd --interface 127.0.0.1` 在目标本地环境可用；已在本地确认 `ttyd --help` 包含 `--interface` 参数。
- ttyd 前端通过 `/token` 和 `/ws` 工作，FastAPI proxy 需要覆盖这两个入口。
- ttyd 前端 WebSocket 使用 `tty` subprotocol，代理两端都需要协商该 subprotocol。

## 未决问题

暂无需要用户确认的未决事项。

## 风险

- Basic credential 如果通过进程命令行或状态文件暴露，适合本地受信环境，不适合不受信网络或多人环境。
- `--interface 127.0.0.1` 会阻止其他设备直连 ttyd 端口；这是本任务的安全目标，但可能改变用户从局域网直接访问 ttyd session 的行为。
- FastAPI WebSocket proxy 增加了一层转发，高频 terminal 输出、取消行为和 close code 传播仍可能需要后续调优。
- 不向后兼容旧 sessions 文件可能需要用户删除或重建本地 `.termbridge` 状态。

## 用户评审记录

- 初始需求是只添加 ttyd Basic 认证和本地 interface 绑定，不准备实现 WebSocket proxy。
- 浏览器验证证明 embedded credential iframe URL 行不通后，用户允许并推动改为 FastAPI proxy 方案。
- WebSocket 1006 排查中确认 ttyd 前端要求 `Sec-WebSocket-Protocol: tty`，proxy 必须在浏览器侧和 upstream ttyd 侧都转发该 subprotocol。
