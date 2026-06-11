# 首页环境引导轻量验证

Review status: Accepted

## What changed

- 引入 vue-router 和 Pinia。
- 将根路径 `/` 改为环境就绪分流入口：任一环境可用时进入 `/session`，无可用环境时展示首页引导。
- 将原会话/终端工作台迁移到 `/session`，并保留环境管理和快捷方式管理在同一 shell 内展示。
- 新增无可用环境首页，展示 Windows/Cygwin、Windows/WSL、Linux 三种运行环境选择。
- 首页环境卡片跳转到 `/environment?tab=<host>`，环境管理页按 query 打开对应 tab。
- 新增 `/help` 帮助页入口，当前内容显示“即将到来”/“Comming Soon”。

## Acceptance

- [x] 当没有任何可用运行环境时，访问主页展示环境引导，而不是会话/终端界面。
- [x] 当任一运行环境可用时，访问主页进入 `/session`。
- [x] `/session` 承载现有会话管理和终端主界面。
- [x] 未就绪主页展示 Windows/Cygwin、Windows/WSL、Linux 三种运行环境选择。
- [x] 点击某个运行环境选择后，进入环境管理页对应配置位置。
- [x] 未就绪主页提供可见的配置说明链接，点击后进入 `/help`，帮助页显示“即将到来”/“Comming Soon”。
- [x] 未就绪状态下不应引导用户新建会话到不可完成的流程。

## Commands

- `yarn --cwd frontend build`：通过。Vite/Rolldown 对 `@vueuse/core` 的 PURE annotation 输出 warning，但构建成功。
- `yarn --cwd frontend lint`：通过。
- `yarn --cwd frontend dev --host 127.0.0.1`：启动成功，端口自动落到 9009。
- 通过 HTTP 检查 `/`、`/session`、`/environment?tab=windows_wsl`、`/help` 均返回前端 shell。
- 调整帮助入口后重新运行 `yarn --cwd frontend build` 和 `yarn --cwd frontend lint`：通过。

## Remaining risk

- 当前会话没有可用浏览器自动化工具，未进行真实浏览器点击验证；已用 Vite dev server 和 HTTP route 检查覆盖路由入口。
- 路由分流依赖 `/api/environments` 的 readiness summary，若后端状态与环境管理页检测结果不一致，首页分流也会不一致。
