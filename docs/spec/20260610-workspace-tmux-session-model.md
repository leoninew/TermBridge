# 工作区中心的 tmux 会话模型规格

Review status: Accepted

当前：严格模式 / strict，规格阶段 / Spec

## Requirement basis

基于 `docs/requirement/20260610-workspace-tmux-session-model.md`，Requirement 已接受。核心要求是将 TermBridge 从“用户命名的 flat session list”调整为“运行环境 + 工作目录”的工作区模型：

1. 用户填写的显示名不能再作为 tmux session 的唯一身份来源。
2. `运行环境 + 工作目录` 是工作区身份，并对应一个工作区级 tmux session。
3. 工作区下的 TermBridge 会话入口对应该 tmux session 内的 managed tmux window。
4. 左侧导航按 `环境 -> 目录工作区 -> 会话入口` 树型展示。
5. 删除、停止、重启、重新连接必须区分 TermBridge record、ttyd 进程、tmux window 和 tmux session。
6. 后续设计不再假设“用户输入会话名 = tmux session name”。

## Overview

当前模型近似为：

```text
SessionRecord
└── ttyd process
    └── runtime shell
        └── tmux new-session -A -s <normalized user name> <shortcut command>
```

问题是 tmux session 身份来自用户显示名，导致相同环境下不同目录使用同名时会 attach 到同一个 tmux session。

新模型调整为：

```text
Environment
└── Workspace = environment + workspace path
    └── tmux session
        └── managed session entry = tmux window
            └── shortcut command
```

TermBridge 顶层管理对象不再是一条孤立 session，而是一个目录工作区。用户看到的第三级“会话”是工作区内的运行入口；技术上它对应一个由 TermBridge 创建和追踪的 tmux window。

## Design decisions

### 1. Workspace identity

工作区身份由 `运行环境 + 工作目录` 派生，而不是由用户显示名派生。

语义：

- 同一 host + 同一规范化 workspace path 视为同一个 workspace。
- 不同 host 即使 workspace 文本相同，也视为不同 workspace。
- 不同 workspace 即使显示名相同，也必须映射到不同 tmux session。

路径规范化应在每个 host 的边界内完成：

- Windows/Cygwin：保留 Windows 路径作为用户可见路径，tmux 命令内可继续使用 Cygwin 可接受的 forward-slash 表达。
- Windows/WSL：用户意图是 Windows 后端调用 `wsl --cd <Windows path>`，workspace identity 不应依赖 `wslpath` 预转换。
- Linux：使用 Linux 原生路径语义。

### 2. Workspace tmux session name

工作区级 tmux session name 由系统生成或由稳定 workspace identity 派生，不能只使用用户显示名。

要求：

- tmux session name 必须跨同一 host 的不同目录稳定区分。
- 名称应只包含 tmux 和 shell 命令中安全的字符。
- 同一 host + workspace 再次打开时应复用同一个 tmux session name。
- 用户显示名、目录名、快捷方式名只作为 UI 元数据或 alias，不作为唯一身份。

推荐方向：使用固定前缀加 workspace identity hash，例如 `tb_<host>_<hash>`。具体 hash 输入和字段落地留到 Plan 阶段细化。

### 3. Session entry maps to managed tmux window

第三级 TermBridge 会话入口映射为工作区 tmux session 内的 managed tmux window。

创建入口时：

1. 确保 workspace tmux session 存在。
2. 在该 tmux session 内创建一个 window 运行所选 shortcut command。
3. 记录该 window 的稳定身份。
4. 通过 ttyd attach 到该 tmux session，并切换到目标 window。

window 身份应优先使用 tmux window id，例如 `@3`，而不是 window index。window index 可因用户重排、关闭、移动而变化，不适合作为持久引用。tmux window id/current window name 仅作为内部诊断信息，不在 UI 中显式展示。

### 4. Attach and reconnect behavior

点击第三级会话入口时按状态分支：

1. ttyd process 活着，managed window 存在：展示当前连接，必要时切换到目标 window。
2. ttyd process 不存在，managed window 仍存在：创建新的 ttyd process，attach 到 workspace tmux session 并切到目标 window。
3. managed window 不存在，workspace tmux session 存在：将 entry 视为 stopped/invalid；用户执行重启时创建新的 managed window。
4. workspace tmux session 不存在：将 workspace 与其 entries 视为 stopped/invalid；用户执行重启时先重建 workspace tmux session，再创建目标 window。
5. workspace path 不存在或环境未 ready：禁止启动/重连，并返回用户可理解错误。

该语义把 “重新连接 ttyd” 和 “重新启动 shortcut command” 区分开。

### 5. Stop and delete semantics

生命周期分层：

```text
TermBridge record       管理记录和 UI 可见条目
managed tmux window     第三级入口对应的 tmux 执行状态
tmux session            工作区级持久状态边界
ttyd process            浏览器访问终端的连接进程
```

推荐操作语义：

- Close connection：只停止 ttyd process，不 kill managed window，也不删除记录。
- Stop entry：关闭该 entry 对应的 managed tmux window，保留 TermBridge record 并标记为 stopped。
- Delete entry：从 TermBridge 中移除该 entry；如果 managed window 仍存在，应同时关闭该 managed window，避免孤儿 managed state。
- Delete workspace：删除工作区记录及其所有 managed entries；如果没有保留状态的需求，则 kill workspace tmux session。
- Kill workspace tmux session：只在工作区下已无需要保留的 managed entry/window，或用户明确选择终止工作区状态时执行。

本阶段不暴露“只移除 TermBridge record 但保留 managed tmux window”的默认高级操作。停止会话的语义是保留记录、移除对应 window；再次启动时按记录重新创建 window。

### 6. Manual tmux operation tolerance

TermBridge 只管理自己创建的 tmux windows。用户手工操作 tmux 时：

- Rename managed window：保持同一 entry 映射；UI 可显示 shortcut 元数据，并可附带当前 tmux window name。
- Move/reorder window：不影响映射，因为不依赖 window index。
- Close managed window：entry 进入 stopped/invalid 状态。
- Create manual window：不自动导入为 TermBridge entry。
- Kill tmux session：workspace 与其 entries 进入 stopped/invalid 状态。

这要求后端在 attach/reconnect/restart 前能检查 tmux session/window 是否仍存在。

### 7. Navigation and search model

左侧导航采用树型结构：

```text
Environment
└── Workspace directory
    └── Session entry / Shortcut run
```

前端可参考 `docs/guides/llms.txt` 中的 Reka UI `Tree` 组件说明：树视图用于显示可展开/收起的层级列表。

搜索覆盖：

- environment label / host。
- workspace directory name。
- workspace full path fragment。
- session entry display name。
- shortcut name。

搜索结果默认仍应保留树上下文，高亮匹配节点并展开祖先节点。若结果过多，再考虑扁平结果列表；本 Spec 不要求独立搜索页。

### 8. Back-end restart recovery

后端重启后 `_processes` 中的 ttyd process 跟踪会丢失，但 tmux session/window 可能仍存在。

恢复策略采用懒恢复：

- list 阶段可显示持久记录，状态可标记为 stopped/unknown，需要按 tmux 查询能力进一步细化。
- 用户点击 entry 时，后端检查 workspace tmux session 和 managed window 是否存在。
- 若存在，重建 ttyd process 并 attach。
- 若 window 或 tmux session 缺失，按 restart 语义重建。

本阶段不要求启动时扫描所有 tmux sessions 并自动导入工作区列表，也不提供手动“重新扫描/重新连接已有 tmux 状态”的入口。

### 9. Compatibility with existing runtime hosts

三类 tmux-backed host 都应遵循同一产品语义：

- Windows/Cygwin：Windows 后端启动 ttyd，命令进入 Cygwin bash，再操作 tmux。
- Windows/WSL：Windows 后端启动 ttyd，命令使用 `wsl --cd <Windows path>` 进入默认 WSL，再操作 tmux。
- Linux：后端直接通过 Linux shell 操作 tmux。

差异只存在于命令包装和路径表达，不应改变 workspace/session/window 的产品层级。

## Affected components

### Backend

- `src/termbridge/models.py`
  - 需要表达 workspace、session entry、tmux session/window 相关持久元数据。
  - `SessionRecord` 现有字段可能需要重新归位为 entry 级字段，或被新的 workspace/entry 模型替代。
- `src/termbridge/services.py`
  - `SessionService.create()` 不再用 `request.name` 生成 tmux session name。
  - 创建流程需要先 resolve workspace，再确保 workspace tmux session，再创建/连接 managed window。
  - restart/delete/reconnect 需要区分 ttyd、window、session 层级。
  - `TerminalService.resolve_shortcut_command()` 需要从“启动 tmux session 运行 command”转向支持 workspace session + window 操作。
- `src/termbridge/api.py`
  - session create/list/delete/restart 语义需要与 workspace/entry 模型对齐。
  - 可能需要新增 workspace-level 操作或扩展现有 endpoint 返回结构。
- `src/termbridge/repositories.py`
  - 文件持久化结构需要支持 workspace 与 entries 的层级数据。
- `tests/test_services.py`
  - 覆盖 workspace identity、同目录复用、不同目录隔离、entry/window 生命周期。
- `tests/test_terminal_service.py`
  - 覆盖 Cygwin/WSL/Linux 三类 host 的 workspace tmux session 与 window command 生成。

### Frontend

- `frontend/src/types/sessions.ts`
  - 类型需要表达环境、workspace、entry 的树型关系，或至少支持由 flat API result 组装树。
- `frontend/src/api/sessions.ts`
  - 需要同步更新 list/create/restart/delete payload 和 response 类型。
- `frontend/src/components/SessionList.vue`
  - 从 flat list 改为 environment -> workspace -> entry 树型导航。
  - 支持展开/收起、选中状态、搜索过滤和状态聚合。
- `frontend/src/components/SessionCard.vue`
  - 可能被 entry row/tree item 替代，或缩小为第三级节点内容。
- `frontend/src/components/SessionCreateForm.vue`
  - 创建语义从“创建顶层 session”变为“选择环境 + 目录工作区 + 快捷方式，在工作区下创建 entry”。
- `frontend/src/components/SessionTerminal.vue`
  - 需要展示 entry 连接状态，并区分 reconnect/restart 操作。
- locale files
  - 增加 workspace、entry、reconnect、stop entry、delete workspace 等文案。

### Documentation

- `docs/spec/20260609-tmux-session-persistence.md`
  - 其中“tmux session name 使用 session_id”的旧设计会被本模型 supersede。
- `docs/spec/20260610-windows-wsl-runtime-support.md`
  - WSL command 应遵循当前业务语义：Windows 后端使用 `wsl --cd <Windows path>`，不要依赖 `wslpath` 预转换。

## Interface direction

本阶段不锁定最终 API/schema 字段，但接口语义应满足：

1. list 返回足够信息让前端构建 environment -> workspace -> entry 树。
2. create entry 能表达 host、workspace、shortcut、显示名/别名。
3. reconnect 能针对 entry 重建 ttyd process，而不重启 shortcut command。
4. restart entry 能在 workspace tmux session 中重建 managed window。
5. delete entry 与 delete workspace 语义分开。
6. 后端响应需要暴露 entry 状态：running、connection lost、window missing、workspace missing、environment not ready 等至少可被 UI 区分的状态。

## Technical questions

1. workspace identity 的规范化输入具体包含哪些字段：host、workspace path、distro、shell profile 是否需要纳入？
2. tmux session name hash 是否需要可逆或可诊断，还是只要稳定唯一即可？
3. 创建 managed window 时，是否用 tmux window name 承载 TermBridge entry id，还是只依赖 window id 持久记录？
4. tmux window id 在 session 被 kill/recreate 后必然失效，entry restart 时如何更新记录并避免误 attach？
5. list API 是否直接返回树，还是返回 flat workspaces/entries 由前端组装？
6. 搜索在前端完成是否足够，还是需要后端搜索支持以应对未来大量记录？
7. 旧 flat SessionRecord 数据如何迁移或兼容展示？

## Risks

1. tmux session/window 命令组合比当前 `new-session -A -s` 更复杂，quoting 和跨 host 行为需要重点测试。
2. 如果 window id 记录与实际 tmux 状态漂移，UI 可能显示 running 但 attach 失败；需要明确状态刷新和降级语义。
3. 删除语义若设计不清，会误杀用户仍想保留的 tmux 状态。
4. 懒恢复依赖点击时检查 tmux 状态，首次 list 的状态可能不完全准确。
5. 树型导航会改变现有 session list 交互，需要避免一次性引入过多 UI 行为。
6. 旧规格和现有代码中已有“每个 SessionRecord 一个 tmux session”的假设，实施时需要集中替换，避免双模型并存。
7. Windows/Cygwin、Windows/WSL、Linux 对路径和 shell quoting 的差异可能导致同一抽象在不同 host 下行为不一致。

## Alternatives considered

### Alternative 1: 继续每个 TermBridge session 一个 tmux session

优点：实现更接近现有代码。

缺点：无法自然表达同一目录工作区；长列表仍会膨胀；同名误 attach 只能靠改 tmux name 缓解，不能解决产品心智模型。

结论：不采用。

### Alternative 2: 工作区对应 tmux session，入口对应 tmux window

优点：符合目录工作区心智；支持多快捷方式共享一个目录上下文；树型导航层级清晰；tmux window 可自然承载第三级入口。

缺点：实现复杂度高于当前模型，需要处理 window id、手工操作和删除语义。

结论：采用。

### Alternative 3: 工作区对应 tmux session，入口对应 tmux pane

优点：同一窗口内可并排多个入口。

缺点：pane 更像布局细节，不适合作为左侧导航第三级身份；关闭/重排/聚焦语义更复杂。

结论：本阶段不采用，pane/tabs 留作未来终端区域交互设计。

### Alternative 4: 自动导入所有 tmux manual windows

优点：能完整反映 tmux 实际状态。

缺点：引入未托管状态、命令来源不明、命名冲突和同步复杂度。

结论：本阶段不采用；只管理 TermBridge 创建的 windows。

## User review notes

- 用户采纳 `tmux session` / `tmux window` 术语。
- 用户确认左侧导航使用树型结构，一级环境、二级目录、三级会话。
- 用户确认不支持同目录第二个独立运行实例。
- 用户希望停止语义分离 TermBridge 会话记录与 tmux 状态。
- 用户询问第三级会话与 tmux window 的映射，以及用户手工操作 tmux window 的影响；本规格采用 managed window 模型。
