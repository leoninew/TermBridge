# 打包与分发计划

Review status: Accepted

当前：标准模式 / standard，验证阶段 / Verification

## Requirement basis

基于 `docs/requirement/20260610-packaging-distribution.md`：提供 Docker 镜像和 wheel 两种分发形态；前端先构建，后端提供静态页面服务；wheel 包含前端制品；不引入 CLI 子命令，安装后的 `termbridge` 默认启动后端并提供前端页面。

## Implementation steps

### 1. 后端支持静态页面服务

修改 `src/termbridge/api.py`：

1. 保留现有 `router`、API handler 和 `RequestLoggingMiddleware`。
2. 扩展 `create_app()` 参数：
   - `serve_web: bool = True`
   - `web_dir: Path | None = None`
3. 添加静态资源解析逻辑：
   - 如果传入 `web_dir`，优先使用该目录。
   - 否则使用包内资源目录 `termbridge/static`。
   - 只有目录存在且包含 `index.html` 时启用前端服务；否则保持 API-only。
4. 添加最后注册的 catch-all route：
   - `/api/*` 不走 fallback。
   - `/health` 不走 fallback。
   - GET/HEAD 前端路径返回真实静态文件或 `index.html`。
   - 前端 history 路由如 `/environment`、`/shortcuts` 返回 `index.html`。

### 2. 保持单入口 CLI

修改 `src/termbridge/main.py`：

1. 保持 `termbridge = "termbridge.main:main"` 不变。
2. 保留现有参数：`--host`、`--port`、`--reload`。
3. 新增可选参数：
   - `--web-dir PATH`：显式指定构建后的前端目录。
   - `--no-web`：开发或调试时强制 API-only。
4. 默认行为：启用前端服务；如果包内或指定目录没有 `index.html`，后端自动退化为 API-only。
5. 保留 `app = create_app()`，使现有 reload 字符串入口继续可用。
6. 当用户传入 `--web-dir` 或 `--no-web` 时，运行动态创建的 app 对象；否则沿用 `uvicorn.run("termbridge.main:app", ...)`。

### 3. wheel 包含前端制品

修改 `pyproject.toml`：

1. 保留 `[tool.hatch.build.targets.wheel] packages = ["src/termbridge"]`。
2. 确保 `src/termbridge/static/**` 被纳入 wheel。
3. 如 Hatch 默认未包含该目录，添加明确 include/artifact 配置。

本阶段采用显式构建流程，不让 Python build 自动调用 Node/Yarn：

1. `make build` 构建前端并同步到 `src/termbridge/static/`
2. 同一个 `make build` 目标随后运行 `uv build`

### 4. Docker 镜像构建

新增 `Dockerfile`：

1. web build stage：
   - 使用 Node 镜像。
   - 安装 web 依赖。
   - 运行 `yarn --cwd web build`。
2. fastapi runtime stage：
   - 使用 Python slim 镜像。
   - 复制 Python 项目文件。
   - 从 web stage 复制 `web/dist` 到 `src/termbridge/static`。
   - `pip install .`。
   - `EXPOSE 9008`。
   - 默认命令：`termbridge --host 0.0.0.0 --port 9008`。

新增 `.dockerignore`：

- `.git`
- `.termbridge`
- `.venv`
- `dist`
- `web/node_modules`
- Python/tooling caches
- 临时构建输出

### 5. 测试覆盖

修改 `tests/test_api.py`：

1. 使用 `tmp_path` 创建临时 web 目录，包含：
   - `index.html`
   - 一个静态 asset 文件
2. 验证：
   - `/` 返回 `index.html`
   - `/environment` 返回 `index.html`
   - `/shortcuts` 返回 `index.html`
   - asset 路径返回 asset 内容
   - `/api/missing` 返回 404
   - `/health` 仍返回 `{"status": "ok"}`
3. 保持现有 API 测试不变。

### 6. 文档更新

修改 `README.md`：

1. 增加 Docker 构建与运行命令。
2. 增加 wheel 构建流程：前端 build、复制静态制品、`uv build`、安装运行。
3. 说明 `termbridge` 默认服务前端；`--no-web` 可用于 API-only 调试。
4. 说明 Docker/wheel 不自动安装 `ttyd`、`tmux`、Cygwin 或 WSL runtime。

## Files to change

- `src/termbridge/api.py`
- `src/termbridge/main.py`
- `pyproject.toml`
- `tests/test_api.py`
- `Dockerfile`
- `.dockerignore`
- `README.md`
- 如决定不提交生成制品，更新 `.gitignore` 忽略 `src/termbridge/static/`

## Verification plan

1. Python checks：
   - `uv run ruff check .`
   - `uv run mypy src tests`
   - `uv run pytest`
2. web checks：
   - `yarn --cwd web lint`
   - `yarn --cwd web typecheck`
   - `yarn --cwd web build`
3. Wheel：
   - 将 `web/dist/*` 复制到 `src/termbridge/static/`
   - `uv build`
   - 检查 wheel 内包含 `termbridge/static/index.html` 和 assets
   - 安装 wheel 后运行 `termbridge --host 127.0.0.1 --port 9008`
   - 验证 `/`、`/environment`、`/shortcuts`、`/health`、`/api/sessions`
4. Docker：
   - `docker build -t termbridge:local .`
   - `docker run --rm -p 9008:9008 termbridge:local`
   - 验证同样 URL

## Assumptions

1. wheel 构建采用显式前端构建和复制制品流程，不把 Node/Yarn 作为 Python build hook 的隐式依赖。
2. `src/termbridge/static/` 是生成目录，默认不作为源码长期维护。
3. `termbridge` 默认服务前端，但在没有构建制品时不报错，自动保持 API-only，避免破坏开发流程。

## Risks

1. Docker 容器内的 `ttyd`、`tmux` 和具体 shell/runtime 依赖仍可能缺失；本计划只解决 Web 应用打包，不解决所有终端 runtime 安装。
2. SPA fallback 若实现过宽，可能吞掉 API 404；测试必须覆盖 `/api/missing`。
3. Hatch package-data 行为需要通过实际 wheel 内容验证，不能只依赖配置假设。

## Rollback

1. 移除 Dockerfile 和 `.dockerignore`。
2. 恢复 `create_app()` 默认 API-only 行为。
3. 移除 CLI 新增参数。
4. 移除 wheel 静态资源 include 配置。
