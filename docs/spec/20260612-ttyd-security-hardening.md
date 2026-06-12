# ttyd WebSocket 安全加固规格

Review status: Accepted

当前：严格模式 / strict，规格 / Spec

## 需求依据

基于 `docs/requirement/20260612-ttyd-security-hardening.md`。本任务先完成 ttyd 子进程安全默认值加固：显式绑定 `--interface`，默认开启 Basic credential 认证，空密码时生成不少于 12 位的随机密码并持久化到 `.termbridge/sessions.json`。

实施中发现 Chrome 会阻止 iframe/subresource 加载包含 embedded credentials 的 URL（例如 `http://user:pass@host/`）。因此访问层从 URL userinfo 方案调整为 FastAPI terminal proxy：浏览器访问 TermBridge 同源 `/terminal/<session_id>/`，后端向本地 ttyd 添加 `Authorization: Basic ...` 并代理 HTTP 与 WebSocket。

后续浏览器 WebSocket 验证又发现 ttyd 前端会使用：

```javascript
new WebSocket(this.options.wsUrl, ["tty"])
```

因此 FastAPI WebSocket proxy 必须转发 `tty` subprotocol：浏览器侧 `websocket.accept(subprotocol="tty")`，upstream 侧 `websockets.connect(..., subprotocols=["tty"])`。

## 概览

实现分为五个层面：

1. **配置层**：在 `Settings` 中新增 ttyd interface 与 credential 配置，默认本机回环绑定、默认 Basic credential。
2. **模型层**：在 session entry 中保存已解析的 ttyd credential，支持随机密码跨重启复用。
3. **命令构造层**：启动 ttyd 时追加 `--interface <value>`，并在 Basic 模式下追加 `--credential <username>:<password>`。
4. **访问 URL 层**：`SessionResponse.url` 指向 TermBridge 同源 terminal proxy 路径 `/terminal/<session_id>/`，不再包含 embedded credentials。
5. **代理层**：FastAPI 代理 ttyd HTTP 静态资源、`/token` 和 `/ws` WebSocket 连接，并在转发到 ttyd 时注入 Basic Authorization header；WebSocket 连接同时协商 `tty` subprotocol。

## 设计决策

### 1. ttyd interface 独立配置

新增配置：

```python
ttyd_interface: str = "127.0.0.1"
```

对应环境变量：

```env
TERMBRIDGE_TTYD_INTERFACE=127.0.0.1
```

启动命令始终包含：

```text
--interface <settings.ttyd_interface>
```

不复用 `TERMBRIDGE_HOST`，因为 API bind address 和 ttyd 子进程 bind address 是不同安全边界。即使未来 API 绑定 `0.0.0.0`，ttyd 子进程默认仍只绑定 `127.0.0.1`。

### 2. ttyd credential mode

新增配置：

```python
ttyd_credential_mode: Literal["basic", "none"] = "basic"
ttyd_credential_username: str = "termbridge"
ttyd_credential_password: str = ""
```

对应环境变量：

```env
TERMBRIDGE_TTYD_CREDENTIAL_MODE=basic
TERMBRIDGE_TTYD_CREDENTIAL_USERNAME=termbridge
TERMBRIDGE_TTYD_CREDENTIAL_PASSWORD=
```

行为：

- `basic`：启动 ttyd 时传入 `--credential <username>:<password>`。
- `none`：启动 ttyd 时不传入 `--credential`。

`pydantic-settings` 通过 `Literal` 限制 mode 只能是 `basic` 或 `none`。

### 3. 随机密码生成

当 `ttyd_credential_mode == "basic"` 且 `ttyd_credential_password == ""` 时，使用 Python 标准库安全随机能力生成随机密码：

```python
secrets.token_urlsafe(18)
```

说明：

- `secrets` 是面向密码学用途的标准库随机模块。
- `token_urlsafe(18)` 输出长度通常约 24 个 URL-safe 字符，满足“不少于 12 位”。
- 实现中通过测试断言生成结果长度 `>= 12`。

### 4. credential 持久化粒度

在 `SessionEntryRecord` 增加字段保存当前 session entry 使用的 ttyd credential：

```python
class TtydCredential(BaseModel):
    mode: Literal["basic"] = "basic"
    username: str
    password: str

class SessionEntryRecord(BaseModel):
    ...
    ttyd_credential: TtydCredential | None = None
```

解析规则：

- mode 为 `none`：返回 `None`，entry 的 `ttyd_credential` 置为 `None`。
- mode 为 `basic` 且配置密码非空：使用配置 username/password，并写入 entry。
- mode 为 `basic` 且配置密码为空：
  - 如果 entry 已有同 username 的非空 credential，则复用。
  - 否则生成新 password 并写入 entry。
- 如果 username 改变，已有随机 credential 不复用，生成新 credential。

该设计让随机密码按 session entry 持久化：同一 session 停止后重新 start 时复用已有随机密码；新建 session 会获得自己的随机密码。

### 5. ttyd 命令构造

`_build_ttyd_command()` 接收已解析 credential：

```python
command = [
    ttyd_executable,
    "--writable",
    "--interface",
    self._settings.ttyd_interface,
    "--port",
    str(port),
    "--cwd",
    str(workspace),
]
if credential is not None:
    command.extend(["--credential", f"{credential.username}:{credential.password}"])
command.extend(runtime_command)
```

命令形态：

```text
ttyd --writable --interface <interface> --port <port> --cwd <workspace> [--credential user:password] <runtime-command>
```

### 6. Session URL 与 FastAPI proxy

`SessionResponse.url` 不再指向 ttyd 端口，也不包含 credential。它指向 TermBridge 同源路径：

```text
/terminal/<session_id>/
```

如果配置了 `public_base_url`：

```text
<public_base_url>/terminal/<session_id>/
```

后端提供代理目标解析：

```python
@dataclass(frozen=True)
class TerminalProxyTarget:
    base_url: str
    credential: TtydCredential | None
```

`SessionService.terminal_proxy_target(session_id)` 只允许 running session，返回内部 ttyd base URL（例如 `http://127.0.0.1:19001`）和 credential。

### 7. FastAPI HTTP proxy

新增 HTTP route：

```text
GET /terminal/<session_id>/<path:path>
```

行为：

- `/terminal/<session_id>` 使用 307 redirect 到 `/terminal/<session_id>/`，避免 ttyd HTML 内相对路径解析错误。
- 查询 session proxy target。
- 将请求转发到 `<target.base_url>/<path>`。
- 保留 query string。
- 如果 session 有 credential，后端添加：

```text
Authorization: Basic <base64(username:password)>
```

- 过滤 hop-by-hop headers，如 `connection`、`transfer-encoding`、`upgrade`、`content-length`、`content-encoding`。
- 用于代理 ttyd HTML、前端资源和 `/token`。

### 8. FastAPI WebSocket proxy

新增 WebSocket route：

```text
/terminal/<session_id>/ws
```

行为：

- 查询 session proxy target。
- 将目标 URL 从 `http://...` 转换为 `ws://.../ws`，并保留 query string。
- 从浏览器请求头 `Sec-WebSocket-Protocol` 解析 subprotocol 列表。
- 如果浏览器请求了 `tty`，则对浏览器执行 `websocket.accept(subprotocol="tty")`。
- 如果浏览器请求了 `tty`，则对 upstream ttyd 执行 `websockets.connect(..., subprotocols=["tty"])`。
- 使用 `websockets.connect(..., additional_headers={Authorization: ...}, proxy=None)` 连接 ttyd。
- 双向转发 browser WebSocket 与 ttyd WebSocket 的 text/bytes frame。
- 任一方向关闭后取消另一方向。
- session 不存在或不 running 时关闭 WebSocket。

`tty` subprotocol 是必要行为，不是可选优化。漏掉时浏览器可能在发送任何 terminal message 前异常关闭，DevTools 表现为 WebSocket close code `1006`，后端计数常见为 `client_messages=0 upstream_messages=0`。

### 9. Vite dev proxy

开发服务器需要代理 `/terminal` 到后端并启用 WebSocket：

```ts
'/terminal': {
  target: 'http://127.0.0.1:9008',
  ws: true,
}
```

这样前端开发环境中的 iframe `/terminal/<session_id>/` 和 WebSocket `/terminal/<session_id>/ws` 都可以到达 FastAPI proxy。

## 影响组件

- `src/termbridge/settings.py`
  - 新增 ttyd interface 与 credential settings。
- `src/termbridge/models.py`
  - 新增 `TtydCredential` 模型。
  - `SessionEntryRecord` 增加 `ttyd_credential` 字段。
- `src/termbridge/services.py`
  - 解析 ttyd credential。
  - 生成随机密码。
  - 构造带 `--interface` 和可选 `--credential` 的 ttyd 命令。
  - 构造 `/terminal/<session_id>/` URL。
  - 提供 terminal proxy target。
- `src/termbridge/api.py`
  - 新增 terminal HTTP/WebSocket proxy routes。
  - HTTP 和 WebSocket upstream 请求注入 Basic Authorization header。
  - WebSocket proxy 转发 `tty` subprotocol。
- `frontend/vite.config.ts`
  - 新增 `/terminal` dev proxy，启用 WebSocket。
- `pyproject.toml` / `uv.lock`
  - 新增 runtime dependencies：`httpx` 和 `websockets`。
- `.env.sample`
  - 增加新增配置说明。
- `tests/test_services.py` / `tests/test_api.py`
  - 覆盖命令构造、状态持久化、proxy URL、proxy target 和 HTTP proxy Authorization header。

## 接口

### 环境变量

```env
TERMBRIDGE_TTYD_INTERFACE=127.0.0.1
TERMBRIDGE_TTYD_CREDENTIAL_MODE=basic
TERMBRIDGE_TTYD_CREDENTIAL_USERNAME=termbridge
TERMBRIDGE_TTYD_CREDENTIAL_PASSWORD=
```

### Session response URL

```text
/terminal/<session_id>/
```

### 内部 ttyd target

```python
TerminalProxyTarget(base_url="http://127.0.0.1:<port>", credential=...)
```

### WebSocket subprotocol

浏览器请求：

```text
Sec-WebSocket-Protocol: tty
```

FastAPI 接受浏览器连接：

```python
await websocket.accept(subprotocol="tty")
```

FastAPI 连接 upstream ttyd：

```python
websockets.connect(..., subprotocols=["tty"])
```

## 风险

- FastAPI WebSocket proxy 增加了转发层，高频 terminal 输出、取消行为和 close code 传播可能仍需调优。
- 需要浏览器级验证，因为 TestClient 级 WebSocket smoke 不能完整覆盖 ttyd 前端、`/token`、`tty` subprotocol 和 binary frame 行为。
- URL userinfo 不再使用，可避开 Chrome embedded credential subresource blocking。
- 该方案仍是本地加固，不是托管式多用户授权边界。

## 已考虑方案

### 1. iframe 中使用 URL userinfo

浏览器验证后拒绝。Chrome 会阻止 subresource requests whose URLs contain embedded credentials。

### 2. 用户手动打开 ttyd 并输入 Basic Auth

本轮不采用，因为会丢失嵌入式 terminal workflow。

### 3. 移除 Basic Auth，只依赖 `--interface 127.0.0.1`

不采用，因为已接受的需求要求默认启用 Basic credential。

### 4. 只代理 HTTP，不代理 WebSocket

不采用。ttyd HTML 可以加载不代表 terminal 可交互；terminal 交互依赖 `/ws` WebSocket。

## 用户评审记录

- 用户观察到 Chrome 阻止 embedded credential iframe URL 后，要求开始尝试 FastAPI proxy。
- 后续 WebSocket 1006 排查确认缺少 `tty` subprotocol 是关键问题，因此规格补充两端 subprotocol 协商要求。
