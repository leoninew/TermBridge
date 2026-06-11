# tmux window 与会话存储生命周期修复需求

Review status: Accepted

## Background

用户在实际使用中发现：

- 新建一个 TermBridge 会话后，对应 workspace tmux session 内会出现两个 window：一个默认 `bash` window 和一个业务会话 window。
- 停止后恢复同一个会话时，可能继续创建额外 tmux window。
- 当前 `.termbridge/sessions.json` 虽然已有 workspace 层，但 key 是 hash id，entries 是列表；用户希望与左侧导航一致，按“环境 → 标准化目录完整路径 → 会话名称”组织，使会话管理更新更可靠。

## Goals

1. 保持产品模型：每个环境每个目录一个 tmux session，每个 TermBridge 会话一个 managed tmux window。
2. 新建第一个会话时不留下额外默认 `bash` window。
3. 停止会话时保留 managed tmux window，只停止 ttyd 连接并标记记录为 stopped。
4. 恢复 stopped 会话时复用原 managed tmux window，不创建额外 window。
5. 将 sessions 持久化结构调整为三层结构：环境、标准化目录完整路径、会话名称。
6. 不向后兼容旧 sessions schema，不迁移历史数据；新实现只接受新三层 schema。
7. 删除会话时保留目录节点，让用户可在目录节点上快速创建新会话。
8. 创建会话的选中环境和目录改成显式上下文，不再从当前会话隐式推断。
9. 目录节点 hover 时右侧展示删除 icon，可删除 `.termbridge/sessions.json` 的二级目录节点。

## Non-goals

- 不自动导入用户手工创建的 tmux window。
- 不改变 shortcuts、environment settings 或前端路由模型。
- 不在本需求中增加单独的“关闭连接”和“终止 window”按钮。
- 删除会话不删除目录节点；删除目录节点是单独的目录级操作。

## User scenarios

- 用户在某个环境和目录下新建一个会话后，`tmux list-windows -a` 中该 workspace tmux session 只出现一个由 TermBridge 管理的业务 window。
- 用户停止会话后再恢复，同一个会话继续 attach 到原 window，不新增 window。
- 用户查看 `.termbridge/sessions.json` 时，能够按环境、目录、会话名称理解和定位记录。
- 用户删除某个会话后，目录仍保留在左侧导航，可从该目录快速创建新会话。
- 用户 hover 目录节点时，可以点击右侧删除 icon 删除该目录节点。
- 用户在目录节点上触发新建会话时，创建表单显式使用该环境和目录作为初始上下文。
- 旧格式 sessions 文件不再作为兼容目标；需要用户清理或重新生成 `.termbridge/sessions.json`。

## Acceptance

- [ ] 新建 workspace tmux session 时不会保留默认空 `bash` window。
- [ ] 每个 TermBridge 会话对应一个 managed tmux window。
- [ ] Stop 保留 `tmux_window_id`，停止 ttyd process，清空 URL/端口连接状态，并将 entry 标记为 stopped。
- [ ] Restart stopped entry 时如果原 window 仍存在，则复用原 window 并启动新的 ttyd attach。
- [ ] Restart stopped entry 时如果原 window 不存在，则按同一个 entry 重建 window 并更新 `tmux_window_id`。
- [ ] Delete entry 仍会 kill managed window，但不删除目录节点。
- [ ] Close all sessions 关闭所有 managed windows 和 workspace tmux sessions，并保留 records 与目录节点。
- [ ] 目录节点 hover 时展示删除 icon；确认/点击后删除 `.termbridge/sessions.json` 中对应二级目录节点。
- [ ] 从目录节点新建会话时，创建表单显式使用该环境和目录作为初始值。
- [ ] `.termbridge/sessions.json` 写出为环境、标准化目录完整路径、会话名称三级结构。
- [ ] 旧 `workspaces` hash schema 不再兼容，读取时应明确报 incompatible schema。
- [ ] 后端测试覆盖新建、停止、恢复、删除、close all、新 schema 写读和旧 schema 拒绝。

## Risks and assumptions

- 以会话名称作为第三级 key 意味着同一环境同一目录下会话名称必须唯一；创建重名会话应被拒绝或明确覆盖策略。本需求采用拒绝重名。
- 标准化目录完整路径作为 JSON key 在 Windows 路径中包含盘符和反斜杠/斜杠，需要统一转成稳定的 forward-slash 表达。
- Stop 语义从 kill window 改为保留 window，会改变当前测试和既有规格中的部分描述；本需求以用户最新确认的语义为准。
- Close all sessions 仍是高影响操作，可以 kill windows/session，因为它是显式批量终止动作。
- 不兼容旧 sessions schema 会丢失历史会话管理记录的自动读取能力；这是本需求的明确约束。
