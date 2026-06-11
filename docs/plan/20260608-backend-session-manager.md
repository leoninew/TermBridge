# 后端 ttyd 会话管理计划 / Backend ttyd Session Manager Plan

Review status: Accepted

## Requirement / Spec basis

- Requirement: `docs/requirement/20260608-backend-session-manager.md`，状态 `Accepted`。
- Spec: `docs/spec/20260608-backend-session-manager.md`，状态 `Accepted`。

实施目标是在仓库根目录创建 Python + uv + FastAPI 后端工程，实现基于文件的 ttyd 会话管理。范围限定为后端 MVP，不实现前端、认证、HTTPS/反向代理、数据库/ORM、FastAPI WebSocket 终端转发。

## Implementation steps

### 1. 探查现有仓库与工具链

- 检查当前仓库是否已有 `pyproject.toml`、Python 后端目录、测试配置或 lint 配置。
- 检查 `ttyd --help`，确认当前 ttyd 版本的端口、工作目录参数。
- 确认 `uv` 可用性；若不可用，记录为 blocker。

### 2. 创建 Python uv 工程配置

- 在根目录创建或更新 `pyproject.toml`。
- 配置运行依赖：
  - `fastapi`
  - `uvicorn`
  - `pydantic-settings`
  - `python-dotenv`
- 配置开发依赖：
  - `pytest`
  - `ruff`
  - `mypy`
  - `httpx` 或 FastAPI TestClient 所需依赖
- 配置 ruff、mypy、pytest 基础规则。

### 3. 实现应用入口与 API 层

- 创建 `src/cc_ttyd/main.py`：构建 FastAPI app，注册 router。
- 创建 `src/cc_ttyd/api.py`：
  - `GET /health`
  - `POST /api/sessions`
  - `GET /api/sessions`
  - `GET /api/sessions/{session_id}`
  - `DELETE /api/sessions/{session_id}`
- route handler 只处理 HTTP 边界、依赖声明和异常转换，不直接写业务流程。

### 4. 实现 Pydantic 模型

- 创建 `src/cc_ttyd/models.py`。
- 定义 request/response model、内部 session model、session status enum。
- 确保 API 不暴露进程对象，只暴露可序列化元数据。

### 5. 实现配置管理

- 创建 `src/cc_ttyd/settings.py`。
- 使用 `pydantic-settings` + `python-dotenv`。
- 配置项包括：
  - `ttyd_executable`
  - `host`
  - `port_start`
  - `port_end`
  - `state_dir` 或 `sessions_file`
  - `public_base_url`
- 业务代码不得直接读取环境变量。

### 6. 实现分层 DI

- 创建 `src/cc_ttyd/di.py`。
- 在业务包内定义 dependency provider，例如：
  - `get_settings`
  - `get_session_repository`
  - `get_runtime_registry`
  - `get_port_allocator`
  - `get_process_adapter`
  - `get_session_service`
- 依赖按当前业务包边界组织。该 `di.py` 不是全局集中式容器；未来若出现其他业务包，可在各自目录继续定义各自 `di.py` 并逐层组合。
- API/service/repository 内不自行实例化下游组件。

### 7. 实现 runtime registry

- 创建 `src/cc_ttyd/runtime.py`。
- 支持 runtime：
  - `claude-code` → `claude`
  - `codex` → `codex`
  - `powershell` → `pwsh`
  - `bash` → `bash`
- 未知 runtime 抛出业务异常，由 API 层转换为 400。

### 8. 实现端口分配

- 创建 `src/cc_ttyd/ports.py`。
- 遍历配置端口范围。
- 跳过文件会话注册表中已使用端口。
- 使用 socket bind 检查端口是否实际可用。
- 无端口时抛出业务异常，由 API 层转换为 503。

### 9. 实现基于文件的会话 repository

- 创建 `src/cc_ttyd/repositories.py`。
- 使用 JSON 文件保存 session registry，例如 `.termbridge/sessions.json`。
- 实现 CRUD：
  - create
  - list
  - get
  - update
  - delete
- 写入使用临时文件 + 原子替换。
- repository 只负责元数据读写，不管理 ttyd 进程。
- 处理文件不存在的初始状态。
- 对损坏 JSON 给出明确异常；MVP 不做自动修复。

### 10. 实现 ttyd process adapter

- 创建 `src/cc_ttyd/process.py`。
- 封装：
  - start command
  - terminate process
  - check running
- 使用 `subprocess.Popen`。
- 不在单元测试中真实启动 ttyd；测试通过 fake adapter。
- Windows 下终止行为先使用可测试的基础实现，复杂进程树清理由后续增强处理。

### 11. 实现 session service

- 创建 `src/cc_ttyd/services.py`。
- 协调 repository、runtime registry、port allocator、process adapter。
- 创建会话流程：
  1. 校验 workspace 存在且是目录。
  2. 解析 runtime command。
  3. 分配端口。
  4. 构造 ttyd command。
  5. 启动进程。
  6. 写入文件 registry。
  7. 返回 session response。
- 查询/list 时懒检查运行状态并必要时更新 registry。
- 删除会话流程：读取记录、停止进程、删除 registry。

### 12. 编写单元测试

- 测试 API：健康检查、创建/列表/详情/删除 happy path、常见错误码。
- 测试 repository：文件不存在、CRUD、原子写入结果、损坏 JSON 异常。
- 测试 port allocator：跳过已注册端口、跳过被占用端口、无可用端口。
- 测试 runtime registry：已知 runtime、未知 runtime。
- 测试 session service：创建命令构造、停止流程、workspace 校验、fake process adapter。
- 测试 DI：API 可以通过 dependency override 注入 fake service/repository。

### 13. 运行质量检查与测试

- `uv run ruff format .`
- `uv run ruff check .`
- `uv run mypy src tests`
- `uv run pytest`

## Files to change

预计新增：

- `pyproject.toml`
- `src/cc_ttyd/__init__.py`
- `src/cc_ttyd/main.py`
- `src/cc_ttyd/api.py`
- `src/cc_ttyd/di.py`
- `src/cc_ttyd/models.py`
- `src/cc_ttyd/settings.py`
- `src/cc_ttyd/runtime.py`
- `src/cc_ttyd/ports.py`
- `src/cc_ttyd/process.py`
- `src/cc_ttyd/repositories.py`
- `src/cc_ttyd/services.py`
- `tests/test_api.py`
- `tests/test_repositories.py`
- `tests/test_ports.py`
- `tests/test_runtime.py`
- `tests/test_services.py`
- `docs/verification/20260608-backend-session-manager.md`（验证阶段创建）

预计更新：

- `docs/plan/20260608-backend-session-manager.md`
- 如实现发现 ttyd 参数不同，更新 `docs/spec/20260608-backend-session-manager.md` 或在 verification 中记录偏差。

## Verification plan

- 使用 `ttyd --help` 验证命令参数。
- 使用 `uv run ruff format .` 保证格式化。
- 使用 `uv run ruff check .` 做 lint。
- 使用 `uv run mypy src tests` 做类型检查。
- 使用 `uv run pytest` 跑单元测试。
- 验证 API 路由覆盖需求中的创建、列表、详情、停止/删除。
- 对照 diff 确认未实现前端、认证、数据库/ORM、HTTPS/反向代理、WebSocket 代理等非目标。

## Blockers

- 若本机没有 `uv`，无法按用户要求执行完整验证。
- 若 `ttyd --help` 不可用或参数与预期不一致，需要先修正命令构造设计。
- 若 Windows 下 `pwsh` 不存在，runtime registry 仍可保留默认映射，但真实启动 PowerShell 会话可能失败；可通过配置后续调整。

## Assumptions

- 后端工程放在仓库根目录 `src/cc_ttyd/`。
- `ttyd` 默认在 PATH 中，可通过配置覆盖。
- 文件 session registry 默认放在 `.termbridge/sessions.json`。
- 本阶段测试以单元测试为主，不把真实 ttyd 进程作为必需测试依赖。

## Risks

- 文件 registry 并发写入在多 worker 场景下可能需要文件锁；MVP 先保证单进程原子写入。
- 服务重启后无法恢复 Python `Popen` handle，只能通过 pid/端口懒检查状态。
- ttyd 参数在不同平台可能不一致，实现阶段需要以本机版本为准。

## Rollback

- 所有改动为新增后端工程和文档；如需回滚，可移除 `src/cc_ttyd/`、`tests/`、`pyproject.toml` 中新增配置，以及本 feature 文档目录。
- 不修改现有 `README.md` 和已有子项目，降低回滚影响。

## User review notes

- 待用户 review。若确认计划或要求开始实现，将本计划状态更新为 `Accepted` 并进入 Implementation。
