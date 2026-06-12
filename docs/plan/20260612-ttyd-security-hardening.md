# ttyd WebSocket 安全加固计划

Review status: Accepted

当前：严格模式 / strict，计划 / Plan

## 依据

- 需求：`docs/requirement/20260612-ttyd-security-hardening.md`，Review status: Accepted
- 规格：`docs/spec/20260612-ttyd-security-hardening.md`，Review status: Accepted

初始计划只加固 ttyd 子进程：显式传入 `--interface`，默认开启 ttyd Basic credential，并尝试让前端通过 direct ttyd URL 或 URL userinfo 访问受保护 ttyd。浏览器验证发现 Chrome 会阻止 iframe/subresource embedded credential URL 后，本计划修订为 **FastAPI terminal proxy** 方案。目标是在保留 ttyd Basic Auth 的同时，继续支持嵌入式 terminal workflow，并避免在 iframe URL 中放置 credential。

后续 WebSocket 验证又发现 ttyd 前端会以 `new WebSocket(url, ["tty"])` 方式连接，因此 proxy 必须在浏览器侧和 upstream ttyd 侧都协商 `tty` subprotocol。否则浏览器可能在发送任何 terminal payload 前以 close code `1006` 异常断开。

## 实施步骤

### 1. 扩展配置模型

修改 `src/termbridge/settings.py`：

- 新增：
  - `ttyd_interface: str = "127.0.0.1"`
  - `ttyd_credential_mode: Literal["basic", "none"] = "basic"`
  - `ttyd_credential_username: str = "termbridge"`
  - `ttyd_credential_password: str = ""`
- 复用现有 `SettingsConfigDict(env_prefix="TERMBRIDGE_")`，使环境变量自动映射为：
  - `TERMBRIDGE_TTYD_INTERFACE`
  - `TERMBRIDGE_TTYD_CREDENTIAL_MODE`
  - `TERMBRIDGE_TTYD_CREDENTIAL_USERNAME`
  - `TERMBRIDGE_TTYD_CREDENTIAL_PASSWORD`

### 2. 扩展 session 模型

修改 `src/termbridge/models.py`：

```python
class TtydCredential(BaseModel):
    mode: Literal["basic"] = "basic"
    username: str
    password: str
```

在 `SessionEntryRecord` 增加：

```python
ttyd_credential: TtydCredential | None = None
```

`SessionResponse` 不新增 credential 字段；浏览器只拿到 proxy URL。

### 3. 实现 credential 解析与随机密码生成

修改 `src/termbridge/services.py`：

- 使用 `secrets.token_urlsafe(18)` 生成随机密码。
- 生成结果通过测试保证长度 `>= 12`。
- `basic` + 显式 password：使用配置 password。
- `basic` + 空 password：复用同 username 的已持久化 entry credential，否则生成新 password。
- `none`：不传 credential，并将 entry credential 置为 `None`。
- username 改变时，不复用旧随机 credential。

### 4. 更新 ttyd 启动流程

修改 `SessionService._start_entry()`：

- 启动前解析 credential。
- ttyd 命令加入：

```text
--interface <settings.ttyd_interface>
```

- Basic 模式下加入：

```text
--credential <username>:<password>
```

- entry 更新时写入：

```python
"ttyd_credential": credential,
"url": self._build_url(entry.id),
```

### 5. 改为 terminal proxy URL

`SessionResponse.url` 改为 TermBridge 同源 proxy URL：

```text
/terminal/<session_id>/
```

如果配置 `public_base_url`：

```text
<public_base_url>/terminal/<session_id>/
```

不再生成：

```text
http://user:password@host:port
```

原因：Chrome 会阻止 iframe/subresource embedded credential URL，这条路径已通过浏览器验证判定不可行。

### 6. 暴露内部 proxy target

在 `src/termbridge/services.py` 中新增：

```python
@dataclass(frozen=True)
class TerminalProxyTarget:
    base_url: str
    credential: TtydCredential | None
```

新增：

```python
def terminal_proxy_target(self, session_id: str) -> TerminalProxyTarget:
```

要求：

- session 必须存在。
- session 必须 running 且有 pid。
- 返回内部 ttyd base URL，例如 `http://127.0.0.1:19001`。
- 返回 entry credential，供 API proxy 添加 Authorization header。

### 7. 实现 FastAPI HTTP proxy

修改 `src/termbridge/api.py`：

- 新增 runtime dependency：`httpx`。
- 新增 route：

```text
GET /terminal/<session_id>/<path:path>
```

- `/terminal/<session_id>` 307 redirect 到 `/terminal/<session_id>/`。
- 代理逻辑：
  - 从 `SessionService.terminal_proxy_target()` 获取 target。
  - 将请求转发到 `<target.base_url>/<path>`。
  - 保留 query string。
  - 如果 target credential 存在，添加：

```text
Authorization: Basic <base64(username:password)>
```

  - 过滤 hop-by-hop headers：`connection`、`transfer-encoding`、`upgrade`、`content-length`、`content-encoding` 等。

### 8. 实现 FastAPI WebSocket proxy

修改 `src/termbridge/api.py`：

- 新增 runtime dependency：`websockets`。
- 新增 route：

```text
/terminal/<session_id>/ws
```

- 将 target URL 转换为：

```text
ws://<ttyd-host>:<port>/ws
```

- 保留 browser WebSocket query string。
- 从浏览器请求头 `Sec-WebSocket-Protocol` 解析 subprotocol 列表。
- 如果包含 `tty`：
  - 对浏览器执行 `await websocket.accept(subprotocol="tty")`。
  - 对 upstream ttyd 执行 `websockets.connect(..., subprotocols=["tty"])`。
- 使用：

```python
websockets.connect(
    target_url,
    additional_headers=...,
    origin=target.base_url,
    subprotocols=["tty"],
    proxy=None,
)
```

- 双向转发 browser ↔ ttyd 的 text/bytes frame。
- 任一方向结束时取消另一方向。
- session 不存在或不 running 时关闭 WebSocket。
- 逐帧调试日志使用 `DEBUG`，连接、断开、失败日志使用 `INFO` / `ERROR`。

### 9. 更新 Vite dev proxy

修改 `web/vite.config.ts`：

```ts
'/terminal': {
  target: 'http://127.0.0.1:9008',
  ws: true,
}
```

这样开发环境下 `/terminal/<session_id>/` 和 `/terminal/<session_id>/ws` 都能转发到 FastAPI 后端。

### 10. 更新测试

修改 `tests/test_services.py`：

- 默认 session URL 是 `/terminal/<session_id>/`。
- `public_base_url` 下 URL 是 `<public_base_url>/terminal/<session_id>/`。
- 默认 credential 生成并持久化。
- `none` 模式不传 `--credential`。
- 显式 credential 生效。
- restart 复用随机 credential。
- username 改变时替换 credential。
- 自定义 `ttyd_interface` 影响命令和 proxy target。
- stopped session 拒绝 proxy target。

修改 `tests/test_api.py`：

- 使用 `httpx.MockTransport` 测试 HTTP proxy 会向 ttyd target 添加 Basic Authorization header。
- 测试 hop-by-hop headers 被过滤。
- 测试 query string 被保留。

WebSocket proxy 需要浏览器级或真实 ttyd smoke 验证补足：

- 确认 iframe `/terminal/<session_id>/` 能加载 ttyd HTML。
- 确认 `/terminal/<session_id>/token` 通过 FastAPI proxy 返回 200。
- 确认 `/terminal/<session_id>/ws` 协商 `tty` subprotocol。
- 确认 browser binary frames 能到达 FastAPI，upstream ttyd binary frames 能返回 browser。

### 11. 更新文档

- `.env.sample`：新增配置说明。
- `README.md` / `README.zh-CN.md`：说明 ttyd 本地绑定和 Basic Auth 是本地加固，不是公网部署安全边界。
- `docs/requirement`：修正早期“暂不做 WebSocket proxy”的已废弃假设，记录浏览器验证导致的需求 pivot。
- `docs/spec`：记录 FastAPI HTTP/WebSocket proxy、Authorization header 和 `tty` subprotocol。
- `docs/plan`：记录 pivot 后新增的实现步骤、依赖和验证方式。
- `docs/verification`：记录失败尝试、浏览器现象、最终通过条件和剩余风险。
- `docs/guides`：沉淀可复用的 FastAPI proxy、ttyd Basic Auth 和 WebSocket subprotocol 实践。

## 预计修改文件

- `src/termbridge/settings.py`
- `src/termbridge/models.py`
- `src/termbridge/services.py`
- `src/termbridge/api.py`
- `web/vite.config.ts`
- `.env.sample`
- `pyproject.toml`
- `uv.lock`
- `tests/test_services.py`
- `tests/test_api.py`
- `tests/test_settings.py`
- `README.md`
- `README.zh-CN.md`
- `docs/requirement/20260612-ttyd-security-hardening.md`
- `docs/spec/20260612-ttyd-security-hardening.md`
- `docs/plan/20260612-ttyd-security-hardening.md`
- `docs/verification/20260612-ttyd-security-hardening.md`
- `docs/guides/fastapi-ttyd-websocket-proxy.md`

不修改：

- 前端 terminal iframe 组件结构；它继续使用 `item.url`。

## 验证计划

### 后端目标测试

```powershell
uv run pytest tests/test_api.py tests/test_services.py tests/test_settings.py
```

### 后端 lint

```powershell
uv run ruff check .
```

### 前端类型检查

```powershell
yarn --cwd web typecheck
```

### 全量测试

```powershell
uv run pytest
```

已知当前全量 suite 可能仍因无关 `tests/test_logging.py::test_request_logging_uses_error_for_unhandled_exception` 失败。

### 本地 proxy smoke

- 启动本地 `ttyd --interface 127.0.0.1 --credential ...`。
- 请求 `/terminal/<session_id>/` 和 `/terminal/<session_id>/token`。
- 确认 HTTP proxy 返回 ttyd HTML/token，并向 ttyd 添加 Basic Authorization。
- 实际浏览器验证：前端 iframe 加载 `/terminal/<session_id>/` 时不再触发 Chrome embedded credential blocking。
- 实际浏览器验证：WebSocket `/terminal/<session_id>/ws` 协商 `tty` subprotocol，不再出现缺少消息的 1006 异常断开。

## 回滚计划

- 回滚 terminal proxy routes、`TerminalProxyTarget` 和 proxy URL 构造。
- 移除 `httpx` / `websockets` runtime dependencies。
- 恢复 session URL 旧行为或关闭 Basic credential。
- 删除 Vite `/terminal` proxy。

注意：回滚到 URL userinfo 不是推荐方案，因为已通过浏览器验证确认它会被 Chrome iframe/subresource 策略阻止。

## 假设

- ttyd 的 HTML 使用当前路径推导 `/ws` 和 `/token`，代理路径 `/terminal/<session_id>/` 能满足该行为。
- `websockets` runtime dependency 可接受。
- 当前目标是本地开发工作台，FastAPI proxy 性能足够支撑少量本地 terminal sessions。
- ttyd 前端要求 `tty` WebSocket subprotocol，proxy 两端都必须协商。

## 风险

- WebSocket proxy 是新链路，高频输出、取消行为和 close-code 传播仍可能需要后续调优。
- FastAPI proxy 会增加转发层和少量延迟。
- 大量输出或大量并发 terminal session 下可能需要 backpressure、streaming 和连接管理优化。
- 当前 HTTP proxy 使用非 streaming response；对 ttyd HTML/token/static resources 足够，但不是通用大文件 proxy。

## 阻塞项

暂无阻塞项。

## 用户评审记录

- 初始需求只准备添加 ttyd Basic 认证和本地 interface 绑定，不准备实现 WebSocket proxy。
- Chrome 实际报错：subresource requests with embedded credentials are blocked。
- 用户要求开始尝试 FastAPI proxy。
- 后续 WebSocket 1006 排查确认缺少 `tty` subprotocol；计划补充两端 subprotocol 转发。
