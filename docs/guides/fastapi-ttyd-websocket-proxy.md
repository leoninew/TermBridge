# FastAPI 代理 ttyd WebSocket 与认证实践

本文记录 TermBridge 在加固 ttyd 访问路径时踩过的坑和最终实践，重点覆盖 FastAPI proxy、ttyd Basic Auth、WebSocket subprotocol，以及浏览器 iframe 场景下的排查方法。

## 背景

ttyd 可以通过 `--credential <username>:<password>` 开启 Basic Authentication。最初方案曾尝试把 credential 放进 iframe URL：

```text
http://user:password@127.0.0.1:19001/
```

这个方案在普通 HTTP 客户端中可用，但浏览器会阻止 iframe/subresource 加载 embedded credentials URL。Chrome 中表现为页面或子资源无法正常加载，因此不能把 ttyd credential 直接塞进 iframe URL。

最终方案是：

- ttyd 仍然启用 Basic Auth。
- ttyd 默认只绑定本机回环地址，例如 `--interface 127.0.0.1`。
- 浏览器 iframe 访问 TermBridge 同源 URL：`/terminal/<session_id>/`。
- FastAPI 后端代理 HTTP 与 WebSocket 请求到本地 ttyd。
- FastAPI 在转发到 ttyd 时注入 `Authorization: Basic ...`。
- 浏览器侧永远不需要知道 ttyd credential。

## 推荐架构

```text
Browser iframe
  GET /terminal/<session_id>/
  WS  /terminal/<session_id>/ws
        |
        v
FastAPI terminal proxy
  - 根据 session_id 找到内部 ttyd base_url
  - 为 upstream 请求添加 Basic Authorization header
  - HTTP 代理 ttyd HTML、assets、/token
  - WebSocket 双向转发 browser <-> ttyd
        |
        v
ttyd
  http://127.0.0.1:<port>/
  Basic Auth enabled
  WebSocket subprotocol: tty
```

核心原则：

- 不把 credential 放进 iframe URL。
- 不把 ttyd 端口作为前端公开入口。
- `SessionResponse.url` 返回 `/terminal/<session_id>/`，而不是 ttyd direct URL。
- 后端 proxy target 只允许 running session。
- 认证只发生在 FastAPI 到 ttyd 的 upstream 请求中。

## ttyd 启动实践

启动 ttyd 时固定加入 interface 和可选 credential：

```python
command = [
    ttyd_executable,
    "--writable",
    "--interface",
    settings.ttyd_interface,
    "--port",
    str(port),
    "--cwd",
    str(workspace),
]
if credential is not None:
    command.extend(["--credential", f"{credential.username}:{credential.password}"])
command.extend(runtime_command)
```

建议默认值：

```env
TERMBRIDGE_TTYD_INTERFACE=127.0.0.1
TERMBRIDGE_TTYD_CREDENTIAL_MODE=basic
TERMBRIDGE_TTYD_CREDENTIAL_USERNAME=termbridge
TERMBRIDGE_TTYD_CREDENTIAL_PASSWORD=
```

空密码时由后端生成随机密码，并按 session entry 持久化。这样同一 session 停止后再次启动时可以复用 credential。

## HTTP proxy 实践

HTTP proxy 需要处理 ttyd 的 HTML、静态资源和 `/token` 请求。

关键点：

- 目标 URL 从 session 的内部 ttyd base URL 拼出来，例如 `http://127.0.0.1:19001/<path>`。
- 保留 query string。
- upstream 请求添加 Basic Authorization header。
- 返回响应时过滤 hop-by-hop headers。
- `/terminal/<session_id>` 应重定向到 `/terminal/<session_id>/`，避免相对资源路径错位。

示例：

```python
@router.get("/terminal/{session_id}", include_in_schema=False)
def redirect_terminal_root(session_id: str) -> RedirectResponse:
    return RedirectResponse(url=f"/terminal/{session_id}/", status_code=307)


@router.get("/terminal/{session_id}/{path:path}", include_in_schema=False)
async def proxy_terminal_http(session_id: str, path: str, request: Request, service: SessionServiceDep) -> Response:
    target = service.terminal_proxy_target(session_id)
    target_url = f"{target.base_url.rstrip('/')}/{path or ''}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        upstream = await client.request(
            request.method,
            target_url,
            headers=_target_headers(target.credential),
            content=await request.body(),
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_proxy_headers(upstream.headers),
    )
```

Basic Auth header 构造：

```python
def _basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


def _target_headers(credential: TtydCredential | None) -> dict[str, str]:
    if credential is None:
        return {}
    return {"Authorization": _basic_auth_header(credential.username, credential.password)}
```

建议过滤这些 response headers：

```python
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
}
```

## ttyd `/token` 与 WebSocket AuthToken 流程

`ttyd --credential <username>:<password>` 的直觉是：客户端用 HTTP Basic Auth 访问 ttyd 即可。但 ttyd 自带前端实际还有一个 WebSocket 应用层认证流程：

- HTTP endpoint 通过 `Authorization: Basic <base64(username:password)>` 保护。
- ttyd 的 `/token` endpoint 在通过 Basic Auth 后，返回 JSON：`{"token":"<base64(username:password)>"}`。
- ttyd 前端 JS 再把这个 token 作为 WebSocket 协议里的 `AuthToken` 发给 ttyd 后端。
- ttyd 后端比较 WebSocket 消息里的 `AuthToken` 和启动时保存的 credential token，匹配后才允许 terminal 会话继续。

也就是说，`/token` 不是 TermBridge 的登录 token，也不是独立的 session token；它是 ttyd 自己把 Basic credential token 暴露给 ttyd 前端 JS，用于后续 WebSocket 应用层认证的桥接 endpoint。

业务流程图：

```text
TermBridge AppShell / SessionTerminal
  iframe src="/terminal/<session_id>/"
        |
        | 1. GET /terminal/<session_id>/
        v
TermBridge FastAPI HTTP proxy
  查 session_id -> ttyd base_url=http://127.0.0.1:<port>
  upstream 添加 Authorization: Basic <base64(termbridge:password)>
        |
        | 2. GET http://127.0.0.1:<port>/
        v
ttyd HTTP server
  校验 Basic Auth
  返回 ttyd 自带 HTML/JS
        |
        | 3. iframe 内 ttyd JS 请求相对路径 /token
        v
Browser
  GET /terminal/<session_id>/token
        |
        | 4. proxy 添加相同 Basic Authorization
        v
ttyd /token
  返回 {"token":"<base64(termbridge:password)>"}
        |
        | 5. iframe 内 ttyd JS 使用 token 建立 WebSocket 认证消息
        v
Browser WebSocket
  WS /terminal/<session_id>/ws
  Sec-WebSocket-Protocol: tty
        |
        | 6. FastAPI proxy 连接 upstream ttyd /ws
        |    - additional_headers: Authorization: Basic ...
        |    - subprotocols=["tty"]
        v
ttyd WebSocket /ws
  校验 WebSocket 消息里的 AuthToken
  开始 terminal binary/text frame 交互
```

对应日志通常是：

```text
GET /terminal/<session_id>/       -> GET http://127.0.0.1:<port>/
GET /terminal/<session_id>/token  -> GET http://127.0.0.1:<port>/token
WS  /terminal/<session_id>/ws     -> WS  ws://127.0.0.1:<port>/ws subprotocol=tty
```

注意：`/token` response body 本质上包含 `base64(username:password)`。即使本项目当前定位是本地使用，也不建议长期在普通 `INFO` 日志中记录 `/terminal/<session_id>/token` 的 response body。需要排查时可以临时打开更细粒度调试，或对 token body 做脱敏。

## WebSocket proxy 实践

ttyd 前端不是普通裸 WebSocket。它会这样连接：

```javascript
this.socket = new WebSocket(this.options.wsUrl, ["tty"])
```

也就是说浏览器请求里会带：

```text
Sec-WebSocket-Protocol: tty
```

FastAPI proxy 必须同时做两件事：

1. 对浏览器 accept 时协商 `tty` subprotocol。
2. 对 upstream ttyd 连接时也传入 `subprotocols=["tty"]`。

如果漏掉这一步，浏览器可能在发送任何 terminal payload 前直接断开，DevTools 常见表现是：

```text
WebSocket disconnected
Client/Server Close Code: 1006
```

后端日志也可能显示：

```text
client_messages=0 upstream_messages=0
```

这种组合很像“连接刚建立就断”，但实际根因可能是 subprotocol 没有协商成功。

推荐实现：

```python
@router.websocket("/terminal/{session_id}/ws")
async def proxy_terminal_websocket(session_id: str, websocket: WebSocket, service: SessionServiceDep) -> None:
    target = service.terminal_proxy_target(session_id)
    target_url = target.base_url.replace("http://", "ws://", 1).replace("https://", "wss://", 1).rstrip("/")
    target_url = f"{target_url}/ws"
    if websocket.url.query:
        target_url = f"{target_url}?{websocket.url.query}"

    requested_subprotocols = [
        item.strip()
        for item in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if item.strip()
    ]
    subprotocol = "tty" if "tty" in requested_subprotocols else None

    async with websockets.connect(
        target_url,
        additional_headers=_target_headers(target.credential),
        origin=target.base_url,
        subprotocols=[subprotocol] if subprotocol else None,
        proxy=None,
    ) as upstream:
        await websocket.accept(subprotocol=subprotocol)

        async def client_to_upstream() -> None:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    await upstream.close()
                    return
                if message.get("bytes") is not None:
                    await upstream.send(message["bytes"])
                elif message.get("text") is not None:
                    await upstream.send(message["text"])

        async def upstream_to_client() -> None:
            async for message in upstream:
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_text(message)

        done, pending = await asyncio.wait(
            {asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
```

实践中建议连接成功后记录：

```text
Terminal websocket proxy connected session_id=<id> target=<ws-url> subprotocol=tty
```

如果日志中 `subprotocol=None`，而浏览器实际来自 ttyd 前端，优先检查请求头是否被中间层丢掉。

## accept 顺序

WebSocket proxy 可以先连 upstream，再 accept browser：

```python
async with websockets.connect(...) as upstream:
    await websocket.accept(subprotocol=subprotocol)
```

这样如果 session 不存在、ttyd 未运行、Basic Auth 失败或 upstream WebSocket 握手失败，可以在 accept 前关闭浏览器连接，避免前端误以为 terminal 已经可用。

但要注意：如果 upstream 连接较慢，浏览器握手会等待更久。当前本地 ttyd 场景下这个取舍通常可以接受。

## `websockets.connect` 注意事项

本项目中使用：

```python
websockets.connect(
    target_url,
    additional_headers=_target_headers(target.credential),
    origin=target.base_url,
    subprotocols=["tty"],
    proxy=None,
)
```

说明：

- `additional_headers` 用于给 ttyd upstream 握手添加 `Authorization: Basic ...`。
- `origin=target.base_url` 明确设置 Origin，避免 ttyd 或中间层对空 Origin 行为不一致。
- `subprotocols=["tty"]` 是 ttyd 前端协议要求，不能省略。
- `proxy=None` 避免本机 `ws://127.0.0.1:<port>` 连接被系统代理环境变量错误接管。

## 诊断顺序

遇到 iframe terminal 空白、WebSocket 1006、或者 ttyd 页面加载但终端不输出时，按这个顺序查：

1. **确认 HTTP proxy 可用**
   - `/terminal/<session_id>/` 返回 200。
   - HTML 中能加载 ttyd 前端资源。
   - `/terminal/<session_id>/token` 返回 200。
   - FastAPI 到 ttyd 的请求带了 `Authorization: Basic ...`。
   - `/token` 返回的 token 只用于 ttyd 前端后续 WebSocket `AuthToken`，不要误认为是 TermBridge 用户登录 token。

2. **确认 WebSocket URL 正确**
   - 浏览器连接的是 `/terminal/<session_id>/ws`。
   - Vite dev proxy 或反向代理允许 WebSocket upgrade。
   - query string 被保留。

3. **确认 subprotocol**
   - 浏览器请求头有 `Sec-WebSocket-Protocol: tty`。
   - FastAPI `websocket.accept(subprotocol="tty")`。
   - `websockets.connect(..., subprotocols=["tty"])`。
   - 日志显示 `subprotocol=tty`。

4. **确认消息是否流动**
   - 如果 `client_messages=0 upstream_messages=0`，优先怀疑握手或 subprotocol。
   - 如果 client 有消息但 upstream 没消息，查 Basic Auth、target URL、ttyd 状态。
   - 如果 upstream 有消息但 browser 没显示，查 binary/text frame 转发和前端 xterm 渲染。

5. **确认 close code**
   - `1006` 是异常关闭，浏览器不会收到正常 close frame。
   - `1008` 可用于 policy violation，例如 session 不存在或未运行。
   - `1011` 可用于 proxy 内部错误。

## 日志实践

连接、断开、失败建议用 `INFO` 或 `ERROR`：

```text
Terminal websocket proxy connected session_id=... target=... subprotocol=tty
Terminal websocket client disconnected session_id=... code=... client_messages=... upstream_messages=...
Terminal websocket upstream closed session_id=... code=... reason=...
Terminal websocket proxy failed session_id=...
```

逐帧日志建议使用 `DEBUG`，不要长期放在 `INFO`：

```text
Terminal websocket client bytes session_id=... length=... count=...
Terminal websocket upstream bytes session_id=... length=... count=...
```

原因：terminal 输出量可能很大，逐帧 `INFO` 会污染正常日志，也可能影响性能。

## 测试建议

单元测试可以覆盖 HTTP proxy：

- proxy 会添加 Basic Authorization header。
- query string 会保留。
- hop-by-hop response headers 会过滤。
- stopped session 不能返回 proxy target。

WebSocket proxy 最好补充浏览器级或真实 ttyd smoke：

- 用真实 ttyd 启动 Basic Auth。
- 打开 `/terminal/<session_id>/`。
- 确认 WebSocket 请求协商了 `tty` subprotocol。
- 确认浏览器能收到 ttyd binary frames。
- 确认用户输入能从 browser 转发到 ttyd。

仅用 FastAPI `TestClient` 做 synthetic WebSocket smoke 可能不够，因为 ttyd 真实前端、token、subprotocol 和 binary frame 行为都需要一起验证。

## 常见错误

### 1. iframe URL 使用 embedded credentials

不推荐：

```text
http://user:password@127.0.0.1:19001/
```

问题：Chrome 会阻止 iframe/subresource embedded credentials。

推荐：

```text
/terminal/<session_id>/
```

由 FastAPI proxy 注入 Authorization header。

### 2. 只代理 HTTP，不代理 WebSocket

ttyd HTML 能打开不代表 terminal 可用。ttyd terminal 交互依赖 `/ws` WebSocket。

开发环境 Vite proxy 也要启用 WebSocket：

```ts
'/terminal': {
  target: 'http://127.0.0.1:9008',
  ws: true,
}
```

### 3. 误解 `/token` 的作用

`/token` 不是 TermBridge 自己的认证接口，也不是给外部用户使用的 API。它是 ttyd 自带前端为了连接 ttyd WebSocket 而调用的 endpoint。

常见误解：

```text
既然 WebSocket handshake 已经可以带 Authorization: Basic ...，就不需要 /token。
```

实际情况：ttyd WebSocket 连接建立后还会在应用层校验 `AuthToken`。`/token` 返回的就是 ttyd 前端要发送的 `AuthToken`。因此透明复用 ttyd 自带前端时，需要代理 `/token`。

需要避免的是把 `/token` response body 打到普通日志里，因为它本质上包含 `base64(username:password)`。

### 4. 漏掉 `tty` subprotocol

症状：

```text
WebSocket 1006
client_messages=0 upstream_messages=0
```

修复：

```python
await websocket.accept(subprotocol="tty")
websockets.connect(..., subprotocols=["tty"])
```

### 5. 逐帧日志使用 INFO

终端输出高频时会刷爆日志。逐帧日志应使用 `DEBUG`。

### 6. 把 FastAPI proxy 当作公网安全边界

当前方案是本地安全默认值和本地嵌入体验修复：

- ttyd 不直接监听所有网卡。
- ttyd 有 Basic Auth。
- 浏览器不接触 credential。

但这不是完整的多用户授权模型。若要公网部署，还需要 HTTPS/WSS、用户登录、session ownership、CSRF/Origin 策略、反向代理配置、审计和更严格的 secret 管理。

## 检查清单

实现或修改 ttyd proxy 时检查：

- [ ] ttyd 启动命令包含 `--interface 127.0.0.1` 或明确配置的 interface。
- [ ] Basic 模式下 ttyd 启动命令包含 `--credential <username>:<password>`。
- [ ] 空密码生成的 credential 已持久化到 session entry。
- [ ] `SessionResponse.url` 指向 `/terminal/<session_id>/`。
- [ ] `/terminal/<session_id>` 307 到 `/terminal/<session_id>/`。
- [ ] HTTP proxy 向 ttyd 添加 `Authorization: Basic ...`。
- [ ] HTTP proxy 代理 `/terminal/<session_id>/token` 到 ttyd `/token`。
- [ ] 不在普通 `INFO` 日志中记录 `/token` response body，或已对 token 做脱敏。
- [ ] HTTP proxy 保留 query string。
- [ ] HTTP proxy 过滤 hop-by-hop headers。
- [ ] WebSocket proxy 转发 browser query string 到 ttyd `/ws`。
- [ ] WebSocket proxy 从浏览器请求中识别 `Sec-WebSocket-Protocol: tty`。
- [ ] WebSocket proxy 对浏览器 `accept(subprotocol="tty")`。
- [ ] WebSocket proxy 对 upstream `websockets.connect(..., subprotocols=["tty"])`。
- [ ] WebSocket proxy 同时转发 text 和 bytes frame。
- [ ] 任一方向关闭后取消另一方向任务。
- [ ] 连接级日志在 `INFO`，逐帧日志在 `DEBUG`。
- [ ] Vite 或反向代理对 `/terminal` 启用 WebSocket upgrade。
