# 终端管理功能需求

Review status: Accepted

当前：严格模式 / strict，需求 / Requirement

## Background

当前系统仍有内部 `runtime` 概念，并在创建 session 的流程中作为终端选择来源。用户视角下真正需要管理的是“终端”：系统内置终端、自动检测到的 AI CLI 工具，以及用户自己的 shell/alias/命令组合。

用户当前环境包含 Cygwin bash，并有个人化命令入口，例如：

- `claude` 是 alias：`claude --dangerously-skip-permissions`
- `mini-claude` 位于 `/usr/local/bin/mini-claude`
- `ccl run m 3 -c` 是用户自定义工作流入口，依赖 Cygwin 环境；这是整段命令，不需要拆分为 argv。

Windows 版 ttyd 启动进程时默认处于 Windows 进程环境。`claude`、`mini-claude` 如果已经在 Windows 系统环境变量 `PATH` 中，可以作为普通命令直接启动；但依赖 Cygwin 的命令、alias 或 shell 初始化逻辑，不能假定 Windows 进程环境直接可用，需要通过 Cygwin bash 作为适配层启动。

这些都应被视为可管理的自定义终端，而不是 runtime。

## Goals

- 提供「终端管理」功能入口，避免继续把 `runtime` 作为用户可见概念。
- 在页面右上角工具条提供进入终端管理的入口。
- 后端识别当前运行平台架构，并提供系统内置终端候选。
- Windows 平台默认识别并展示 PowerShell、cmd 等系统终端。
- 检查当前环境中是否存在 Claude Code、Codex 等命令行工具，并作为系统级终端候选展示。
- 系统级终端属于系统能力，不允许用户删除。
- 支持用户自定义终端命令，例如 Cygwin bash、带 alias 的 `claude`、`mini-claude`、`ccl run m 3 -c` 等个人工作流入口。
- 自定义终端需要支持不同启动方式：直接 Windows 命令，以及通过 Cygwin bash 包装执行的命令。
- 对依赖 Cygwin 的命令，系统需要允许配置 shell 适配层，例如通过 Cygwin bash 执行 `ccl run m 3 -c`。
- 用户自定义终端配置需要持久化，并支持新增、编辑、停用/隐藏和删除。
- 创建 session 时使用“终端”概念选择启动命令，保持现有 session 启动能力。
- 提供 ttyd 可执行文件配置能力：默认按终端启动模式从对应环境的 `PATH` 查找 `ttyd`，也允许用户显式指定 ttyd 可执行文件路径。

## Non-goals

- 不重做完整视觉设计系统。
- 不改变现有 session 生命周期和 ttyd 启动语义。
- 不引入用户认证、多用户权限或远程终端配置同步。
- 不允许用户删除系统内置或自动检测出的系统级终端，只允许隐藏/停用。
- 本阶段不实现复杂 shell 初始化文件解析；alias 是否可用以实际启动命令所在 shell 环境为准。
- 不自动猜测所有 Cygwin/MSYS/Git Bash 安装位置；可以优先支持显式配置 shell 路径，自动探测作为增强。
- 不强制一次性移除后端内部字段名 `runtime`，如果为了兼容测试和 API 需要保留内部字段，用户可见语义仍必须是“终端”。

## User scenarios

- 作为 Windows 用户，我打开终端管理时，能看到系统提供的 PowerShell 和 cmd，且它们不可删除。
- 作为安装了 Claude Code 或 Codex 的用户，我希望系统能检测到这些 CLI，并把它们作为可选终端入口展示。
- 作为使用 Cygwin bash 的用户，我希望添加一个自定义终端命令，用它启动我自己的 shell 工作流。
- 作为 Windows ttyd 用户，我希望普通 Windows PATH 中的命令可以直接启动，而依赖 Cygwin 的命令可以通过 Cygwin bash 包装启动。
- 作为有 alias 的用户，我希望可以把 `claude`、`mini-claude` 或 `ccl run m 3 -c` 这样的命令保存为自定义终端，并在创建 session 时直接选择。
- 作为用户，我希望自定义终端保存后，重启服务仍然存在。
- 作为用户，我希望系统级终端不会被误删，但可以隐藏不用。

## Acceptance criteria

- UI 中不再把终端选择/管理暴露为 `Runtime` 概念。
- 页面右上角工具条提供「终端管理」入口。
- 终端管理中展示系统级终端和用户自定义终端。
- 后端返回系统级终端列表，至少覆盖当前平台默认终端；Windows 下包含 PowerShell、cmd。
- 后端检测环境中可用的 Claude Code、Codex 等命令行工具，并展示为系统级终端候选。
- 系统级终端标记为不可删除。
- 用户可以新增、编辑、删除自定义终端配置。
- 用户可以隐藏/停用系统级终端或自定义终端。
- 用户自定义终端配置持久化，重启后仍可用于创建 session。
- 终端配置能表达名称、命令和是否启用/隐藏。
- 终端配置能表达启动方式：直接命令，或通过指定 shell/适配层执行。
- Windows ttyd 环境下，Windows PATH 可见命令可以直接启动；Cygwin 依赖命令可以配置为通过 Cygwin bash 启动。
- 创建 session 时仍可选择终端，也可使用自定义终端命令能力。
- 现有 session 列表、创建、删除、打开终端能力不回退。
- ttyd 配置默认按终端启动模式从对应环境 `PATH` 中查找 `ttyd`：direct 使用服务进程/Windows PATH，Cygwin 模式使用 Cygwin 环境 PATH；用户可在配置中指定明确的可执行文件路径，例如 `D:\ProgramFiles\Cygwin64\usr\local\bin\ttyd.exe`。

## Decisions

- 终端是用户可见概念；`runtime` 只允许作为内部兼容实现细节存在。
- 系统级终端不可删除，避免用户破坏基础入口。
- 自定义终端属于用户配置，必须持久化并可管理。
- alias/PATH/shell 初始化差异不由系统自动猜测；用户可以保存能在目标 shell 环境中执行的命令。
- Windows ttyd 接入自定义终端时，直接可执行命令和 Cygwin 依赖命令需要用不同启动方式表达。
- 对 Cygwin 依赖命令，推荐通过 Cygwin bash 适配层执行，并将用户输入的命令作为整段命令交给 Cygwin 环境，而不是拆分为 argv。
- Windows 进程启动 Cygwin bash 时应使用 Windows 可执行路径，例如 `D:\ProgramFiles\Cygwin64\bin\bash.exe`，不能直接使用 `/usr/bin/bash`。
- 进入指定 workspace 可以通过 Cygwin bash 执行 `cd D:/SourceCodes/agentic/cc-ttyd` 或 `cd $(cygpath -u <windows-path>)`；后续 Spec 需要明确最终命令模板。
- ttyd 默认查找由终端启动模式决定：direct 使用服务进程/Windows PATH，Cygwin 模式使用 Cygwin PATH；用户配置完整可执行文件路径时直接使用该路径。

## Open questions

- 系统级终端隐藏/停用状态是否也需要持久化？默认倾向需要，否则用户每次重启都会看到已隐藏项。
- Claude Code、Codex 的检测范围以 `PATH` 为准，还是需要额外检测 Cygwin 路径和 Windows 原生命令路径？
- 终端管理 UI 使用弹窗、页面级面板还是右侧抽屉？当前只确定入口位于右上角工具条。
- Windows ttyd 打开 Cygwin 后如何进入指定 workspace，需要在 Spec 中确定命令模板：使用 ttyd `--cwd`，还是在 Cygwin bash 内执行 `cd` 后再启动交互 shell/命令。

## Environment notes

- 当前环境 `ttyd` 位于 `/usr/local/bin/ttyd`，Windows 路径为 `D:\ProgramFiles\Cygwin64\usr\local\bin\ttyd.exe`。
- 当前环境 `bash` 位于 `/usr/bin/bash`，Windows 路径为 `D:\ProgramFiles\Cygwin64\bin\bash.exe`。
- Windows Python `shutil.which` 可解析 `ttyd`、`bash`、`claude`、`mini-claude`，但不能直接解析无 `.exe` 的 Cygwin 脚本 `ccl`。
- `ccl` 在 Cygwin bash 内可解析为 `/usr/local/bin/ccl`。
- Cygwin bash 可以 `cd "D:/SourceCodes/agentic/cc-ttyd"` 并进入 `/d/SourceCodes/agentic/cc-ttyd`。

## Risks

- 自动检测命令行工具时，不同 shell、PATH、alias 语义不同；例如 Cygwin bash 中的 alias 不一定能被普通可执行文件检测发现。
- 用户自定义终端如果依赖 alias 或 shell 初始化，需要保存为能在目标 shell 中执行的命令，例如显式通过 Cygwin bash 启动。
- 系统级终端不可删除，但隐藏/停用策略需要避免让用户失去恢复入口。
- 如果后端 API 从 `runtime` 彻底改名为 terminal，可能影响现有前端、测试和保存的 session 数据；严格模式后续 Spec 需要设计兼容边界。
- Windows 路径与 Cygwin 路径表达不同；进入指定 workspace 可能需要 `cygpath` 转换，否则 shell 内工作目录可能不符合预期。

## User review notes

- 用户明确要求从 light 切换到 strict，后续需要补 Spec、Plan、Implementation、Verification。
