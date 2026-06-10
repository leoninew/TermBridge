# 终端管理功能规格

Review status: Accepted

当前：严格模式 / strict，规格 / Spec

## Requirement basis

基于 `docs/requirement/20260609-terminal-management.md`，该需求已接受。核心目标是将用户可见的 `runtime` 概念升级为「终端管理」：系统终端自动识别、用户终端持久化管理、ttyd 可执行文件可配置，并解决 Windows ttyd 与 Cygwin 命令集成问题。

## Overview

新增一个 Terminal Management 后端能力和前端管理入口：

- 后端集中管理终端配置、系统终端检测、用户终端持久化、ttyd 可执行文件配置。
- 前端右上角工具条提供「终端管理」入口。
- 创建 session 表单从终端列表中选择终端，不再把 `runtime` 暴露为用户概念。
- 终端启动方式支持：
  - `direct`：直接执行 Windows/PATH 可见命令。
  - `cygwin`：通过 Cygwin 环境执行命令，用于 Cygwin bash、Cygwin PATH、Cygwin 脚本和用户工作流。
- ttyd 启动器默认按终端启动方式从对应环境的 `PATH` 查找 `ttyd`；用户配置明确可执行文件路径时直接断言并使用该路径。

## Design decisions

### 用户可见概念

- UI、接口展示层、文案统一使用「终端」而不是 `runtime`。
- 后端可短期保留 `runtime` 字段作为兼容层，但新增模型和 API 应围绕 `terminal` 命名。

### 终端来源

终端分为两类：

1. `system`
   - 系统内置或自动检测出的终端。
   - 不可删除。
   - 可隐藏/停用，隐藏状态需要持久化。
2. `user`
   - 用户自定义终端。
   - 可新增、编辑、删除、隐藏/停用。
   - 持久化到项目状态目录。

### 终端启动方式

#### direct

适用于 Windows 进程环境或当前服务进程 `PATH` 可直接解析的命令：

- PowerShell
- cmd
- `claude`
- `mini-claude`
- 其他 Windows PATH 中的 CLI

命令构造：

```text
<program> <args...>
```

后端使用 `shlex.split` 或结构化参数拆分，不经过 shell。该规则只适用于 `direct`。

#### cygwin

适用于需要 Cygwin 环境的命令：

- `ccl run m 3 -c` 在 cygwin 模式下是整段命令，不拆分为 argv
- 依赖 Cygwin PATH 的脚本
- 用户 Cygwin shell alias/function

配置字段应表达：

- `cygwin_bash_path`：Windows 可执行文件路径，例如 `D:\ProgramFiles\Cygwin64\bin\bash.exe`
- `cygwin_bash_args`：默认可为 `-lc`，用户需要 alias/function 时可配置 login/interactive 参数
- `command`：在 Cygwin 环境内执行的整段命令，例如 `ccl run m 3 -c`；该字段不拆分为 argv
- `workspace_strategy`：进入 workspace 的方式

推荐 Cygwin 模板：

```text
D:\ProgramFiles\Cygwin64\bin\bash.exe -lc 'cd "D:/SourceCodes/agentic/cc-ttyd" && exec ccl run m 3 -c'
```

说明：

- Windows 进程启动 Cygwin bash 必须使用 Windows 路径的 `bash.exe`。
- Cygwin bash 可直接 `cd "D:/..."`，也可使用 `cygpath -u` 转换。
- 若用户需要 alias/function，应允许配置 login/interactive 参数，但默认不强行解析 shell 初始化文件。

### workspace 处理

现有 ttyd 命令使用 `--cwd <workspace>`。对 `direct` 终端继续使用 ttyd `--cwd`。

对 `cygwin` 终端：

- ttyd 仍传 `--cwd <workspace>`，作为外层进程工作目录。
- Cygwin 命令内部也应在执行用户命令前 `cd <workspace>`，保证 Cygwin 环境内路径语义正确。
- Windows 路径统一转为 forward slash 形式传入 Cygwin 命令，例如 `D:/SourceCodes/agentic/cc-ttyd`，避免反斜杠转义问题。

### ttyd 可执行文件配置

新增 ttyd 配置能力：

- ttyd 配置支持两种形式：
  - `auto`：按终端启动模式从对应环境的 `PATH` 查找 `ttyd`。
  - `explicit`：用户指定明确可执行文件路径，后端直接断言该路径并使用。
- `direct` 模式下，`auto` 使用服务进程/Windows 环境 PATH 查找 `ttyd`。
- `cygwin` 模式下，`auto` 使用 Cygwin 环境 PATH 查找 `ttyd`，例如通过 Cygwin bash 或 Cygwin 路径解析得到 `/usr/local/bin/ttyd` 对应的 Windows executable。
- 用户可指定明确可执行文件路径，例如 `D:\ProgramFiles\Cygwin64\usr\local\bin\ttyd.exe`。
- 后端启动 session 时使用按模式解析后的 ttyd executable。
- 配置项应持久化，避免重启后丢失。

## Affected components

### Backend

- `src/cc_ttyd/models.py`
  - 新增终端配置模型、请求/响应模型、ttyd 配置模型。
- `src/cc_ttyd/services.py`
  - 新增或拆分 `TerminalService`，负责终端列表合并、检测、持久化和命令解析。
  - `SessionService` 改为通过终端配置解析启动命令。
- `src/cc_ttyd/repositories.py`
  - 新增文件持久化 repository，用于用户终端配置和系统隐藏状态。
- `src/cc_ttyd/runtime.py`
  - 逐步降级为兼容层，或迁移为 terminal resolver。
- `src/cc_ttyd/settings.py`
  - 增加 ttyd executable 配置默认值和状态文件路径。
- `src/cc_ttyd/api.py`
  - 新增终端管理 API 和 ttyd 配置 API。
- `src/cc_ttyd/di.py`
  - 新增 TerminalService 依赖注入。

### Frontend

- `frontend/src/components/AppStatus.vue` 或顶层工具条组件
  - 右上角新增「终端管理」入口。
- 新增 `TerminalManagement` 组件
  - 展示系统终端、用户终端、隐藏/启用状态。
  - 支持用户终端新增、编辑、删除。
  - 支持 ttyd executable 配置。
- `frontend/src/components/SessionCreateForm.vue`
  - 终端选择来源改为终端 API。
  - 继续支持临时自定义命令，但推荐保存为用户终端。
- `frontend/src/api/sessions.ts` 或新增 API 模块
  - 增加终端管理和 ttyd 配置请求。
- `frontend/src/types/sessions.ts` 或新增 types 文件
  - 增加终端相关类型。

## Interfaces

### Terminal model

```ts
type TerminalSource = 'system' | 'user'
type TerminalLaunchType = 'direct' | 'cygwin'

interface TerminalDefinition {
  id: string
  name: string
  source: TerminalSource
  launch_type: TerminalLaunchType
  command: string // direct 可配合 args；cygwin 下为整段命令，不拆分
  args: string[] // direct 参数；cygwin 下为空或忽略
  cygwin_bash_path?: string
  cygwin_bash_args?: string[]
  hidden: boolean
  enabled: boolean
  deletable: boolean
  detected: boolean
}
```

### API draft

- `GET /api/terminals`
  - 返回系统终端和用户终端的合并列表。
- `POST /api/terminals`
  - 新增用户终端。
- `PUT /api/terminals/{terminal_id}`
  - 编辑用户终端，或更新隐藏/启用状态。
- `DELETE /api/terminals/{terminal_id}`
  - 删除用户终端；系统终端返回 400/403。
- `GET /api/terminal-settings`
  - 返回 ttyd executable 配置和检测状态。
- `PUT /api/terminal-settings`
  - 更新 ttyd executable 配置。

### Session create compatibility

短期兼容：

- `CreateSessionRequest.runtime` 可以继续存在。
- 新增 `terminal_id` 优先级高于 `runtime`。
- 如果 `terminal_id` 缺失，沿用现有 runtime/custom command 行为。

长期目标：

- 前端只使用 `terminal_id` 和终端管理 API。
- `runtime` 仅作为旧数据兼容。

## Technical questions

- 系统级 Claude Code/Codex 检测清单需要明确命令名：初始建议检测 `claude`、`mini-claude`、`codex`。
- 本阶段启动方式明确为 `direct` 和 `cygwin`；MSYS/Git Bash 不混入 `cygwin`，后续如需要再扩展新的 launch type。
- 终端管理 UI 使用独立路由/页面，入口位于右上角工具条。
- `cygwin_bash_args` 默认是否使用 `-lc` 还是 `--login -i -c`。如果需要 alias，通常需要 login/interactive；但这可能改变启动速度和副作用。
- cygwin 模式 `ttyd auto` 如何解析 Cygwin PATH：可通过 Cygwin bash 执行 `command -v ttyd` 后用 `cygpath -w` 转为 Windows executable 路径，或要求用户显式配置完整路径。

## Risks

- Cygwin 命令拼接存在注入风险；cygwin 模式下用户命令作为整段命令执行，不拆分 argv，因此必须只对 workspace 等系统插入片段做集中转义，不要错误重写用户命令语义。
- Windows/Cygwin 路径转换容易出错；必须用测试覆盖路径构造。
- 直接检测 `PATH` 不能发现 Cygwin 环境内脚本，如 `ccl`；这类应通过 cygwin 启动方式解决。
- 系统终端隐藏状态持久化后，需要保留恢复入口，避免用户无法找回系统终端。
- `runtime` 到 `terminal` 的迁移要避免破坏现有 session 数据和测试。

## Alternatives

- 只保留自由文本自定义命令：实现简单，但不能支持持久化管理、系统终端不可删除、Cygwin 适配层等需求。
- 强制所有命令都通过 shell 执行：兼容 alias，但增加注入风险，也不符合当前不经 shell 执行的安全设计。
- 彻底移除 `runtime` 字段：语义最干净，但迁移成本较高，容易破坏现有 API 和测试；本阶段不推荐。

## User review notes

- 用户补充：ttyd 配置能力由终端启动方式决定；direct 模式从服务进程/Windows PATH 找，cygwin 模式从 Cygwin PATH 找。用户直接配置完整路径时后端直接断言并使用。
- 用户澄清：`ccl run m 3 -c` 是整段命令，cygwin 模式下不拆分为 argv。
- 用户要求进入 Spec，因此 Requirement 已标记为 `Accepted`。
