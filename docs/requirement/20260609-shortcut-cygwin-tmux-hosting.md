# 快捷方式 Cygwin tmux 托管需求

Review status: Accepted

当前：严格模式 / strict，规格 / Spec

## Background

现有功能已经整理了 `ttyd`、`tmux`、Cygwin 的运行时检测和基础配置边界：`ttyd` 是 Web terminal 承载进程，Cygwin bash 是 Cygwin host 的入口，`tmux` 是 Cygwin 专属的持久化能力。

在这个基础上，原先“终端 / terminal”这个概念需要跟上进度。它不应继续被理解为 runtime 本身，或者单纯的 shell command 配置；更合适的定义是“快捷方式 / shortcut”：用户点击后，在某个 host 环境中启动一个入口命令。

第一阶段先聚焦 Cygwin + tmux 模式：把 `claude --dangerously-skip-permissions`、`codex -a never --sandbox danger-full-access` 等 agent CLI 入口作为快捷方式托管起来。`cmd`、`python`、普通 shell 等入口可以后续再扩展。

## Goals

1. 将产品概念从“终端定义 / terminal definition”调整为“快捷方式 / shortcut”。
2. 明确 shortcut 是入口配置，不是 runtime host：
   - 每个 shortcut 必须绑定 Windows、Cygwin、WSL 之一作为 host 环境。
   - host 负责在哪里运行以及有哪些启动依赖。
   - shortcut 负责运行什么命令。
3. 第一阶段只要求支持 `cygwin_tmux` host：
   - Cygwin bash path 来自环境配置。
   - tmux 负责会话持久化。
   - ttyd 负责 Web terminal 承载和 attach。
4. 支持创建、查看、编辑、删除 shortcut。
5. 支持用 shortcut 创建 session：
   - 选择 shortcut。
   - 后端创建或复用 Cygwin tmux session。
   - tmux session 内启动 shortcut command。
   - ttyd attach 到该 tmux session。
6. 默认提供 Claude Code 和 Codex 两个 shortcut：
   - Claude Code：`claude --dangerously-skip-permissions`
   - Codex：`codex -a never --sandbox danger-full-access`
7. 保留已有 Cygwin/tmux/ttyd 环境检测能力，并在 shortcut 创建或启动前复用这些能力做校验。
8. UI 文案和结构中替换为“快捷方式”术语，移除原“终端”作为入口配置的描述。

## Non-goals

1. 本阶段不实现 Windows host shortcut。
2. 本阶段不实现 WSL host shortcut。
3. 本阶段不优先处理 `cmd`、`python`、普通 shell 等泛用入口。
4. 本阶段不实现复杂 env 管理、secret 管理或 profile 继承。
5. 本阶段不实现多种 persistence backend；只聚焦 Cygwin + tmux。
6. 本阶段不实现 system/user shortcut 类别，也不控制默认 shortcut 是否可修改或删除。
7. 本阶段不改变 ttyd 作为全局承载进程配置的定位。
8. 本阶段不要求自动安装或修复 Cygwin、tmux、ttyd、Claude Code、Codex。

## User scenarios

### 场景 1：查看快捷方式列表

用户进入快捷方式管理页，可以看到 Claude Code、Codex 等入口。每个快捷方式展示名称、命令、host 类型和说明。

### 场景 2：创建 Claude Code 快捷方式

用户创建一个快捷方式，名称为 Claude Code，命令为 `claude --dangerously-skip-permissions`，host 为 `cygwin_tmux`。保存后它出现在快捷方式列表中。

### 场景 3：通过快捷方式启动持久会话

用户点击 Claude Code 快捷方式创建 session。系统使用当前 Cygwin bash path 创建 tmux session，在 tmux 中启动 `claude --dangerously-skip-permissions`，然后用 ttyd attach 到该 tmux session。

### 场景 4：刷新页面后恢复会话

用户刷新页面或重新进入应用，已启动的 shortcut session 仍可以通过 ttyd/tmux attach 回到原 tmux session。

### 场景 5：绑定环境不可用时阻止启动

每个 shortcut 必须绑定 Windows、Cygwin、WSL 之一作为 host 环境。用户点击 shortcut 时，系统按该 shortcut 绑定的 host 环境判断配置是否就绪；如果对应 host 配置未就绪，用户看到明确错误或不可用状态，而不是创建失败的空白 session。启动前不要求额外检查进程和版本。

## Acceptance criteria

1. 数据模型或 API 语义中有明确 shortcut 概念，用于表达“入口命令配置”。
2. Shortcut 至少包含：
   - id
   - name
   - command
   - host type，第一阶段支持 `cygwin_tmux`
   - description 可选
   - icon 可选
3. 第一阶段 shortcut host 只实现 `cygwin_tmux`。
4. Cygwin bash path 不在每个 shortcut 中重复配置，而是来自环境设置。
5. ttyd path 不在每个 shortcut 中重复配置，而是来自全局 terminal settings / environment settings。
6. 使用 shortcut 创建 session 时，后端能创建 tmux session 并在其中启动 shortcut command。
7. 使用 shortcut 创建 session 后，ttyd attach 到对应 tmux session。
8. session 记录能保留 shortcut 来源或等价信息，便于列表展示和恢复。
9. Shortcut 必须绑定 Windows、Cygwin、WSL 之一；启动前只检查绑定 host 环境的配置是否就绪，不要求检查进程和版本；配置未就绪时给出可理解错误，不应静默失败。
10. 默认提供 Claude Code shortcut，命令为 `claude --dangerously-skip-permissions`。
11. 默认提供 Codex shortcut，命令为 `codex -a never --sandbox danger-full-access`。
12. 本阶段不区分 system/user shortcut 类别，也不限制默认 shortcut 的修改或删除。
13. 模型、API 和前端主要命名一次性迁移为 shortcut 语义，移除旧的 `TerminalDefinition` 作为入口配置的命名。
14. UI 中统一使用“快捷方式”作为入口配置概念，移除旧的“终端定义”文案和结构描述。
15. 新建会话时用户选择 shortcut + workspace，shortcut 本身不内置固定工作目录。
16. 现有环境管理页继续负责 Cygwin/tmux/ttyd 检测和路径配置。
17. 不破坏已有 session 创建、删除、restart、tmux persistence 的基本能力。

## Open questions

无。

## Decisions

1. 底层代码命名一次性从 `TerminalDefinition` 迁移为 shortcut 语义，包括模型、API 和前端主要命名。
2. Shortcut command 允许任意非空白字符串；本阶段不限制命令内容。
3. Shortcut 表达“如何启动”，不内置固定工作目录；新建会话时由用户选择 shortcut + workspace。
4. 默认提供 Claude Code shortcut，命令为 `claude --dangerously-skip-permissions`。
5. 默认提供 Codex shortcut，命令为 `codex -a never --sandbox danger-full-access`。
6. Shortcut session 需要存储和 tmux 相关的信息。tmux session 可以用会话名指代；会话名需要符合规范，方便切换应用会话时切换到对应 tmux session。
7. 已有 terminal definitions 数据不迁移，直接删除旧数据并以 shortcuts 重新开始。

## User review notes

- Codex 的入口命令应使用 `codex -a never --sandbox danger-full-access`。
- UI 文案和结构应替换为“快捷方式”术语，移除原“终端”作为入口配置的描述。
- Claude Code 和 Codex 应作为系统预置快捷方式提供。
- 每个快捷方式都必须绑定 Windows、Cygwin、WSL 之一；能否启动取决于绑定 host 环境配置是否就绪。
- 启动前检查只需要确认绑定 host 配置就绪，不要求额外检查进程和版本。
- Claude Code 和 Codex 是默认提供的快捷方式；本阶段不实现 system/user 类别，也不控制能否修改或删除。
- 底层 `TerminalDefinition` 命名一次性迁移为 shortcut 语义。
- Shortcut command 只要求非空白，不限制命令内容。
- Shortcut 表达如何启动；新建会话时选择 shortcut + workspace。
- Shortcut session 需要存储 tmux 相关信息，可用规范化会话名指代 tmux session。
- 已有 terminal definitions 数据直接删除，不做迁移。
