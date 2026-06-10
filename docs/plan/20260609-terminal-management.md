# 终端管理功能实施计划

Review status: Accepted

当前：严格模式 / strict，计划 / Plan

## Requirement and spec basis

- Requirement：`docs/requirement/20260609-terminal-management.md`，Review status: Accepted
- Spec：`docs/spec/20260609-terminal-management.md`，Review status: Accepted

目标是在不破坏现有 session 生命周期的前提下，新增终端管理能力：系统终端检测、用户终端持久化、Cygwin 模式适配、按启动模式解析 ttyd 可执行文件配置，并让创建 session 使用“终端”概念。

## Implementation steps

### 1. 后端模型扩展

修改 `src/cc_ttyd/models.py`：

- 新增枚举/字面量模型：
  - `TerminalSource`: `system | user`
  - `TerminalLaunchType`: `direct | cygwin`
- 新增终端模型：
  - `TerminalDefinition`
  - `TerminalListResponse`
  - `CreateTerminalRequest`
  - `UpdateTerminalRequest`
- 新增 ttyd 配置模型：
  - `TerminalSettings`
  - `UpdateTerminalSettingsRequest`
- 扩展 `CreateSessionRequest`：
  - 新增 `terminal_id: str | None`
  - 保留 `runtime` 和 `terminal_command` 作为兼容字段。

### 2. 后端持久化 repository

修改 `src/cc_ttyd/repositories.py`：

- 新增文件型 `FileTerminalRepository`。
- 持久化内容至少包含：
  - 用户自定义终端列表。
  - 系统终端 hidden/enabled 覆盖状态。
  - ttyd executable 配置：模式化解析配置（auto/explicit），explicit 保存完整路径，auto 按启动模式解析。
- 存储文件建议：`settings.state_dir / "terminals.json"`。
- 行为约束：
  - user terminal 可 create/update/delete。
  - system terminal 不存在于用户列表，只保存覆盖状态。
  - 文件不存在时返回默认空状态。

### 3. 后端终端检测与解析服务

新增或扩展 `src/cc_ttyd/services.py`：

- 新增 `TerminalService`：
  - `list_terminals()`：合并系统终端、检测终端、用户终端和持久化覆盖状态。
  - `create_terminal()` / `update_terminal()` / `delete_terminal()`。
  - `get_settings()` / `update_settings()`。
  - `resolve_terminal_command(terminal_id, workspace)`：返回可传给 ttyd 的 terminal command。
- 系统终端：
  - Windows: PowerShell、cmd。
  - 非 Windows: bash/sh，按可用性检测。
- CLI 检测：
  - 初始检测 `claude`、`mini-claude`、`codex`。
  - 使用服务进程 `PATH` 检测可执行命令。
- Cygwin 启动模式：
  - `cygwin_bash_path` 必须是 Windows 可执行路径。
  - Cygwin 命令内部执行 `cd <workspace-forward-slash> && exec <command>`。
  - cygwin 模式下 `<command>` 是用户配置的整段命令，例如 `ccl run m 3 -c`，不拆分为 argv。
  - workspace 转换为 forward slash 形式，例如 `D:/SourceCodes/...`。
  - Cygwin 命令字符串必须集中 quote，避免路径空格或特殊字符破坏命令。
- ttyd executable 解析：
  - explicit：用户提供完整路径，直接断言文件存在并使用。
  - direct + auto：从服务进程/Windows PATH 解析 `ttyd`。
  - cygwin + auto：从 Cygwin 环境 PATH 解析 `ttyd`，必要时通过 `cygwin_bash_path` 执行 `command -v ttyd` 并用 `cygpath -w` 转为 Windows 路径。

### 4. SessionService 接入终端配置

修改 `src/cc_ttyd/services.py` 的 `SessionService`：

- 构造函数注入 `TerminalService` 或 terminal resolver。
- `create()` 中优先使用 `request.terminal_id`：
  - 有 `terminal_id`：从 TerminalService 解析命令。
  - 无 `terminal_id`：沿用现有 `RuntimeRegistry.resolve(runtime, terminal_command)` 兼容逻辑。
- `_build_ttyd_command()` 的 ttyd executable 来源改为 TerminalService/settings 中按 terminal launch type 解析后的配置：
  - explicit：用户配置完整路径后直接使用。
  - direct + auto：从服务进程/Windows PATH 找 `ttyd`。
  - cygwin + auto：从 Cygwin PATH 找 `ttyd`。
- 保留现有日志，并新增 terminal/ttyd 配置解析日志。

### 5. 后端 DI 与 API

修改 `src/cc_ttyd/di.py`：

- 新增 `get_terminal_repository()`。
- 新增 `get_terminal_service()`。
- 注入到 `SessionService`。

修改 `src/cc_ttyd/api.py`：

- `GET /api/terminals`
- `POST /api/terminals`
- `PUT /api/terminals/{terminal_id}`
- `DELETE /api/terminals/{terminal_id}`
- `GET /api/terminal-settings`
- `PUT /api/terminal-settings`

错误映射：

- 删除系统终端：400 或 403。
- 找不到终端：404。
- 无效 cygwin/命令配置：400。
- 持久化失败：500。

### 6. 前端类型与 API

修改或新增：

- `frontend/src/types/sessions.ts` 或新文件：增加终端类型。
- `frontend/src/api/sessions.ts` 或新 API 文件：增加终端管理请求函数。

前端类型需要覆盖：

- terminal source
- launch type
- command/args（direct 可拆分为 program + args；cygwin command 是整段命令，args 可为空或忽略）
- cygwin bash path/cygwin bash args
- hidden/enabled/deletable/detected
- ttyd executable 设置（auto/explicit）

### 7. 前端终端管理入口与 UI

修改顶层右上角工具条相关组件：

- 增加「终端管理」按钮。
- 点击打开终端管理界面。

新增 `frontend/src/components/TerminalManagement.vue`：

- 展示系统终端和用户终端。
- 系统终端：
  - 展示不可删除状态。
  - 支持隐藏/启用切换。
- 用户终端：
  - 新增、编辑、删除。
  - 支持 direct/cygwin 启动方式。
  - cygwin 模式展示 `cygwin_bash_path`、`cygwin_bash_args`、`command` 字段。
- ttyd 配置：
  - 展示当前 ttyd executable 解析策略。
  - 默认 `auto`，按终端启动模式解析 `ttyd`。
  - 允许输入明确可执行文件路径作为 `explicit`。

### 8. 创建 session 表单接入终端列表

修改 `frontend/src/components/SessionCreateForm.vue`：

- 初始化加载 `/api/terminals`。
- 终端选择列表使用 `TerminalDefinition`。
- 创建 session 时发送 `terminal_id`。
- 保留临时自定义命令入口作为兼容/快捷方式，但用户文案建议保存到终端管理。
- 移除用户可见 `Runtime` 文案残留。

### 9. 后端测试

新增或扩展测试：

- `tests/test_terminal_service.py`
  - 系统终端列表生成。
  - PATH 检测 claude/mini-claude/codex 可模拟。
  - 用户终端 create/update/delete。
  - 系统终端不可删除。
  - hidden/enabled 覆盖状态持久化。
  - ttyd executable 配置持久化。
  - direct 命令解析不经 shell。
  - cygwin 命令构造包含 workspace cd，保留用户命令为整段命令，并正确 quote 系统插入片段。
  - ttyd executable direct auto 从服务进程 PATH 解析。
  - ttyd executable cygwin auto 从 Cygwin PATH 解析。
- `tests/test_services.py`
  - `SessionService.create()` 使用 `terminal_id` 优先。
  - 未传 `terminal_id` 时旧 runtime/custom command 仍可用。
  - ttyd executable 使用配置值。
- `tests/test_api.py` 或新增 API 测试
  - 终端列表 API。
  - 用户终端 CRUD。
  - 删除系统终端失败。
  - terminal settings 读取/更新。

### 10. 前端验证

至少运行：

- `cd /d/SourceCodes/agentic/cc-ttyd/frontend && yarn lint`
- `cd /d/SourceCodes/agentic/cc-ttyd/frontend && yarn format:check`
- `cd /d/SourceCodes/agentic/cc-ttyd/frontend && yarn typecheck`
- `cd /d/SourceCodes/agentic/cc-ttyd/frontend && yarn build`

### 11. 后端验证

至少运行：

- `cd /d/SourceCodes/agentic/cc-ttyd && uv run pytest`
- `cd /d/SourceCodes/agentic/cc-ttyd && uv run ruff check .`
- `cd /d/SourceCodes/agentic/cc-ttyd && uv run ruff format --check .`

## Files to change

预计修改：

- `src/cc_ttyd/models.py`
- `src/cc_ttyd/repositories.py`
- `src/cc_ttyd/services.py`
- `src/cc_ttyd/runtime.py`（兼容调整，尽量少改）
- `src/cc_ttyd/settings.py`
- `src/cc_ttyd/di.py`
- `src/cc_ttyd/api.py`
- `tests/test_terminal_service.py`（新增）
- `tests/test_services.py`
- `tests/test_api.py` 或新增终端 API 测试
- `frontend/src/types/sessions.ts` 或新增 terminal types
- `frontend/src/api/sessions.ts` 或新增 terminal API
- `frontend/src/components/AppStatus.vue` 或顶层工具条相关组件
- `frontend/src/components/TerminalManagement.vue`（新增）
- `frontend/src/components/SessionCreateForm.vue`

## Verification plan

- 后端单测覆盖终端检测、持久化、命令解析、Cygwin command 模板、按模式解析 ttyd executable 配置和 session 创建兼容。
- 前端 typecheck 保证新增类型和 API 接入正确。
- 前端 lint/format/build 确保 UI 改动符合项目规范。
- 手动验证：
  1. 打开页面右上角「终端管理」。
  2. 能看到 PowerShell/cmd 和检测到的 CLI。
  3. 新增 Cygwin 模式终端：`ccl run m 3 -c`。
  4. 设置 cygwin bash path 为 `D:\ProgramFiles\Cygwin64\bin\bash.exe`。
  5. 设置 ttyd executable 为 auto，确认 cygwin 模式从 Cygwin PATH 找到 ttyd；或设置 explicit 路径。
  6. 创建 session 选择该终端，确认进入指定 workspace。

## Blockers

- 终端管理 UI 形态：使用独立路由/页面，右上角工具条入口跳转到该页面；页面主区域用卡片展示终端列表，工具条提供「ttyd 启动器」和「新建终端」入口；ttyd 配置、新建、编辑、删除确认均使用模态窗，自定义终端卡片可删除。
- `cygwin_bash_args` 默认策略未最终确认：计划默认使用 `-lc`；用户需要 alias 时可改为 login/interactive 参数。

## Assumptions

- 当前单用户本地工具，不引入账号体系。
- 状态文件继续放在现有 `state_dir` 下。
- 系统终端隐藏/启用覆盖状态需要持久化。
- direct 命令继续不经 shell 执行。
- cygwin 命令只在用户选择 cygwin launch type 时使用。
- cygwin 模式下用户命令按整段命令保存和执行，不拆分为 argv。

## Risks

- Cygwin command quoting 需要特别小心：用户命令是整段命令，不能被错误拆分或重写；系统只负责安全插入 workspace cd 和执行包装。
- 前端改动范围较大，可能需要压缩 UI 复杂度以保持当前 light 风格。
- `runtime` 兼容字段和新增 `terminal_id` 同时存在时，需要明确优先级并用测试固定。

## Rollback

- 后端保留 runtime/custom command 兼容路径；如 terminal API 出问题，可让前端回退到旧创建 session 请求。
- 终端配置持久化文件独立于 sessions 文件，删除或忽略该文件不会破坏已有 sessions 数据。
- ttyd executable 配置错误时可以清空 explicit 路径，回退到按启动模式 auto 解析。

## User review notes

- 用户要求进入 Plan，因此 Spec 已标记为 `Accepted`。
- 用户澄清：ttyd 查找不是单一 PATH 语义，而是由终端启动模式决定；direct 使用服务进程/Windows PATH，cygwin 使用 Cygwin PATH，explicit 完整路径直接使用。
- 用户澄清：`ccl run m 3 -c` 是整段命令，在 cygwin 模式下不需要也不应该拆分。
