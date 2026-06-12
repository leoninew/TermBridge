# ttyd WebSocket 安全加固验证

Review status: Accepted

当前：严格模式 / strict，验证 / Verification

## 需求对齐

- 已新增 `TERMBRIDGE_TTYD_INTERFACE`，默认 `127.0.0.1`。
- 已新增 `TERMBRIDGE_TTYD_CREDENTIAL_MODE`，默认 `basic`，支持 `none` 覆盖。
- 已新增 `TERMBRIDGE_TTYD_CREDENTIAL_USERNAME`，默认 `termbridge`。
- 已新增 `TERMBRIDGE_TTYD_CREDENTIAL_PASSWORD`，默认空字符串。
- 当密码为空时，使用 `secrets.token_urlsafe(18)` 生成随机密码，并通过测试断言长度不少于 12 位。
- 随机生成的 credential 保存到 session entry 的 `ttyd_credential` 字段，并随 `.termbridge/sessions.json` 持久化。
- ttyd 启动命令添加 `--interface <configured-interface>`。
- Basic 模式下 ttyd 启动命令添加 `--credential <username>:<password>`。
- `none` 模式下不添加 `--credential`，且不保存 credential。
- Chrome 阻止 iframe/subresource embedded credential URL 后，访问层改为 FastAPI HTTP/WebSocket proxy，不再把 credential 放进 iframe URL。
- 前端 iframe 仍通过 `SessionResponse.url` 访问；该 URL 指向 `/terminal/<session_id>/`。
- FastAPI HTTP proxy 向 ttyd upstream 添加 `Authorization: Basic ...`。
- FastAPI WebSocket proxy 向 ttyd upstream 添加 `Authorization: Basic ...`，并转发 ttyd 前端要求的 `tty` subprotocol。

## 规格对齐

- 配置层：`Settings` 增加 interface 与 credential 配置。
- 模型层：`SessionEntryRecord` 增加 `ttyd_credential`，并新增 `TtydCredential` 模型。
- 命令构造层：`_build_ttyd_command()` 增加 `--interface` 和可选 `--credential`。
- 访问层：`_build_url()` 返回 TermBridge terminal proxy URL，而不是 ttyd direct URL 或 URL userinfo。
- 代理层：FastAPI 新增 `/terminal/<session_id>/<path:path>` HTTP proxy 和 `/terminal/<session_id>/ws` WebSocket proxy。
- 后端代理向 ttyd target 添加 `Authorization: Basic ...`，因此浏览器无需在 iframe URL 中携带 credential。
- WebSocket proxy 在浏览器侧和 upstream ttyd 侧都协商 `tty` subprotocol。
- Vite dev server 已配置 `/terminal` proxy 并启用 WebSocket。

## 计划对齐

计划中的核心文件均已修改：

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

过程文档已更新以反映 URL userinfo 被 Chrome 阻止后的 FastAPI proxy 方案，并补充 WebSocket `tty` subprotocol 的验证结论。

实际 diff 中还包含两个前端组件变更：`AppShell.vue` 的 `RouterView` / `Transition` 嵌套调整，以及 `SessionTerminal.vue` 移除 iframe `sandbox` 属性。这两项不在原计划的“前端 iframe 组件结构不修改”范围内，验证结论中作为扩展/偏离范围单独记录，提交前建议确认是否保留在同一提交。

## 实际变更摘要

- `.env.sample`：新增 ttyd interface 与 Basic credential 配置示例。
- `README.md` / `README.zh-CN.md`：更新安全提示，说明 ttyd 本地绑定与 Basic Auth 是本地加固，不是公网部署安全边界。
- `pyproject.toml` / `uv.lock`：新增 runtime dependencies `httpx` 和 `websockets`。
- `web/vite.config.ts`：新增 `/terminal` dev proxy，启用 WebSocket。
- `src/termbridge/settings.py`：新增 `ttyd_interface`、`ttyd_credential_mode`、`ttyd_credential_username`、`ttyd_credential_password`。
- `src/termbridge/models.py`：新增 `TtydCredential`；`SessionEntryRecord` 新增 `ttyd_credential`。
- `src/termbridge/services.py`：实现 credential 解析、随机密码生成、ttyd 命令加固、terminal proxy URL 与 proxy target。
- `src/termbridge/api.py`：实现 ttyd HTTP/WebSocket proxy，并向 ttyd 注入 Basic Authorization header；WebSocket proxy 转发 `tty` subprotocol；逐帧日志使用 `DEBUG`。
- `tests/test_services.py`：覆盖默认 Basic credential、`none` 模式、显式 credential、随机 credential 复用、username 改变后替换、自定义 interface、proxy URL 和 proxy target。
- `tests/test_api.py`：覆盖 HTTP proxy Authorization header、query string 与 hop-by-hop header 过滤。
- `tests/test_settings.py`：覆盖新增配置默认值。
- `docs/guides/fastapi-ttyd-websocket-proxy.md`：沉淀 FastAPI proxy、ttyd Basic Auth 和 WebSocket subprotocol 实践。

## 计划与实际文件对照

| 文件 | 计划 | 实际 | 说明 |
| --- | --- | --- | --- |
| `src/termbridge/settings.py` | 是 | 是 | 新增配置。 |
| `src/termbridge/models.py` | 是 | 是 | 新增 credential 模型与字段。 |
| `src/termbridge/services.py` | 是 | 是 | 命令构造、credential、proxy URL/target。 |
| `src/termbridge/api.py` | 是 | 是 | HTTP/WebSocket proxy、Basic Authorization、`tty` subprotocol。 |
| `web/vite.config.ts` | 是 | 是 | `/terminal` dev proxy。 |
| `.env.sample` | 是 | 是 | 新增配置说明。 |
| `pyproject.toml` / `uv.lock` | 是 | 是 | 新增 runtime dependencies。 |
| `tests/test_services.py` | 是 | 是 | 增加服务行为测试。 |
| `tests/test_api.py` | 是 | 是 | 增加 HTTP proxy 测试。 |
| `tests/test_settings.py` | 是 | 是 | 增加默认配置测试。 |
| `README.md` / `README.zh-CN.md` | 可能 | 是 | 同步安全边界说明。 |
| `docs/guides/fastapi-ttyd-websocket-proxy.md` | 后续新增 | 是 | 沉淀实践经验。 |
| `web/src/components/AppShell.vue` | 否 | 是 | 调整 `RouterView` / `Transition` 嵌套，属于本次 diff 的额外前端结构变更。 |
| `web/src/components/SessionTerminal.vue` | 否 | 是 | 移除 iframe `sandbox` 属性，属于本次 diff 的额外 iframe 行为变更。 |

## 验收标准检查清单

- [x] `TERMBRIDGE_TTYD_INTERFACE` 默认 `127.0.0.1`。
- [x] `TERMBRIDGE_TTYD_CREDENTIAL_MODE` 默认 `basic`，支持 `none`。
- [x] `TERMBRIDGE_TTYD_CREDENTIAL_USERNAME` 默认 `termbridge`。
- [x] `TERMBRIDGE_TTYD_CREDENTIAL_PASSWORD` 默认空字符串。
- [x] ttyd 命令包含 `--interface <configured-interface>`。
- [x] Basic 模式下 ttyd 命令包含 `--credential <username>:<password>`。
- [x] `none` 模式下 ttyd 命令不包含 `--credential`。
- [x] 空密码时生成不少于 12 位的随机密码。
- [x] 随机密码持久化到 session entry。
- [x] 停止后重新启动同一 session 时复用已持久化随机密码。
- [x] username 改变时替换已持久化随机 credential。
- [x] session URL 不包含 embedded credential。
- [x] session URL 指向 `/terminal/<session_id>/` proxy。
- [x] FastAPI HTTP proxy 向 ttyd 添加 Basic Authorization header。
- [x] FastAPI WebSocket proxy 向 ttyd 添加 Basic Authorization header。
- [x] FastAPI WebSocket proxy 转发 `tty` subprotocol。
- [x] Vite dev server 支持 `/terminal` HTTP/WebSocket proxy。
- [x] `.env.sample` 记录新增配置。

## 测试结果

### 已通过

```powershell
uv run pytest tests/test_api.py tests/test_services.py tests/test_settings.py
```

结果：`40 passed, 1 warning`。

```powershell
uv run ruff check .
```

结果：`All checks passed!`。

```powershell
yarn --cwd web typecheck
```

结果：`Done`。

### 全量测试

```powershell
uv run pytest
```

结果：`111 passed, 1 warning`。

此前失败的 `tests/test_logging.py::test_request_logging_uses_error_for_unhandled_exception` 已修正。修正依据是 `docs/requirement/20260611-global-error-ui-state.md`：未捕获异常应统一转换为 `{ "code": "internal_error", "error": "Internal server error" }`，同时后端日志保留 traceback。因此测试不应继续期望 `RuntimeError("broken")` 冒泡，而应断言 500 结构化响应与 `Request failed` / `Request end status=500` 日志。

### 本地 ttyd 行为验证

本地 ttyd 版本此前已确认：

```text
ttyd version 1.7.7-40e79c7
```

本地 listener 检查确认 `--interface 127.0.0.1` 会让 ttyd 绑定到 `127.0.0.1`。

使用本地 ttyd 进程和 `httpx` 做 Basic Auth 检查：

```text
{'no_auth': 401, 'authorization_header': 200, 'url_userinfo': 200}
```

该结果说明 ttyd 接受标准 `Authorization: Basic ...` 请求头，URL userinfo 对普通 HTTP 客户端也可用。但 Chrome 浏览器检查随后显示 iframe/subresource requests with embedded credentials are blocked，因此访问层改为 FastAPI proxy。

FastAPI HTTP proxy 对真实本地 ttyd 的 smoke：

```text
{'root': 200, 'root_has_ws': True, 'token': 200, 'token_body': '{"token": "..."}'}
```

这确认 FastAPI HTTP proxy 可以在添加 Basic Authorization 的情况下获取 ttyd HTML 和 token endpoint。

浏览器级 WebSocket proxy 验证已通过。关键修复是转发 ttyd 必需的 `tty` WebSocket subprotocol：

- 浏览器请求头包含 `Sec-WebSocket-Protocol: tty`。
- FastAPI 对浏览器 `accept(subprotocol="tty")`。
- FastAPI 对 upstream ttyd `websockets.connect(..., subprotocols=["tty"])`。
- 日志显示 `subprotocol=tty`。
- client binary frames 到达 FastAPI。
- upstream ttyd binary frames 返回 browser。

### 已排除或修正的失败路径

- **URL userinfo 方案失败**：`http://user:pass@host/` 在普通 HTTP 客户端可用，但 Chrome 阻止 iframe/subresource embedded credentials，因此不能作为嵌入式 terminal 方案。
- **只加 Basic Auth 不加 proxy 不足够**：浏览器 iframe 无法可靠携带 credential 访问 ttyd，且 ttyd 默认只绑定本地后也需要同源访问入口。
- **WebSocket 1006**：在缺少 `tty` subprotocol 转发时，浏览器可能在发送任何 message 前断开，表现为 `client_messages=0 upstream_messages=0` 和 close code `1006`。补充两端 subprotocol 协商后通过浏览器验证。
- **Synthetic TestClient WebSocket smoke 不充分**：TestClient 级验证无法完整覆盖真实 ttyd 前端、`/token`、subprotocol 和 binary frame 行为，因此最终以浏览器级验证为准。

## Review 结果

Subagent review passes 在 proxy pivot 前运行过：

- Security reviewer：无发现。
- Correctness reviewer：发现 direct session URL 应使用 `ttyd_interface` 而不是 API `host`；后续 direct URL 被 proxy URL 替代。
- Testing reviewer：要求补充 invalid public URL cleanup 和 username-change credential replacement 测试；proxy pivot 后保留 username-change 覆盖，public URL 行为由 proxy URL construction 覆盖。

## 偏离或扩展范围

- 扩展范围：Chrome 阻止 embedded credential iframe URL 后，新增 FastAPI HTTP/WebSocket proxy。
- 扩展范围：`httpx` 和 `websockets` 成为 runtime dependencies。
- 扩展范围：WebSocket proxy 需要转发 ttyd 前端要求的 `tty` subprotocol。
- 扩展范围：新增 `docs/guides/fastapi-ttyd-websocket-proxy.md`，记录本次排查和实践。
- 偏离原计划：`web/src/components/AppShell.vue` 调整了 `RouterView` / `Transition` 嵌套。
- 偏离原计划：`web/src/components/SessionTerminal.vue` 移除了 iframe `sandbox` 属性。
- Vite dev proxy 已更新。

## 剩余风险

- WebSocket proxy 路径在高频 terminal 输出、取消行为和 close-code 传播方面可能仍需调优。
- FastAPI proxy 是本地加固和嵌入体验兼容层，不是托管式多用户授权边界。
- `AppShell.vue` 和 `SessionTerminal.vue` 存在原计划外前端结构/iframe 行为变更；提交前建议确认它们是否应与 ttyd security hardening 放在同一提交。
- 全量测试已通过；当前没有已知测试失败。

## 未完成项

- 原计划外的 `AppShell.vue` 和 `SessionTerminal.vue` 变更需要在提交前确认归属；如果不属于 ttyd security hardening，建议拆分或回退。

## 结论

ttyd security hardening 现在通过本地 ttyd interface binding、默认 Basic credential、随机 credential 持久化，以及 FastAPI terminal HTTP/WebSocket proxy 避免 Chrome embedded credential URL blocking。目标后端测试、后端 lint、前端 typecheck 和浏览器级 WebSocket proxy 验证均已通过。全量验证仍被一个无关的既有 logging 测试失败阻塞。
