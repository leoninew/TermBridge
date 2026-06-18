# 左侧会话节点修改能力需求
最后修改时间: 2026-06-18 16:27:08

- Flow mode: light
- Stage: Requirement
- Review status: Accepted
- Date: 2026-06-18

## Background

当前左侧会话树/会话节点主要支持选择、启动/停止、删除、排序等操作，但缺少直接修改会话展示名称的入口。用户希望在不刷新整个会话接口的前提下，能够从左侧会话节点直接打开编辑弹窗，修改会话名称，并持久化到后端 `sessions.json`。

## Goal

- 为左侧会话节点增加修改入口。
- 鼠标 hover 会话节点时展示修改 icon。
- 点击修改 icon 后打开模态窗。
- 模态窗展示：
  - 当前会话目录 / workspace path，只展示不可修改。
  - 当前会话名称 / name，可修改。
- 保存后调用后端接口更新该 session name。
- 后端将修改持久化到 `sessions.json`。
- 前端保存成功后只更新本地对应 session 数据，不刷新整个 session tree / session list 接口。

## Non-goal

- 不支持修改 session workspace / 目录。
- 不支持修改 shortcut、host、runtime、tmux session、tmux window、port、status、url 等运行态字段。
- 不改变 session 启动、停止、删除、排序逻辑。
- 不引入全量 session tree refresh 作为保存后的同步方式。
- 不处理跨 workspace 移动 session。

## User scenarios

1. 用户在左侧会话树中 hover 某个会话节点。
2. 节点右侧出现修改 icon。
3. 用户点击修改 icon。
4. 系统打开编辑模态窗，展示目录和名称字段。
5. 用户修改名称并保存。
6. 后端更新 `sessions.json` 中该 session entry 的名称。
7. 前端关闭弹窗，并局部更新左侧节点、已打开 terminal tab 或当前 session 标题中受名称影响的展示。

## Acceptance

- hover 会话节点时可见修改 icon；非 hover 状态不应显著干扰现有节点布局。
- 点击修改 icon 不应触发会话选择、启动、停止、删除或拖拽排序等其他节点行为。
- 编辑模态窗必须展示当前目录和名称。
- 目录字段不可修改。
- 名称字段可修改，保存时至少校验非空。
- 后端提供局部更新 session name 的接口，并持久化到 `sessions.json`。
- 若同一 workspace 下已存在同名 session，后端应拒绝并返回可展示错误，避免覆盖或产生重复 key。
- 保存成功后前端仅更新本地 session/session tree 中对应节点，不调用全量 session tree/list refresh。
- 保存成功后已打开终端不应被重新加载；仅展示名称变化。
- 现有 session start/stop/delete/reorder 行为保持不变。

## Open questions

暂无必须阻塞实现的问题。

## Decisions

- 使用 light / 轻量模式。
- 只允许修改 session name，不允许修改目录。
- 保存后不刷新整个会话接口，而是使用后端返回的 updated session 做前端局部状态更新。
- 后端数据源为现有 `sessions.json`，不新增独立存储。
- `sessions.json` 以 session name 作为 map key；改名时必须同时修改节点 key 和 entry 的 `name` 字段。

## Risk

- `sessions.json` 以 session name 作为 map key；改名时需要同时维护 key 和 entry.name，避免持久化结构不一致。
- 如果终端 tab、活动会话、左侧树分别持有不同本地状态副本，局部更新需要覆盖所有受影响位置，避免显示旧名称。
- 修改 icon 位于可点击/可拖拽节点内部，事件冒泡处理不当可能导致点击编辑时同时选中节点或触发其他操作。
- 后端需要保护同 workspace 重名，避免 sessions map key 冲突。

## User review notes

2026-06-18：用户确认 `sessions.json` 以 session name 作为 map key，改名时同时修改节点名称和 `name` 字段，并要求开始实现。
