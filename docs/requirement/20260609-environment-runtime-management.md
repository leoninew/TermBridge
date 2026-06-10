# 环境运行时管理需求

Review status: Accepted

当前：严格模式 / strict，计划 / Plan

## Background

现有环境管理页只提供占位卡片和 ttyd settings 表单；终端管理页承担了 terminal definition 管理。随着 Cygwin + tmux 会话持久化能力引入，环境管理需要成为运行时能力检测和基础配置入口。

用户希望环境管理按运行环境分区：Windows 原生模式、Cygwin 模式、WSL 模式。`ttyd` 不属于某个模式，而是独立运行时依赖；`tmux` 来自 Cygwin，是 Cygwin 专属能力。

## Goals

1. 环境管理页使用 tab 页分开读取和管理：
   - Windows 原生模式
   - Cygwin 模式
   - WSL 模式
2. `ttyd` 作为独立配置区域：
   - 检查当前配置下 ttyd 是否就绪。
   - 展示检测到的 ttyd 路径和版本。
   - 当自动检测不到 ttyd 时，允许用户手动指定 ttyd 路径。
   - 用户指定路径后可再次检测，并展示可用性和版本。
3. Cygwin tab 打开后检查 Cygwin 相关能力：
   - 自动检测 Cygwin bash 是否就绪。
   - 自动检测无果时，允许用户手动指定 Cygwin bash path。
   - 手动指定的 Cygwin bash path 可保存并持久化，后续检测、终端启动和 tmux 检测优先使用该路径。
   - 在可用 Cygwin bash 下检测 tmux 是否就绪。
   - 展示 bash/tmux 的路径和版本；失败时展示原因。
4. Cygwin 的 tmux 配置只出现在 Cygwin tab，不出现在 Windows 或 WSL tab。
5. 检测失败应以可理解状态展示，不应作为页面级崩溃。

## Non-goals

1. 不在本需求中实现完整 Windows/WSL 终端定义管理；terminal definitions 仍由终端管理页负责。
2. 不要求自动安装 Cygwin、tmux、ttyd 或 WSL。
3. 不要求实现后台周期检测；页面打开和用户点击检测即可。
4. 不要求支持 Windows 原生 terminal 的 tmux/screen 持久化。
5. 不改变现有 session 创建、删除、restart 语义。

## User scenarios

### 场景 1：查看 ttyd 当前状态

用户进入环境管理页，能看到独立的 ttyd 状态区域。系统按当前配置检测 ttyd，展示 available/unavailable、路径和版本。

### 场景 2：自动检测不到 ttyd，手动指定路径

当自动模式无法找到 ttyd，用户可以填写显式 ttyd path，点击检测后看到该路径是否可运行以及版本。保存后后续 session 使用该 ttyd 配置。

### 场景 3：查看 Cygwin 与 tmux 状态

用户进入 Cygwin tab，页面自动检查 Cygwin bash 是否可运行；如果自动检测失败，用户可以输入 Cygwin bash path 并保存。保存后页面使用该路径继续检测 bash 和 tmux。页面展示 bash 路径/版本和 tmux 路径/版本；如果 tmux 不存在，展示 unavailable 和原因。

### 场景 4：Windows / WSL tab 基础分区

用户能在环境管理页切换 Windows、Cygwin、WSL tab。Windows/WSL tab 至少展示当前模式说明和检测状态占位，不与 Cygwin tmux 配置混在一起。

## Acceptance criteria

1. 环境管理页有清晰的 tab 导航：Windows、Cygwin、WSL。
2. ttyd 配置作为 tab 外的独立区域显示。
3. ttyd 检测返回并展示：
   - 是否可用
   - path（可用时）
   - version（可用时）
   - reason（不可用时）
4. 用户可以保存显式 ttyd path；保存前或保存后可检测该路径；保存后后续 ttyd 启动优先使用该路径。
5. Cygwin tab 打开时触发 Cygwin/tmux 检测，或提供明确检测按钮并在打开后自动执行一次。
6. Cygwin 检测展示：
   - bash 是否可用、path、version/reason
   - tmux 是否可用、path、version/reason
7. 用户可以保存显式 Cygwin bash path；保存前或保存后可检测该路径；保存后后续 Cygwin/tmux 检测和 Cygwin terminal 启动优先使用该路径。
8. tmux 检测只在 Cygwin tab 中出现。
9. 后端检测失败返回正常响应（例如 `available=false`），不因未安装而返回 500。
10. 现有 `/terminals` 终端管理能力不回退。
11. 现有会话创建、删除、restart 流程不回退。

## Open questions

1. Cygwin bash path 的来源：
   - 已决策：系统先自动检测 Cygwin bash；检测失败或用户需要覆盖时，允许用户手动指定路径并持久化，后续优先使用该路径。
2. WSL 检测深度：
   - 已决策：本需求先检测 `wsl --status` 或 `wsl --version` 是否可运行，展示基础可用性；不管理具体 distro。
3. Windows 原生检测深度：
   - 已决策：本需求先展示 Windows host 基础可用性和 shell 候选状态；不做复杂配置。
4. ttyd 自动检测范围：
   - 已决策：系统先自动检测 PATH 中的 `ttyd`；检测失败或用户需要覆盖时，允许用户手动指定路径并持久化，后续优先使用该路径。

## Decisions

1. `ttyd` 使用“自动检测优先、失败后允许手动指定”的策略。手动指定路径需要持久化，后续 session 启动优先使用该路径。
2. Cygwin bash 使用“自动检测优先、失败后允许手动指定”的策略。手动指定路径需要持久化，后续 Cygwin 检测、tmux 检测和 Cygwin terminal 启动优先使用该路径。
3. tmux 是 Cygwin 专属能力，只在 Cygwin tab 内检测和展示。
4. WSL 本阶段只做基础可用性检测，不管理具体 distro。
5. Windows 本阶段只展示 host 基础可用性和 shell 候选状态，不做复杂配置。

## User review notes

待补充。
