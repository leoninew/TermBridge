# 会话运行时状态一致性规格
最后修改时间: 2026-06-17 16:09:49

- Flow mode: strict
- Stage: Spec
- Review status: Accepted
- Date: 2026-06-17

## Requirement basis

基于已接受的需求文档：

- `docs/requirement/20260617-session-runtime-state-consistency.md`

本规格解决两个相关问题：

1. 业务会话状态必须由 live tmux window 和 live ttyd proxy 推导，不能继续把 persisted `status` 当成最终真相。
2. `/session` 页需要保持首屏性能，两阶段加载可接受；create/start/stop/delete 继续沿用现有局部响应更新策略。

## Overview

业务 session 是 TermBridge 持久化的 session entry；tmux window 和 ttyd process/port 是运行时资源。

对外业务状态收敛为：

```text
running       live tmux window exists + ttyd port available
disconnected  live tmux window exists + ttyd port unavailable
stopped       no live tmux window, or stopped records skipped by live refresh
failed        保留为错误状态，如现有代码仍需要表达启动失败
```

`starting` 语义取消。新建和启动都是同步操作：成功直接返回 `running`，失败直接返回错误。

状态刷新分为两类路径：

1. **单 session 强刷新**：`get()`、`start()`、`terminal_proxy_target()` 使用。可对目标 entry 调用 `tmux_window_exists()` 和 `_ttyd_port_checker()`。
2. **列表批量刷新**：`list_tree(refresh=true)`、`list_sessions()` 使用。为了性能，每个 host 最多执行一次 `tmux list-windows -a`，然后只对存在 live tmux window 的非 stopped entries 检查 ttyd port。

`list_tree(refresh=false)` 用于 `/session` 首屏快速加载，返回持久化/缓存树，但前端必须防止在 live refresh 完成前打开陈旧 `running/url` iframe。

## Design decisions

### 1. SessionStatus 移除 starting

`src/termbridge/models.py`：

```py
class SessionStatus(StrEnum):
    RUNNING = "running"
    DISCONNECTED = "disconnected"
    STOPPED = "stopped"
    FAILED = "failed"
```

删除 `STARTING` enum 值。

兼容决策：不做历史 `status="starting"` JSON 兼容或迁移。移除 enum 后，如果本地历史状态文件仍包含 `starting`，应按非法状态暴露加载错误，由用户清理或重新生成状态文件；实现不保留内部 starting 解析路径。

### 2. create 不再构造 STARTING entry

当前 `SessionService.create()` 先构造 `status=SessionStatus.STARTING` 的 entry，再调用 `_start_entry()`。

调整为：

1. 创建 tmux window。
2. 构造一个内部 entry 草稿时使用 `STOPPED` 或直接不依赖 status。
3. 调用 `_start_entry()`。
4. 成功后持久化 `RUNNING` entry。
5. 失败时清理已创建 tmux window，不持久化对外可见 starting。

该调整不改变同步行为；只是移除对外状态和代码分支中的 starting。

### 3. stopped entry 的 live refresh 规则

需求已明确：`/session` 不检查 stopped 会话是否真实存活，stopped 的历史 `pid` / `port` / `url` / `tmux_window_id` 不参与业务判断。

因此：

- `list_tree(refresh=true)` 批量刷新时，`entry.status == STOPPED` 的 entry 直接保留为 stopped，不调用 ttyd port checker，不依赖历史 tmux_window_id。
- `get()` 如果目标 entry 是 stopped，也直接返回 stopped 或做最小规范化，不主动扫描历史资源。
- `terminal_proxy_target()` 对 stopped entry 直接拒绝，不因为历史 port 可连而恢复 running。
- `start()` 对 stopped entry 按 happy path 重新创建或查找业务 session 对应 window，再启动 ttyd。

注意：如果历史 stopped entry 保留 port 非零，端口分配必须忽略 stopped entry 的 port。

### 4. port allocation 跳过 stopped entries

当前 `_start_entry()` 使用：

```py
used_ports = [item.port for _, item in self._repository.list_entries() if item.id != entry.id and item.port]
```

这会把 stopped 历史 port 当成占用。

调整为只把非 stopped 且 port 非零的 entry 作为业务占用：

```py
used_ports = [
    item.port
    for _, item in self._repository.list_entries()
    if item.id != entry.id and item.status != SessionStatus.STOPPED and item.port
]
```

`PortAllocator` 仍会通过 socket bind 排除 OS 层面实际占用端口，因此即使 stopped 历史 port 被忽略，只要端口仍被孤儿进程占用，也不会被错误分配。

### 5. running / disconnected refresh 规则

对 `RUNNING` 和 `DISCONNECTED` entry：

1. 判断 live tmux window：
   - 单 entry 路径：使用 `terminal_service.tmux_window_exists(host, workspace.path, tmux_window_id=entry.tmux_window_id)`。
   - 批量路径：使用每 host 一次 `list_tmux_windows()` 得到的 live window names，沿用当前 `entry.name in window_names` 模型。
2. 如果 tmux window 不存在 => `STOPPED`。
3. 如果 tmux window 存在，则检查 `entry.port > 0 and _ttyd_port_checker(entry.port)`。
4. port 可用 => `RUNNING`。
5. port 不可用 => `DISCONNECTED`。

本规格不要求额外验证 pid、command line、credential 或日志归属。

### 6. refresh 需要规范化状态关联字段

当前 `_refresh_entry_with_window_state()` 只更新 `status`。这会留下不一致字段。

调整为根据刷新结果做最小规范化：

- `RUNNING`：保留 `port`、`url`、`pid`、`tmux_window_id`。
- `DISCONNECTED`：保留 `tmux_window_id`；`url` 可以保留用于 UI 重连入口或清空，Spec 建议保留现有 url 兼容前端字段，但前端不得在 disconnected 下渲染 iframe。
- `STOPPED`：状态设为 stopped；stop happy path 按现有资源关闭语义写出 stopped。refresh 从 running/disconnected 降级到 stopped 时，不清空 `tmux_window_id`；业务逻辑仍不得依赖 stopped entry 的历史 `tmux_window_id`。

关于 `port`：不要求清零；但 stopped 的 port 不参与端口分配和 terminal proxy。

### 7. list_tree 两阶段加载语义

后端已支持：

```ts
listSessionTree({ refresh: false })
listSessionTree()
```

保留该接口形态。

前端 `AppShell.refresh()` 当前流程已经是：

1. `loadStoredSessions()` 调用 `/api/session-tree?refresh=false`。
2. 后台继续 `refreshLiveSessions()` 调用 `/api/session-tree`。

需要补齐的是 iframe 保护策略：

- 首屏缓存数据应用后，如果 `sessionStatusRefreshing` 为 true，则不应立即渲染缓存 running session 的 iframe。
- 可以保留 tab / active selection。Plan 阶段需要在两种实现之间选择：父级传入 refresh gate prop 让 `SessionTerminal` 自己决定显示“正在刷新会话状态”或空态；或者父级在传入前过滤/包装 `openTerminalSessions`，使 terminal 子组件只看到允许打开 iframe 的 session。
- live refresh 完成后，再按 refreshed session status 渲染 iframe、重连入口或启动入口。

这样接受两阶段加载，同时避免 stale running/url 触发 `/terminal/...` conflict。

### 8. create/start/stop/delete 前端策略

继续沿用现有 happy path 局部响应更新：

- create 返回 `Session`，前端 `updateSession(session)` + `openTerminalSession(session)`。
- start 返回 `Session`，前端 `updateSession(started)` + `openTerminalSession(started)`。
- stop 返回 `Session`，前端 `updateSession(stopped)`。
- delete 返回 204，前端删除本地 session。

不要求这些操作后统一重新拉 `/api/session-tree`。

要求：后端这些接口返回的数据必须符合同步操作结果：

- create/start 成功返回 `running`。
- stop 成功返回 `stopped`。
- delete 成功删除业务记录。

### 9. 前端移除 starting 状态分支

影响：

- `web/src/types/sessions.ts` 删除 `'starting'`。
- `web/src/components/AppShell.vue` 的 workspace 聚合不再判断 starting。
- `web/src/components/SessionList.vue` 删除 `session.status === 'starting'` 的状态样式分支。
- `web/src/components/SessionTerminal.vue` 保留 `startingSessionId` 这类“按钮请求中”的 UI 状态；这是前端 action loading，不是业务 status。
- i18n 中 `session.status.starting` 若存在可删除或不再引用。

注意：`startingSessionId` 命名虽然包含 starting，但语义是“start action pending”，可以保留；如果实现阶段顺手改名会扩大 diff，不建议作为本任务必须项。

### 10. workspace 聚合状态

聚合优先级调整为：

```text
running > disconnected > failed > stopped
```

删除 `starting`。

### 11. tmux window duplicate handling

需求确认：stopped 状态不依赖历史 `tmux_window_id`；running 状态的 `tmux_window_id` 正常不应重复。

本规格不引入复杂自动冲突修复。仅要求：

- stopped entries 不参与 live window ownership 判断。
- 若实现中检测到多个 non-stopped entries 指向同一 live `tmux_window_id`，应优先避免产生 running 重复状态；可以在日志中 warning，并把无法确认的 entry 按 refresh 结果降级。

具体实现可在 Plan 阶段决定是否增加显式检测。

## Affected components

### Backend

- `src/termbridge/models.py`
  - 移除对外 `SessionStatus.STARTING`。
  - 移除 `SessionStatus.STARTING`，不增加历史 starting 兼容加载策略。
- `src/termbridge/services.py`
  - `create()` 不再使用 `STARTING`。
  - `_start_entry()` 端口分配跳过 stopped entries。
  - `_refresh_entry()` / `_refresh_entry_from_tmux_listing()` 不再跳过 starting。
  - stopped entries 不参与 live refresh。
  - `_refresh_entry_with_window_state()` 做状态和字段最小规范化。
  - `_workspace_response()` 删除 starting 聚合优先级。
- `src/termbridge/repositories.py` 或等效 session repository 文件
  - 不增加历史 `status="starting"` 兼容归一化；非法历史状态按加载错误处理。
- `src/termbridge/api.py`
  - API shape 不变；确认 create/start/stop/delete 返回状态符合同步结果。

### Frontend

- `web/src/types/sessions.ts`
  - 删除 `'starting'`。
- `web/src/components/AppShell.vue`
  - 两阶段加载已有，补齐 refresh 前 iframe 保护。
  - workspace 聚合删除 starting。
- `web/src/components/SessionList.vue`
  - 删除业务 status starting 分支。
- `web/src/components/SessionTerminal.vue`
  - 接收刷新中状态或由父级过滤 iframe 渲染；避免 live refresh 完成前渲染 cached running iframe。
  - 保留 action loading 的 `startingSessionId`。
- `web/src/i18n/locales/*.json`
  - 删除或停止引用 `session.status.starting`。

### Tests

- `tests/test_services.py`
  - 更新/新增状态刷新、端口分配、starting 移除、stopped 历史字段不参与判断。
- `tests/test_api.py`
  - 如有 schema/status 断言，更新为无 starting。
- 前端测试或 typecheck
  - 覆盖 TypeScript union 删除 starting 后无编译错误。
  - 如项目已有组件测试，补充 `/session` refresh gate；否则通过 typecheck/lint 验证。

## Interfaces

### SessionStatus API

移除：

```text
starting
```

保留：

```text
running
disconnected
stopped
failed
```

### `/api/session-tree?refresh=false`

语义保持：返回快速缓存树，不执行 live tmux/ttyd 检查。

前端使用限制：refresh=false 数据不得直接驱动 iframe 打开 terminal，除非 live refresh 已完成或该 session 是本轮 create/start 成功返回的 fresh session。

### create/start/stop/delete

接口形态不变：

- `POST /api/sessions` => `SessionResponse`，成功 status 为 `running`。
- `POST /api/sessions/{id}/start` => `SessionResponse`，成功 status 为 `running`。
- `POST /api/sessions/{id}/stop` => `SessionResponse`，成功 status 为 `stopped`。
- `DELETE /api/sessions/{id}` => 204。

## Technical questions

暂无必须阻塞 Plan 的问题。

Plan 阶段需要细化：

1. `SessionTerminal` 的 refresh gate 采用父级传 prop，还是父级过滤/包装 `openTerminalSessions`。

已确认：不做历史 `status="starting"` JSON 兼容或迁移；refresh 降级 stopped 时不清空 `tmux_window_id`。

## Risks

1. 移除 enum `starting` 可能破坏历史状态文件加载；本任务明确不做兼容或迁移，历史非法状态需要用户清理或重新生成。
2. 如果 stopped entries 不参与 refresh，历史 stopped 但 live 资源仍在的脏数据不会被自动恢复；这是本需求接受的业务选择，但可能留下 orphan ttyd/tmux，需要依赖 stop/delete/close-all 或用户手动清理。
3. 两阶段加载的 iframe gate 如果实现不完整，仍可能在 refresh 前触发 `/terminal/...` 409。
4. 端口分配跳过 stopped entries 后，若 stopped 历史 port 对应的孤儿 ttyd 仍占用 OS 端口，必须依赖 `PortAllocator._is_available()` 排除；该行为需要测试确认。
5. 删除 starting 前端分支时，要区分业务 status starting 和 action loading `startingSessionId`，避免误删按钮 loading 保护。

## Alternatives considered

1. **保留 starting 但不使用**：拒绝。用户明确要求消除 starting 语义；保留会继续污染类型和 UI 分支。
2. **所有操作后统一重新拉 `/api/session-tree`**：拒绝。用户明确要求 create/start/stop/delete 沿用现有 happy path 局部响应策略。
3. **每次 `/session` 首屏都全量 live refresh 后再展示**：拒绝。会牺牲性能；需求接受两阶段加载。
4. **对 ttyd 归属做 command line / credential 验证**：拒绝。用户确认当前 `tmux_window_id + ttyd port` 模型足够。

## User review notes

- 用户确认 Spec，要求进入 Plan。
- 用户明确：历史 `status="starting"` JSON 不做兼容或迁移。
- 用户明确：refresh 降级到 stopped 时不清空 `tmux_window_id`。
- 用户要求解释 `SessionTerminal` refresh gate 的父级 prop 与父级过滤方案差异，并在 Plan 中选型。
