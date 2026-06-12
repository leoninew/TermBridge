# 打包与分发需求

Review status: Accepted

当前：标准模式 / standard，计划阶段 / Plan

## Background

TermBridge 当前以开发模式运行：Vite 单独提供前端页面并代理 `/api`、`/health` 到 FastAPI 后端；后端 wheel 只包含 Python 代码，不包含前端构建制品；项目中尚无 Dockerfile。

本需求希望提供两种分发形态：Docker 镜像和 Python wheel。两者都应先构建前端，再由后端提供静态页面服务，使部署后只需要启动后端入口即可访问页面和 API。

## Goals

1. 提供基于 `Dockerfile` 的镜像构建方式。
2. Docker 构建流程先构建前端，再把前端制品放入后端可服务的静态资源目录。
3. FastAPI 后端能够提供前端静态页面，并支持 SPA history fallback。
4. Python wheel 包包含前端构建制品。
5. 安装 wheel 后，通过现有 `termbridge` 命令即可启动后端并提供前端页面。
6. 保留当前开发体验：后端仍可 API-only 运行，前端仍可使用 Vite dev server 代理到后端。

## Non-goals

1. 不在本需求中引入多个 CLI 子命令；用户已确认不需要子命令。
2. 不在本需求中完整解决 `ttyd`、`tmux`、Cygwin、WSL、Linux runtime 的安装问题。
3. 不改变现有 API 路径、前端页面路由或业务功能语义。
4. 不把前端 API base URL 改成环境变量；当前同源相对路径继续适用。
5. 不做生产级安全加固，例如认证、HTTPS、多用户隔离或反向代理配置。

## User scenarios

### 场景 1：使用 Docker 镜像运行

用户执行 Docker 构建命令生成镜像，运行容器后访问后端端口即可打开 TermBridge 页面，并能调用 `/api` 与 `/health`。

### 场景 2：安装 wheel 后运行

用户构建 wheel 并安装后，执行 `termbridge --host 127.0.0.1 --port 9008`，后端启动并提供前端页面。

### 场景 3：继续本地开发

开发者仍可运行后端 API 服务并使用 Vite dev server，保持现有前端热更新和代理开发方式。

## Acceptance criteria

1. 项目根目录提供可构建的 `Dockerfile`。
2. Docker 构建过程中执行前端构建，并将 `web/dist` 制品纳入后端镜像。
3. Docker 容器默认启动 `termbridge` 并监听 `0.0.0.0:9008`。
4. 后端能返回前端 `index.html`。
5. `/environment`、`/shortcuts` 等前端 history 路由能 fallback 到 `index.html`。
6. `/api/*` 的不存在路径仍返回 API 404，不被 SPA fallback 吞掉。
7. `/health` 仍返回 `{"status": "ok"}`。
8. wheel 构建产物包含前端静态资源。
9. 安装 wheel 后执行 `termbridge` 即可启动后端并提供前端页面，不要求用户再启动 Vite。
10. 当前开发模式仍可用：前端 dev server 继续代理 `/api` 和 `/health` 到后端。
11. 新增或更新测试覆盖静态页面服务、SPA fallback 和 API 404 边界。
12. 文档或构建命令说明 wheel 构建前需要先生成并纳入前端制品。

## Open questions

1. wheel 构建时是否应自动执行前端构建，还是保持显式两步：先 `yarn --cwd web build`，再复制制品并 `uv build`？
   - 当前倾向：显式两步，避免 Python 构建后端隐式依赖 Node/Yarn。
2. `src/termbridge/static/` 是否提交到仓库？
   - 当前倾向：作为生成制品，不提交；Docker 和 release 构建时生成。

## Decisions

1. 不引入 CLI 子命令；`termbridge` 默认承担生产运行入口。
2. 后端提供同源静态页面服务，前端继续使用相对路径调用 API。
3. SPA fallback 只应用于非 `/api`、非 `/health` 的前端页面请求。
4. Docker 先构建前端，再安装并运行后端。

## User review notes

- 2026-06-10：用户提出需要 Docker 镜像和 wheel 两种分发形态，前端先构建，再由后端提供静态页面服务。
- 2026-06-10：用户确认不需要 CLI 子命令。
