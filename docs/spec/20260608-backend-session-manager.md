# 后端 ttyd 会话管理规格 / Backend ttyd Session Manager Spec

Review status: Accepted

## Requirement basis

基于 `docs/requirement/20260608-backend-session-manager.md`，本阶段设计一个 Python + uv + FastAPI 后端，用于管理 ttyd 会话生命周期。Requirement 已接受，范围限定为后端 MVP，不包含前端、认证、HTTPS/反向代理、持久化数据库和 WebSocket 终端转发。

## Overview

后端提供一个 FastAPI 应用，包含：

- HTTP API：健康检查、创建会话、列出会话、查询会话、停止/删除会话。
- Session service：封装会话生命周期和业务规则。
- Process adapter：封装 ttyd 进程启动、停止、状态检查，便于单元测试替换。
- Port allocator：为 ttyd 会话分配本地端口，避免与已注册会话冲突。
- Runtime registry：定义允许启动的 runtime 与对应命令。
- File session repository：MVP 阶段使用文件保存会话元数据，支持增删改查，不引入数据库存储和 ORM。

## Design decisions

### 工程布局

采用根目录 Python 后端工程，避免在 README 之外引入额外顶层应用目录复杂度：

```text
pyproject.toml
src/cc_ttyd/
  __init__.py
  main.py
  api.py
  di.py
  models.py
  settings.py
  ports.py
  runtime.py
  process.py
  repositories.py
  services.py
tests/
  test_*.py
```

### 分层与依赖注入

FastAPI 后端必须保持基本分层，避免把业务逻辑写在 route handler 中：

- `api.py`：只负责 HTTP request/response、依赖声明、异常到 HTTP 状态码的转换。
- `services.py`：封装会话生命周期业务规则。
- `repositories.py`：封装基于文件的会话注册表读写，MVP 不引入数据库或 ORM。
- `process.py`：封装 ttyd 进程启动、停止、状态检查。
- `ports.py`：封装端口分配。
- `runtime.py`：封装 runtime registry 和命令解析。
- `settings.py`：封装配置。
- `di.py`：定义当前业务包的 FastAPI dependency provider。

业务性质代码不按可复用类库设计；在业务包目录内定义该包自己的 `di.py`，管理该包需要暴露给上一层或 FastAPI 的 dependency provider。项目可以存在多个不同目录的 `di.py`，依赖按包/模块边界逐层组合，而不是放进一个全局集中式依赖容器。API、service 或 repository 内部不自行实例化下游组件，不使用 `SessionService(...)`、`TtydProcessAdapter(...)` 等方式临时 new 依赖。所有组件通过 FastAPI dependency injection 获取，测试通过覆盖 dependency provider 或注入 fake 实现完成。

### API 边界

采用 `/api` 前缀：

- `GET /health`：健康检查。
- `POST /api/sessions`：创建会话。
- `GET /api/sessions`：列出会话。
- `GET /api/sessions/{session_id}`：查询单个会话。
- `DELETE /api/sessions/{session_id}`：停止并删除会话。

### 会话模型

内部会话记录包含：

```text
id
name
workspace
runtime
command
port
status
pid
created_at
updated_at
url
```

状态建议：

```text
starting
running
stopped
failed
```

MVP API 返回 Pydantic response model，不直接暴露 Python 进程对象。

### Runtime registry

初始支持：

- `claude-code` → `claude`
- `codex` → `codex`
- `powershell` → `pwsh`
- `bash` → `bash`

说明：README MVP 明确包含 Claude Code、Codex、PowerShell；Bash 在总体 Runtime 中出现，且对测试和本地兼容有价值，因此纳入默认支持。

### ttyd 命令构造

默认假定 `ttyd` 在 PATH 中，同时通过 settings 支持覆盖可执行文件路径。

命令形态：

```text
ttyd --port <port> --cwd <workspace> <runtime-command>
```

如果 ttyd `1.7.7-40e79c7` 的实际参数名与此不一致，Implementation 阶段以本地 `ttyd --help` 为准，并回写文档风险或调整。

### 端口分配

使用可配置端口范围，例如：

```text
9001-9999
```

分配策略：

1. 遍历端口范围。
2. 跳过当前 repository 中已注册会话端口。
3. 尝试绑定本地 socket 验证端口可用。
4. 返回第一个可用端口。

### 进程管理

Process adapter 提供：

- `start(command: list[str], cwd: Path) -> ProcessHandle`
- `terminate(handle: ProcessHandle) -> None`
- `is_running(handle: ProcessHandle) -> bool`

实现层使用 `subprocess.Popen`。测试中使用 fake adapter，避免真实启动 ttyd。

### 文件会话管理

当前不引入数据库、ORM 或外部存储服务。会话元数据使用本地文件管理，repository 负责提供 CRUD 能力：

- `create(session)`：新增会话记录。
- `list()`：列出全部会话记录。
- `get(session_id)`：读取单个会话记录。
- `update(session)`：更新状态、pid、端口、更新时间等字段。
- `delete(session_id)`：删除会话记录。

文件格式采用 JSON，优先使用单一 registry 文件，例如 `.cc-ttyd/sessions.json`。写入时应使用临时文件 + 原子替换，避免进程异常导致文件半写入。repository 只负责元数据持久化，不直接管理 ttyd 进程；进程生命周期仍由 service 协调 process adapter 完成。

服务启动时可以从文件加载既有会话记录；由于进程句柄无法跨服务重启恢复，list/detail 时需要通过 pid 或端口懒检查状态，并将无法确认仍运行的会话标记为 `stopped` 或 `failed`。

### 配置

基于 `pydantic-settings` + `python-dotenv` 管理配置。配置从环境变量和 `.env` 文件读取，`settings.py` 定义 `BaseSettings` 模型，`di.py` 提供 settings dependency provider。配置项包括：

- `ttyd_executable`
- `host`
- `port_start`
- `port_end`
- `sessions_file` 或 `state_dir`
- `public_base_url` 可选

MVP 使用显式配置模型，避免在业务代码中直接读取环境变量。

### 错误处理

- 未知 runtime：返回 400。
- workspace 不存在或不是目录：返回 400。
- 无可用端口：返回 503。
- session 不存在：返回 404。
- 启动 ttyd 失败：返回 500 或创建失败响应，不注册 running 会话。

## Affected components

- 新增 Python 工程配置：`pyproject.toml`。
- 新增后端应用代码：`src/cc_ttyd/`，按 API、DI、service、repository、process adapter、port allocator、runtime registry、settings 分层。
- 新增单元测试：`tests/`。
- 新增过程文档：`docs/spec/20260608-backend-session-manager.md`。

## Interfaces

### Create session request

```json
{
  "name": "Preflight",
  "workspace": "D:/projects/preflight",
  "runtime": "claude-code"
}
```

### Session response

```json
{
  "id": "sess_...",
  "name": "Preflight",
  "workspace": "D:/projects/preflight",
  "runtime": "claude-code",
  "status": "running",
  "port": 9001,
  "url": "http://127.0.0.1:9001",
  "created_at": "2026-06-08T00:00:00Z",
  "updated_at": "2026-06-08T00:00:00Z"
}
```

### Delete session response

可返回 `204 No Content`。若需要调试信息，未来再扩展，不在 MVP 中增加复杂响应。

## Technical questions

- `ttyd --cwd` 是否为当前版本支持的参数，需要 Implementation 阶段用本地 `ttyd --help` 验证。
- Windows 环境下 PowerShell 命令应优先使用 `pwsh` 还是 `powershell.exe`，MVP 先用 `pwsh`，必要时通过配置调整。
- 是否需要 session 状态后台刷新；MVP 可在 list/detail 时懒检查进程是否仍在运行。

## Risks

- ttyd 参数与预期不一致会影响启动命令，需要在实现前验证。
- Windows 下 `subprocess.Popen`、进程终止和 shell runtime 的行为可能与 Unix 不同，需要通过 adapter 隔离并测试核心逻辑。
- 文件会话注册表需要处理半写入、损坏 JSON、并发写入等风险；MVP 至少保证单进程内原子写入。
- 真实 ttyd 进程集成测试可能依赖本机环境，不应作为单元测试硬依赖。

## Alternatives

### 直接由 FastAPI WebSocket 代理 PTY

不采用。README 明确选择 ttyd，项目不重复造轮子。

### 使用数据库持久化会话

不采用。当前要求不引入数据库存储和 ORM；MVP 使用基于文件的会话管理。

### 为每种 runtime 写独立启动器

暂不采用。MVP 使用 runtime registry 映射命令即可，后续再扩展 runtime-specific adapter。

## User review notes

- 待用户 review。若确认规格或要求进入计划阶段，将本规格状态更新为 `Accepted`。
- 用户补充：当前不引入数据库存储和 ORM，但需要合理设计基于文件的会话管理能力，支持增删改查。
- 用户补充并修正：FastAPI 必须有基本分层，基于依赖注入管理组件；不接受在业务代码里自行实例化组件；业务性质非类库包内定义 `di.py` 管理本包依赖。项目可以存在多个不同目录的 `di.py`，依赖按包/模块边界逐层组合，不是全局集中式依赖容器。
- 用户补充：基于 `pydantic-settings` + `python-dotenv` 管理配置。
