# Windows/WSL 运行环境支持需求

Review status: Accepted

当前：严格模式 / strict，规格阶段 / Spec

## Background

TermBridge 已经把运行环境模型整理为三类 tmux-backed provider：Windows/Cygwin、Windows/WSL、Linux。当前代码中 Windows/WSL 已有环境检测能力，可以检查 WSL 和 WSL 内 tmux 是否可用，但 session 启动仍只支持 Windows/Cygwin，用户也无法在配置项或 shortcut 创建中真正选择 Windows/WSL 作为运行环境。

下一步需要把 Windows/WSL 从“检测可见”推进到“可配置、可选择、可启动”。用户需要能在配置项中选择运行环境，并让创建 session 时基于该运行环境启动对应的 tmux-backed terminal。

## Goals

1. 支持用户在配置项中切换运行环境：
   - Windows/Cygwin
   - Windows/WSL
   - Linux
2. Windows/WSL 不再只是环境检测项，而应能作为 session/shortcut 的运行环境。
3. Windows 宿主上选择 Windows/WSL 后，session 启动应通过默认 WSL 环境运行用户命令，并使用 WSL 内 tmux 提供会话持久化。
4. 保持 Windows/Cygwin 现有启动、删除、restart 行为不回退。
5. 配置项中的运行环境选择应影响默认 shortcut 创建、session 创建或运行环境选择体验，避免用户只能在底层 host 字段中手动理解运行环境。
6. Windows/WSL 的环境检测失败应阻止启动并返回清晰错误，而不是产生不可理解的 ttyd/tmux 失败。
7. Windows/WSL 下 workspace 路径应能转换为 WSL 可访问路径，支持常见 Windows 盘符路径。
8. 删除或停止 session 时，应能清理对应 WSL tmux session，避免 orphan tmux session 残留。
9. Windows/WSL 检测应扩展为可供后续启动使用的能力探测，并在需要时持久化检测到的稳定信息，例如默认 distro、WSL 版本、automount root、tmux path、shell path 或最近一次检测结果。
10. Windows/Cygwin、Windows/WSL、Linux 三类运行环境配置都应有明确的 readiness 状态；默认不是就绪状态，必须通过检测或有效配置后才变为就绪。
11. 主页默认进入会话界面时，应先读取环境列表和 readiness 状态；如果没有任何可用环境，应展示跳转环境配置页的引导，让用户去检测或手动填写 ttyd、Cygwin bash 等路径。

## Non-goals

1. 不在本需求中实现 WSL 安装、distro 安装、tmux 安装或自动修复。
2. 不要求本阶段支持选择具体 WSL distro；继续使用默认 WSL 环境。
3. 不把 Linux 作为本阶段的特殊禁用对象；Linux 是否可用由其检测结果和 readiness 统一决定。
4. 不要求支持 Windows 原生 terminal 的非 tmux 持久化。
5. 不引入 `screen` 作为新的 session persistence fastapi。
6. 不做旧 terminal state 或旧 host 值的向后兼容迁移。
7. 不要求把 ttyd 本身移动到 WSL 内运行；本阶段优先考虑 Windows 进程中的 ttyd 调用 `wsl.exe` 启动运行命令。

## User scenarios

### 场景 1：用户首次进入会话主页但没有可用环境

用户打开 TermBridge 后默认进入会话界面。系统先读取 Windows/Cygwin、Windows/WSL、Linux 的环境列表和 readiness 状态。如果三类环境都未就绪，主界面不应直接展示无法使用的创建会话入口，而应展示空状态提示，并提供跳转环境配置页的链接。用户可以跳转后执行检测，或手动填写 ttyd path、Cygwin bash path 等必要路径。

### 场景 2：用户在配置项中切换默认运行环境

用户进入环境/终端配置页面，可以看到当前默认运行环境。用户选择 Windows/WSL 后，系统保存该选择。后续创建 shortcut 或 session 时，默认使用 Windows/WSL，除非用户在具体 shortcut 中另行选择。

### 场景 3：用户创建 Windows/WSL shortcut

用户在 shortcut 管理页面创建 shortcut，运行环境选择 Windows/WSL，填写命令如 `bash`、`claude` 或 `codex`。保存后 shortcut 列表应正确展示其运行环境为 Windows/WSL。

### 场景 4：用户启动 Windows/WSL session

用户选择一个 Windows/WSL shortcut 并指定 workspace。系统先确认 Windows/WSL 与 tmux 可用，然后通过默认 WSL 环境进入 workspace，创建或附加 tmux session，并通过 ttyd 暴露到浏览器。

### 场景 5：WSL 或 tmux 不可用

用户选择 Windows/WSL shortcut 启动 session，但当前机器未安装 WSL、默认 WSL 不可用，或 WSL 内未安装 tmux。系统应返回明确错误，提示 WSL/tmux 不可用，而不是留下 failed session 或显示底层命令异常。

### 场景 6：workspace 路径需要转换

用户从 Windows 文件系统选择 workspace，例如 `D:\Projects\TermBridge`。启动 Windows/WSL session 时，系统应将其转换成 WSL 可访问路径，例如 `/mnt/d/Projects/TermBridge`，并在 WSL 内执行 `cd`。

### 场景 7：删除 Windows/WSL session

用户删除一个 Windows/WSL session 时，系统应终止 ttyd 进程，并在默认 WSL 环境中 kill 对应 tmux session。

### 场景 8：检测 Windows/WSL 并复用检测信息

用户在环境配置页检测 Windows/WSL。系统不仅展示 WSL 和 tmux 是否可用，还记录后续启动可能需要的信息，例如默认 distro、WSL 版本、automount root、tmux path、shell path、最近一次检测时间和失败原因。后续启动 Windows/WSL session 时，可以优先使用这些检测信息进行路径转换、可用性判断和错误提示。

### 场景 9：环境全部检查通过后标记为就绪

用户在环境配置页对某个环境执行完整检查。检查项全部通过后，系统将该环境标记为 ready，并持久化 readiness。下次用户进入会话主页时，系统直接读取 readiness 状态并允许使用该环境，不需要自动重新检测。用户仍可在环境配置页手动重新检测，以刷新 readiness 和检测快照。

## Acceptance criteria

1. 配置项中存在默认运行环境选择，包含 Windows/Cygwin、Windows/WSL、Linux；是否可用统一由检测结果和 readiness 决定。
2. Windows/Cygwin、Windows/WSL、Linux 都有 readiness 字段；新环境默认为 not ready。
3. 环境配置页对某个环境执行完整检查且全部通过后，该环境被标记为 ready 并持久化。
4. 用户下次进入会话主页时，系统直接读取持久化 readiness；已有 ready 环境时无需自动重新检测即可使用。
5. 如果没有任何 ready 环境，会话主页展示空状态和跳转环境配置页的链接，引导用户检测或手填 ttyd、Cygwin bash 等路径。
6. 用户仍可在环境配置页手动重新检测，重新检测结果会刷新 readiness 和检测快照。
7. 默认运行环境选择可持久化，并在重新打开页面后保持。
8. 创建 shortcut 时可选择 Windows/WSL；默认值应跟随配置项中的默认运行环境。
9. Session 创建表单展示所有 host：Windows/Cygwin、Windows/WSL、Linux；未 ready 或当前宿主不可用的 host 以 disabled 状态展示，不隐藏。
10. shortcut 列表和编辑表单能正确展示 Windows/Cygwin、Windows/WSL、Linux 的 label，不再硬编码为 Windows/Cygwin。
11. 后端允许 `windows_wsl` shortcut 进入 session 创建流程，不再直接以 unsupported host 拒绝。
12. Windows/WSL session 启动前会根据持久化 readiness 和必要运行信息判断是否可启动；如果启动失败，返回明确错误并引导用户重新检测环境。
13. Windows/WSL session 的启动命令在默认 WSL 环境内执行用户 shortcut command，并使用 tmux `new-session -A` 提供持久化。
14. Windows 路径 workspace 会转换为 WSL 可访问路径，并正确处理路径中的空格。
15. Windows/WSL 检测会收集并展示后续启动有用的信息，至少包括 WSL 是否可用、WSL version/reason、tmux 是否可用、tmux path/version/reason。
16. Windows/WSL 检测可扩展保存稳定信息或最近一次检测快照，供后续路径转换、启动前判断和诊断使用。
17. session record 能记录足够信息用于 restart 和 delete，包括 host、tmux session name，以及 WSL cleanup 所需上下文。
18. 删除 Windows/WSL session 时会在 WSL 中清理对应 tmux session。
19. restart Windows/WSL session 时能重新启动 ttyd 并附加到同一个 WSL tmux session。
20. Windows/Cygwin 现有 session 创建、删除、restart 流程不回退。
21. API、前端类型和 UI 文案都使用同一组运行环境语义：Windows/Cygwin、Windows/WSL、Linux。
22. README 或相关文档更新支持矩阵，明确 Windows/WSL 已支持默认 WSL 环境启动，三类运行环境都使用 readiness 判断可用性。
23. 前端在加载环境列表、执行检测、保存配置、加载 shortcut 和创建 session 时提供必要 loading/spinner 反馈，并防止重复提交。
24. 相关测试覆盖：
    - Windows/WSL 环境可用时的启动命令构造
    - WSL 不可用时的错误
    - WSL 内 tmux 不可用时的错误
    - workspace 路径转换
    - WSL session delete/restart
    - Windows/Cygwin 回归路径

## Open questions

1. 默认运行环境选择应该保存在哪里？
   - 候选：扩展 `TerminalSettings`，增加类似 `default_host` / `default_runtime_host` 字段。
   - 候选：只保存在 shortcut 创建表单本地状态，不作为全局配置。
   - 倾向：保存到后端 `TerminalSettings`，因为用户明确希望配置项支持切换运行环境。
2. Windows/WSL 启动时是否需要允许用户配置 `wsl.exe` 路径？
   - 倾向：本阶段不配置，使用 PATH 中的 `wsl`。
3. 是否要在本阶段暴露 WSL distro 选择？
   - 已有环境模型阶段决策：不管理具体 distro，使用默认 WSL。
4. workspace 路径转换是否需要动态分析挂载配置？
   - 当前常见路径形态是 `/mnt/<drive>/...`，但 WSL 的 automount root 理论上可通过 `/etc/wsl.conf` 配置改变。
   - 候选：调用 `wsl wslpath -a <windows_path>`，由 WSL 自己返回当前配置下的实际 Linux 路径。
   - 候选：读取或执行命令分析 WSL 配置，例如读取 `/etc/wsl.conf` 的 automount root，再自行转换。
   - 候选：直接按 `/mnt/<drive>/...` 做 deterministic 转换。
   - 倾向：优先调用 `wsl wslpath -a <windows_path>`；它能利用当前 WSL 环境的真实配置，避免 TermBridge 自己复刻 WSL 路径规则。只有当 `wslpath` 不可用或失败时，才考虑是否需要 fallback 到 `/mnt/<drive>/...`。
5. ttyd 的 `--cwd` 和 `wsl --cd` 如何配合？
   - Windows 原生 ttyd 的 `--cwd` 只能作用于 Windows 侧 ttyd 进程工作目录。
   - WSL 支持 `wsl --cd <目录>`，可以在进入 WSL 时指定 Linux 侧工作目录。
   - 倾向：Windows/WSL session 使用 Windows 原生 ttyd 启动 `wsl --cd <wsl_workspace> sh -lc ...`，并在 WSL 内再执行 tmux command；是否继续传 Windows `--cwd` 给 ttyd 留到 plan 阶段验证。
6. Windows/WSL 检测结果哪些应该持久化？
   - 候选：只持久化用户配置，例如默认运行环境；检测结果每次按需实时执行。
   - 候选：持久化最近一次检测快照，例如 WSL version、default distro、tmux path/version、automount root、checked_at、reason。
   - 候选：只持久化稳定信息，例如 automount root 和 default distro，运行态可用性仍实时检测。
   - 倾向：保存“配置 + 最近一次检测快照”，用于 UI 展示、启动诊断和路径转换提示；完整检测通过后标记 ready，后续进入主页不自动重检。启动失败时再提示用户回到环境配置页重新检测。

## Decisions

1. 本需求按标准模式 / standard 推进：Requirement -> Plan -> Implementation -> Verification。
2. Windows/WSL 本阶段使用默认 WSL 环境，不做 distro 管理。
3. Linux 不作为特殊禁用对象；若 Linux 检测通过并标记 ready，则按同一 tmux-backed provider 语义参与启动。
4. Windows/WSL session 使用 Windows 原生 ttyd；TermBridge 后端仍运行在 Windows，ttyd 的 command 进入 `wsl.exe sh -lc ...` 或 `wsl --cd <wsl_workspace> sh -lc ...`。
5. 不在本阶段使用 WSL 内 Linux 版 ttyd。未选理由：这会让 Windows 后端跨边界管理 WSL 内 ttyd 的端口、PID、健康检查和 URL 生成，复杂度明显高于只把 WSL 作为 command provider。
6. 不把 TermBridge 整体移动到 WSL 内运行。未选理由：这会变成 Linux host 支持问题，需要同时改变宿主平台、路径模型、依赖安装和网络访问模型，不适合作为 Windows/WSL provider 支持的一部分。
7. 配置项需要增加运行环境切换选项，支持用户切换默认运行环境。
8. Windows/WSL 检测应增强为可复用的能力探测；计划阶段需要明确持久化字段边界。
9. 每个运行环境都有 readiness 状态，默认 not ready；完整检查全部通过后标记 ready 并持久化。主页优先读取 readiness，不对 ready 环境自动重复检测。
10. 会话主页没有任何 ready 环境时，应展示跳转环境配置页的引导，而不是让用户直接进入不可用的创建会话流程。
11. 删除全局 `Settings.use_wsl` / `TERMBRIDGE_USE_WSL` 语义；WSL 启动必须由 shortcut/provider host 显式决定。

## User review notes

- 2026-06-10：用户要求按标准模式开始需求，组织 Windows/WSL 环境支持，并特别指出配置项也要添加选项，支持用户切换运行环境。
- 2026-06-10：用户补充 Windows/Cygwin、Windows/WSL、Linux 都应有 readiness 字段，默认 not ready；环境完整检查通过后标记 ready 并持久化，下次进入会话主页直接使用，不自动重复检测；若没有任何 ready 环境，主页应引导用户跳转环境配置页检测或手填 ttyd、Cygwin bash 等路径。
