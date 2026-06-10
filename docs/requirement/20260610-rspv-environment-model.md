# RSPV 环境模型调整需求

Review status: Accepted

当前：严格模式 / strict，规格阶段 / Spec

## Background

现有环境管理页把 Windows、Cygwin、WSL 作为三个并列运行环境展示；这会混淆宿主平台、目标平台和实际提供终端持久化能力的 runtime provider。

环境能力的核心不是“Windows / Cygwin / WSL 三个 tab”，而是“基于 tmux 提供会话持久化能力的目标环境”。在 TermBridge 当前设计中，Windows 本身是宿主平台；Cygwin 和 WSL 是 Windows 宿主上的 Linux-like provider；Linux 则是原生 Linux 宿主上的 provider。三类环境形态应为：

- Windows/Cygwin
- Windows/WSL
- Linux

当前运行环境是 Windows，因此 Linux 形态应被识别为不可用，不应表现为可配置的本机 Linux 环境。

`ttyd` 仍是独立运行时依赖，不属于某一个环境形态；每个可用环境形态都应基于 tmux 提供会话持久化能力。

## Goals

1. 环境管理页使用三类 tmux-backed 环境形态组织能力：
   - Windows/Cygwin
   - Windows/WSL
   - Linux
2. 系统应识别当前宿主平台，并据此判断环境形态可用性：
   - Windows 宿主：Windows/Cygwin、Windows/WSL 可检测；Linux 明确不可用。
   - Linux 宿主：Linux 可检测；Windows/Cygwin、Windows/WSL 明确不可用。
3. `ttyd` 作为独立配置区域：
   - 检查当前配置下 ttyd 是否就绪。
   - 展示检测到的 ttyd 路径和版本。
   - 当自动检测不到 ttyd 时，允许用户手动指定 ttyd 路径。
   - 用户指定路径后可再次检测，并展示可用性和版本。
4. Windows/Cygwin 环境检测：
   - 自动检测 Cygwin bash 是否就绪。
   - 自动检测无果时，允许用户手动指定 Cygwin bash path。
   - 手动指定的 Cygwin bash path 可保存并持久化，后续检测、终端启动和 tmux 检测优先使用该路径。
   - 在可用 Cygwin bash 下检测 tmux 是否就绪。
   - 展示 bash/tmux 的路径和版本；失败时展示原因。
5. Windows/WSL 环境检测：
   - 检测 WSL 是否可用。
   - 检测 WSL 内 tmux 是否可用。
   - 本阶段不保存或管理具体 distro，只使用默认 WSL 环境。
6. Linux 环境检测：
   - 本阶段不完整实现 Linux 宿主支持。
   - 在当前 Windows 宿主上展示 Linux 不可用原因。
7. 检测失败应以可理解状态展示，不应作为页面级崩溃。

## Non-goals

1. 不在本需求中实现自动安装 Cygwin、tmux、ttyd、WSL 或 Linux 依赖。
2. 不要求实现后台周期检测；页面打开和用户点击检测即可。
3. 不要求支持 Windows 原生 terminal 的 tmux/screen 持久化；Windows 本身不是独立环境形态。
4. 不要求本阶段管理 WSL distro 选择、安装或 distro-specific 配置。
5. 不要求本阶段完整实现 Linux 宿主支持；当前 Windows 宿主只需明确展示 Linux 不可用。
6. 不要求本阶段把 `screen` 纳入可配置 session persistence backend。
7. 不做旧 `ShortcutHost`、旧环境 API 或历史 terminal state 的向后兼容与迁移。
8. 不改变现有 session 创建、删除、restart 的用户语义。

## User scenarios

### 场景 1：查看 ttyd 当前状态

用户进入环境管理页，能看到独立的 ttyd 状态区域。系统按当前配置检测 ttyd，展示 available/unavailable、路径和版本。

### 场景 2：自动检测不到 ttyd，手动指定路径

当自动模式无法找到 ttyd，用户可以填写显式 ttyd path，点击检测后看到该路径是否可运行以及版本。保存后后续 session 使用该 ttyd 配置。

### 场景 3：查看 Windows/Cygwin 与 tmux 状态

用户进入 Windows/Cygwin 环境，页面自动检查 Cygwin bash 是否可运行；如果自动检测失败，用户可以输入 Cygwin bash path 并保存。保存后页面使用该路径继续检测 bash 和 tmux。页面展示 bash 路径/版本和 tmux 路径/版本；如果 tmux 不存在，展示 unavailable 和原因。

### 场景 4：查看 Windows/WSL 与 tmux 状态

用户进入 Windows/WSL 环境，页面检查 WSL 是否可运行，并检查 WSL 内 tmux 是否可用。页面展示 WSL 和 tmux 的可用状态；本阶段不要求选择或管理具体 distro。

### 场景 5：当前 Windows 宿主下查看 Linux 环境

用户在当前 Windows 宿主上查看 Linux 环境时，页面明确展示 Linux unavailable，并说明当前宿主不是 Linux。

## Acceptance criteria

1. 环境管理页有清晰的环境形态导航：Windows/Cygwin、Windows/WSL、Linux。
2. ttyd 配置作为环境形态导航外的独立区域显示。
3. ttyd 检测返回并展示：
   - 是否可用
   - path（可用时）
   - version（可用时）
   - reason（不可用时）
4. 用户可以保存显式 ttyd path；保存前或保存后可检测该路径；保存后后续 ttyd 启动优先使用该路径。
5. 当前 Windows 宿主下，Linux 环境展示为不可用，不触发本机 Linux tmux 配置流程。
6. Windows/Cygwin 环境打开时触发 Cygwin/tmux 检测，或提供明确检测按钮并在打开后自动执行一次。
7. Windows/Cygwin 检测展示：
   - Cygwin bash 是否可用、path、version/reason
   - tmux 是否可用、path、version/reason
8. 用户可以保存显式 Cygwin bash path；保存前或保存后可检测该路径；保存后后续 Windows/Cygwin 检测、tmux 检测和 session 启动优先使用该路径。
9. Windows/WSL 环境打开时触发默认 WSL/tmux 检测，或提供明确检测按钮并在打开后自动执行一次。
10. Windows/WSL 检测展示：
    - 默认 WSL 是否可用、version/reason
    - 默认 WSL 内 tmux 是否可用、path、version/reason
11. Windows/WSL 不展示或保存 distro 选择。
12. 后端检测失败返回正常响应（例如 `available=false`），不因未安装而返回 500。
13. 现有会话创建、删除、restart 流程不回退。
14. UI 和 API 语义不再把 Windows、Cygwin、WSL 表达为三个同层级独立环境。
15. 现有 `ShortcutHost` 语义需要重命名为 `windows_cygwin` / `windows_wsl` / `linux`。

## Open questions

1. `screen` 是否应和 `tmux` 一样成为可选 session persistence backend？
   - 待决策：`screen` 理论上可以成为类似 tmux 的 host/session persistence 方案，但如果本阶段引入，会把模型扩展为“环境形态 × persistence backend”。
2. ttyd 自动检测范围：
   - 已决策：系统先自动检测 PATH 中的 `ttyd`；检测失败或用户需要覆盖时，允许用户手动指定路径并持久化，后续优先使用该路径。

## Decisions

1. 环境形态采用 Windows/Cygwin、Windows/WSL、Linux 三类，而不是 Windows、Cygwin、WSL 三个并列项。
2. 三类环境形态都以 tmux-backed session persistence 为核心能力。
3. 当前 Windows 宿主下，Linux 环境明确不可用。
4. Linux 宿主支持本阶段不完整实现，只保留模型表达和 Windows 宿主下的 unavailable 状态。
5. Windows 本身是宿主平台，不作为独立 tmux 环境形态。
6. `ShortcutHost` 需要立即重命名为 `windows_cygwin` / `windows_wsl` / `linux`，使代码模型与环境形态一致。
7. `ttyd` 使用“自动检测优先、失败后允许手动指定”的策略。手动指定路径需要持久化，后续 session 启动优先使用该路径。
8. Windows/Cygwin 使用“自动检测 Cygwin bash 优先、失败后允许手动指定”的策略。手动指定路径需要持久化，后续检测、tmux 检测和 session 启动优先使用该路径。
9. Windows/WSL 本阶段只检测默认 WSL 与其中的 tmux，不保存或管理具体 distro。
10. 不做向后兼容和迁移；旧 `cygwin_tmux`、旧环境 API 和旧 terminal state 可在本阶段破坏。

## User review notes

- 2026-06-10：用户指出当前不应区分 Cygwin、WSL、Windows 三个并列环境，而应建模为 Windows/Cygwin、Windows/WSL、Linux 三种形式；它们均基于 tmux 提供环境能力。当前是 Windows 环境，所以 Linux 肯定不可用。
- 2026-06-10：用户确认 Windows/WSL 不需要保存 WSL distro 名称；Linux 宿主支持本阶段不完整实现；现有 `ShortcutHost` 需要立即重命名为 `windows_cygwin` / `windows_wsl` / `linux`。
- 2026-06-10：用户要求把 `screen` 是否能成为类似 tmux 的 host/session persistence 方案作为 open question 记录。
- 2026-06-10：用户确认不做向后兼容和迁移。
