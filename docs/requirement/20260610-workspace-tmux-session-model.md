# 工作区中心的 tmux 会话模型需求

Review status: Accepted

当前：严格模式 / strict，需求阶段 / Requirement

## Background

当前 TermBridge 新建会话时由用户填写名称，后端将该名称规范化后作为 `tmux new-session -A -s <session>` 的 tmux session name。这个模型让“用户显示名称”和“tmux 运行身份”绑定在一起，带来几个产品语义问题：

1. 相同运行环境下，不同目录、不同 TermBridge 会话如果使用相同名称，会因为 tmux `-A -s` 语义而 attach 到同一个 tmux session。
2. 用户真正想管理的常常不是一次启动记录，而是某个目录里的工作上下文。
3. 会话列表随着使用增长会变成长列表，需要按目录、运行环境、快捷方式等维度管理和搜索。
4. 当前“会话”“tmux session”“ttyd 进程”语义混在一起，导致删除、停止、重连、后端重启恢复等行为难以解释。

本需求将 TermBridge 的主模型从“命名会话列表”调整为“运行环境 + 工作目录”的工作区模型，并在该工作区下管理 tmux-backed 运行入口。

## Goals

1. 将 `运行环境 + 工作目录` 定义为主要用户可理解的工作区身份。
2. 避免用户填写的会话名称直接决定 tmux session 身份，从而避免跨目录同名误 attach。
3. 支持同一运行环境、同一工作目录复用一个工作区上下文。
4. 支持在一个工作区下区分不同快捷方式或运行入口，例如 Claude Code、Codex、bash。
5. 为长列表管理提供基础：按环境、目录、运行入口分层展示，并支持搜索和快速回到最近工作区。
6. 让用户能理解“打开工作区”“运行快捷方式”“连接已有 tmux 状态”“删除记录/终止状态”的区别。
7. 将 TermBridge session entry 与 tmux window 建立清晰映射，同时保留工作区级 tmux session 作为持久状态边界。

## Non-goals

1. 本阶段不要求设计具体数据库/schema/API 字段。
2. 本阶段不要求决定 tmux panes/tabs 的最终技术实现。
3. 本阶段不要求实现跨机器、多人共享或远程发现工作区。
4. 本阶段不要求完整解决后端重启后的自动扫描恢复问题。
5. 本阶段不替换 tmux 为其他持久化机制。
6. 本阶段不要求改变快捷方式本身的命令配置语义。
7. 本阶段不自动导入用户在 tmux 内手工创建的 window。
8. 本阶段不支持同一运行环境 + 同一目录下显式创建第二个独立工作区实例。

## User scenarios

### Scenario 1: 相同环境不同目录使用相同显示名称

用户在 Windows/WSL 环境中分别打开：

- `D:\SourceCodes\agentic\TermBridge`
- `D:\SourceCodes\agentic\cc-switch`

即使两个工作区的显示名称都叫 `dev` 或都由目录名派生出相同短名，也不应互相 attach 到同一个 tmux session。

### Scenario 2: 相同环境相同目录重新打开

用户已经在 Windows/WSL + `D:\SourceCodes\agentic\cc-switch` 中运行过 Claude Code。之后再次从同一环境和同一目录创建/打开工作区时，TermBridge 应优先让用户回到已有工作区上下文，而不是创建一个难以区分的重复顶层会话。

### Scenario 3: 同一工作区运行多个快捷方式

用户在同一目录下需要同时运行 Claude Code、Codex 和 bash。TermBridge 应把它们组织在同一个工作区下，而不是在顶层列表中显示为三个彼此无关的会话。

在 tmux 语义上，同一 `运行环境 + 工作目录` 对应一个 tmux session；该工作区下的每个 TermBridge 会话入口对应一个由 TermBridge 管理的 tmux window。

### Scenario 4: 长列表管理

用户长期使用后有几十个目录工作区。左侧导航应采用树型结构：

1. 一级节点：运行环境。
2. 二级节点：目录工作区。
3. 三级节点：会话入口 / 快捷方式运行入口。

树组件参考 `docs/guides/llms.txt` 中的 Reka UI `Tree`，用于表达可展开/收起的层级列表。用户应能通过目录名、路径片段、运行环境、快捷方式名称或显示名称快速找到目标工作区或入口。

### Scenario 5: 删除、停止与终止语义清晰

用户删除某个 TermBridge 条目时，需要知道这是只移除管理记录、关闭 ttyd 连接、关闭某个 managed tmux window，还是同时 kill 对应工作区 tmux session。不同操作的影响应在 UI 和行为上可区分。

### Scenario 6: 手工操作 tmux window 后仍可解释

用户可能在 tmux 内手工 rename、move、关闭 window，或者创建新的 window。TermBridge 应能解释这些操作对 managed session entry 的影响，而不是依赖易变化的 window index。

## Acceptance criteria

1. 相同运行环境下，不同工作目录即使使用相同用户显示名称，也不会 attach 到同一个 tmux session。
2. 相同运行环境 + 相同工作目录再次打开时，系统能够识别这是同一个工作区上下文，并避免默认创建重复顶层条目。
3. 同一工作区内可以展示多个快捷方式/运行入口，并能区分它们的状态或连接入口。
4. 顶层导航按 `运行环境 -> 工作目录 -> 会话入口` 的树型结构组织，至少能让用户看出哪些运行入口属于同一个目录。
5. 搜索能力至少覆盖：目录名、完整路径片段、运行环境、快捷方式名称、用户可见名称。
6. 用户填写的名称可以作为显示名或别名，但不能单独作为 tmux session 的全局唯一身份。
7. tmux session 身份应由系统生成或由稳定的工作区身份派生，避免用户无意制造冲突。
8. `运行环境 + 工作目录` 对应一个工作区级 tmux session。
9. 工作区下的 TermBridge 会话入口对应一个 managed tmux window；身份应优先使用稳定 window id，而不是 window index。
10. 通过会话列表点击运行中的会话入口时，应 attach 到对应工作区 tmux session 并切换到对应 managed tmux window。
11. 当 ttyd 进程失效但 tmux session/window 仍存在时，重新连接应重建 ttyd 连接并 attach 到已有 window。
12. 当 managed tmux window 已不存在但工作区 tmux session 仍存在时，重启入口应重新创建该快捷方式对应的 managed window。
13. 当工作区 tmux session 已不存在时，重启或重新打开应能重新创建工作区 tmux session，再创建或连接目标 window。
14. 删除、停止、重启、重新连接等操作在需求语义上必须区分 TermBridge 管理记录、ttyd 进程、managed tmux window 和工作区 tmux session。
15. 只有当某个工作区下不再有需要保留的 managed entry/window 时，才应终止该工作区 tmux session。
16. 新模型应兼容 Windows/Cygwin、Windows/WSL、Linux 三类 tmux-backed 运行环境。
17. 后续 Spec/Plan 不应再假设“用户输入会话名 = tmux session name”。
18. 用户在 tmux 内手工创建的 window 默认不作为 TermBridge managed entry 导入。

## Decisions

1. 主要产品身份采用 `运行环境 + 工作目录` 的工作区模型。
   - 理由：用户的实际工作上下文通常围绕目录展开；这也天然支持分组、搜索和长列表管理。
2. 用户填写的名称不再作为 tmux session 的唯一身份来源。
   - 理由：tmux `new-session -A -s` 对同名 session 会 attach；直接使用用户名称会造成跨目录误复用。
3. 同一运行环境 + 同一工作目录应被视为同一工作区上下文。
   - 理由：重复创建同目录顶层会话会让列表膨胀，也不利于恢复已有状态。
4. 不同快捷方式属于工作区下的运行入口。
   - 理由：Claude Code、Codex、bash 等入口是同一目录工作的不同工具，不应默认割裂为顶层无关会话。
5. 左侧导航采用树型结构：环境 -> 目录 -> 会话入口。
   - 理由：树结构直接表达归属关系，适合长列表、折叠、搜索和状态聚合。
6. `运行环境 + 工作目录` 映射为工作区级 tmux session。
   - 理由：tmux session 是合适的持久状态边界；不要将它称为 tmux process，tmux server process 可管理多个 session。
7. 第三级 TermBridge 会话入口映射为 managed tmux window。
   - 理由：同一目录下多个快捷方式需要共享工作区状态但彼此可切换，tmux window 比多个 tmux session 更符合“一个目录工作区”的语义。
8. managed tmux window 身份应依赖稳定 window id，而不是 window index。
   - 理由：用户移动或重排 window 会改变 index，但 window id 更适合作为 TermBridge entry 的持久引用。
9. 不支持同一运行环境 + 同一目录下创建第二个独立工作区实例。
   - 理由：默认模型保持简单，避免重新引入重复顶层会话和身份歧义。
10. 用户手工创建的 tmux window 不自动导入。
    - 理由：当前阶段聚焦 TermBridge managed entry；自动发现/导入会扩大产品和同步复杂度。
11. 删除/停止语义应分层表达。
    - 理由：TermBridge record、ttyd 连接、tmux window、tmux session 的生命周期不同，混成一个“删除”会导致误杀长期状态。
12. 会话入口可以停止；停止后 TermBridge record 保留，但对应 managed tmux window 被移除。
    - 理由：停止表示终止该入口的运行状态，而不是遗忘这个入口；再次启动时可按记录重新创建 window。
13. tmux window id/current window name 不在 UI 中显式展示，仅作为内部诊断信息。
    - 理由：用户需要理解工作区和会话入口，不需要暴露 tmux 内部身份细节。
14. 后端重启后的恢复以点击 entry 时懒恢复/重新连接为主，不提供手动“重新扫描/重新连接已有 tmux 状态”的入口。
    - 理由：用户想要的是清晰停止语义和可重新连接能力；自动扫描导入和手动扫描入口会扩大当前阶段复杂度。

## Manual tmux behavior

1. 用户重命名 managed window：TermBridge 仍将其视为同一个 managed entry；UI 可继续显示快捷方式元数据，并可附带当前 tmux window 名称。
2. 用户移动或重排 managed window：不应影响 TermBridge 映射，因为身份不依赖 window index。
3. 用户关闭 managed window：对应 TermBridge entry 进入 stopped/invalid 状态；再次打开时可重新创建 window。
4. 用户手工创建新 window：默认不出现在 TermBridge 树的第三级 managed entries 中。
5. 用户 kill 工作区 tmux session：该目录工作区和其下 managed entries 都进入 stopped/invalid 状态；重新打开时按工作区模型重建。

## Reconnect and lifecycle semantics

1. 点击运行中的 entry：attach 到工作区 tmux session，并切换到该 entry 对应的 managed window。
2. ttyd 进程失效但 tmux session/window 存在：重建 ttyd 连接并 attach 到既有 managed window。
3. managed window 不存在但工作区 tmux session 存在：重启该 entry 时创建新的 managed window。
4. 工作区 tmux session 不存在：重新创建工作区 tmux session，再创建目标 managed window。
5. 工作目录不存在或运行环境未 ready：相关操作应 disabled 或返回明确错误，并给出用户可理解的修复方向。
6. 停止某个 entry 时，保留 TermBridge record，但移除该 entry 对应的 managed tmux window。
7. 删除某个 entry 不应默认 kill 整个工作区 tmux session；只有工作区下无需要保留的 managed entry/window 时，才允许终止工作区 tmux session。

## Open questions

1. 树型导航中的搜索结果应如何展示：保持树上下文、高亮匹配节点，还是切换为扁平结果列表？

## Risks and assumptions

1. 如果工作区模型过早引入复杂 panes/tabs 设计，可能超出当前产品需要；应先解决身份、分组和误 attach 问题。
2. 如果删除/终止语义不清，用户可能误杀长期运行的 tmux 状态。
3. 工作区身份需要跨 Windows/Cygwin、Windows/WSL、Linux 保持一致语义，但不同 host 的路径表示不同，后续规格需要明确规范化策略。
4. 假设用户最常见的心智模型是“我在某个目录里工作”，而不是“我创建了一次临时终端进程”。
5. 假设快捷方式名称在同一运行环境内已保持唯一，便于同一工作区下清晰展示入口。
6. 假设 managed tmux window 可通过稳定 id 追踪；如果部分平台或 tmux 版本行为不一致，Spec/Plan 需要验证。
7. 如果用户大量手工操作 tmux，TermBridge managed state 可能与实际 tmux 状态漂移；当前阶段接受该风险，并以 stopped/invalid/recreate 语义处理。

## User review notes

- 用户指出当前新建会话名称由用户指定，而 tmux 使用该名称时会带来同名 attach 问题。
- 用户选择“目录工作区”作为主要会话身份模型。
- 用户希望严格模式先输出需求，后续再进入 Spec/Plan。
- 用户确认左侧导航采用树型结构：环境 -> 目录 -> 会话。
- 用户确认采用 tmux session / tmux window 术语：工作区对应 tmux session，三级会话入口对应 tmux window。
- 用户确认不支持同目录第二个独立运行实例。
- 用户希望将 TermBridge session record、ttyd 进程、tmux session/window 生命周期分离。
- 用户提出并接受：手工 tmux window 操作应被容忍，但手工创建的 window 当前不自动导入。
- 用户确认会话入口可以停止；停止时保留 TermBridge record，但移除对应 managed tmux window。
- 用户确认 tmux window id/current window name 仅作为内部诊断信息，不在 UI 中显式展示。
- 用户确认后端重启后不提供手动扫描入口，仅在用户点击 entry 时懒恢复。
