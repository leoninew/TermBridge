# 终端管理功能验证

Review status: Accepted

当前：严格模式 / strict，验证 / Verification

## Requirement alignment

- 已提供用户可见的「终端管理」概念，创建 session 表单不再暴露 runtime 文案。
- 已支持系统终端、检测到的 CLI 终端和用户自定义终端。
- 系统终端不可删除；用户终端可新增、编辑、删除，并持久化。
- 已支持 `direct` 与 `cygwin` 启动方式；`cygwin` 命令按整段命令保存和执行。
- 已提供 ttyd 启动器配置：`auto` 按终端启动方式解析，`explicit` 使用用户指定路径。
- 终端管理从右上角工具条进入独立页面。

## Spec alignment

- 后端新增终端模型、持久化 repository、终端服务、API 和 session 创建接入。
- `terminal_id` 优先于兼容的 `runtime`/`terminal_command` 路径。
- direct 命令不经 shell；cygwin 命令通过 `bash -lc` 执行，并只 quote 系统插入的 workspace 路径。
- ttyd explicit 配置校验路径存在；auto direct 使用服务进程 PATH；auto cygwin 通过 Cygwin bash 查询 PATH。
- 前端新增终端管理页面、终端 API 类型、创建 session 表单终端选择。

## Plan alignment

- `src/cc_ttyd/models.py`、`repositories.py`、`services.py`、`di.py`、`api.py` 已按计划扩展。
- 新增 `tests/test_terminal_service.py`，并扩展 session/service 覆盖 terminal_id 路径。
- 前端 `AppStatus.vue`、`App.vue`、`SessionCreateForm.vue`、`TerminalManagement.vue` 已接入终端管理。
- 最新 UI 决策已实现：终端管理独立页面，主区域使用紧凑终端卡片列表，工具条提供「ttyd 启动器」和「新建终端」，ttyd 配置、新建、编辑、删除均使用模态窗。

## Actual diff summary

- 后端：增加终端定义、终端状态持久化、终端 CRUD API、ttyd 设置 API、Cygwin 命令解析和 session terminal_id 创建路径。
- 前端：增加终端管理页面、路由式页面切换、终端选择创建 session、ttyd 配置模态窗、终端 CRUD 模态窗和紧凑终端卡片布局。
- 文档：requirement/spec/plan 记录 ttyd 配置能力、Cygwin 语义和 UI 决策。

## Acceptance checklist

- [x] Windows 系统终端和检测终端可列出。
- [x] 系统终端不可删除。
- [x] 用户自定义终端可新增、编辑、删除并持久化。
- [x] `cygwin` 模式保留 `custom-agent run` 为整段命令。
- [x] 创建 session 可通过 `terminal_id` 使用已配置终端。
- [x] ttyd 可使用 auto 或 explicit 配置。
- [x] 终端管理入口在右上角工具条，使用独立页面。
- [x] 终端管理页面使用卡片列表和模态窗交互。

## Commands

- `cd /d/Projects/TermBridge && uv run pytest`
  - 结果：38 passed, 1 warning。
- `cd /d/Projects/TermBridge && uv run ruff check .`
  - 结果：All checks passed。
- `cd /d/Projects/TermBridge && uv run ruff format --check .`
  - 结果：19 files already formatted。
- `cd /d/Projects/TermBridge/frontend && yarn lint`
  - 结果：通过。
- `cd /d/Projects/TermBridge/frontend && yarn format:check`
  - 结果：All matched files use Prettier code style。
- `cd /d/Projects/TermBridge/frontend && yarn typecheck`
  - 结果：通过。
- `cd /d/Projects/TermBridge/frontend && yarn build`
  - 结果：构建通过；Vite/Rolldown 对 `node_modules/@vueuse/core` 的 `/* #__PURE__ */` 注释给出 warning，不影响构建。

## Missed or expanded scope

- 扩展：根据用户后续决策，将终端管理从轻量面板改为独立页面，并将 ttyd 配置、新建、编辑、删除统一改为模态窗。
- 未完成项：暂无已知功能缺口。

## Remaining risks

- `cygwin_bash_args` 当前默认 `-lc`；如果用户需要 alias 或 interactive/login 行为，可能需要显式调整参数。
- Cygwin PATH 中解析 `ttyd` 依赖用户配置的 `cygwin_bash_path` 可执行且环境正确。
- 构建 warning 来自依赖包注释位置，不是本次业务代码问题。

## Conclusion

终端管理功能已按当前严格模式文档完成实现和验证，可进入交付 review。
