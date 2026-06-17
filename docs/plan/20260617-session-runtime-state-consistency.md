# 会话运行时状态一致性计划
最后修改时间: 2026-06-17 16:23:53

- Flow mode: strict
- Stage: Plan
- Review status: Accepted
- Date: 2026-06-17

## Requirement / Spec basis

- Requirement: `docs/requirement/20260617-session-runtime-state-consistency.md`，Review status: Accepted
- Spec: `docs/spec/20260617-session-runtime-state-consistency.md`，Review status: Accepted

本计划按已接受的需求和规格实施：

1. 删除业务状态 `starting`。
2. 不做历史 `status="starting"` JSON 兼容或迁移；历史非法状态按加载错误处理。
3. stopped entry 不参与 live refresh、terminal proxy 可用性判断或业务端口占用判断。
4. running / disconnected entry 继续按 live tmux window + ttyd port 推导状态。
5. refresh 从 running / disconnected 降级为 stopped 时，不清空 `tmux_window_id`。
6. `/session` 保留两阶段加载和 create/start/stop/delete 局部响应更新。
7. `/api/session-tree?refresh=false` 返回的数据只用于快速展示 session tree 结构，不用于 runtime availability 判断。
8. 前端 live refresh 完成前，来自缓存列表的 session runtime state 统一视为不可用。

## `/session` runtime availability 策略

### 核心原则

`refresh=false` 数据不是可信运行时状态。

它只能回答：

- 有哪些 environment / workspace / session entry。
- session 的名称、workspace、shortcut 等结构信息。

它不能回答：

- session 是否 running。
- session 是否 disconnected。
- session 是否 stopped。
- 是否可以打开 terminal iframe。
- 是否可以执行 start / reconnect / stop 这类依赖运行时状态的操作。

因此 live refresh 未完成前，不应把 cached `status` 解释成业务可用状态。UI 上应统一视为 runtime state unverified / unavailable。

### 职责边界

`SessionTerminal.vue` 不承担 refresh gate 或数据来源判断责任。

`SessionTerminal.vue` 的职责应保持简单：

- 接收已经可信、可解释的 session 状态。
- 根据 `running / disconnected / stopped / failed` 展示 terminal、重连入口或启动入口。
- 处理 tab 展示和 terminal iframe 展示。

`AppShell.vue` 承担 `/session` 页数据可信度管理：

- 知道当前 session tree 是否来自 `refresh=false`。
- 知道 live refresh 是否成功完成。
- 决定 runtime 相关 UI 和操作是否可用。
- 在状态未验证前，不把 session 当成可用 terminal session 打开。

### 采用方案：AppShell 统一管理 runtime state verified

引入前端页面级状态，例如：

```ts
const sessionRuntimeStateVerified = ref(false)
const sessionRuntimeStateRefreshing = ref(false)
```

语义：

- `sessionRuntimeStateVerified === false`：当前 session tree 可用于结构展示，但 runtime 状态不可用。
- `sessionRuntimeStateVerified === true`：当前 session tree 已经过 live refresh，可用于运行时状态判断。

加载流程：

1. 页面初始 refresh 开始时设置 `sessionRuntimeStateVerified = false`。
2. `loadStoredSessions()` 调用 `/api/session-tree?refresh=false` 并应用 tree；此时仍保持 `sessionRuntimeStateVerified = false`。
3. `refreshLiveSessions()` 调用无 query `/api/session-tree`。
4. live refresh 成功并应用 tree 后，设置 `sessionRuntimeStateVerified = true`。
5. live refresh 失败时保持 `sessionRuntimeStateVerified = false`，避免把 stale cached state 当成可用状态。

### UI 行为

当 `sessionRuntimeStateVerified === false`：

- session list 可以展示 environment / workspace / session entry。
- session status badge 或状态区域显示“状态检查中”或等价 loading 状态。
- 依赖 runtime state 的操作禁用：
  - 打开 terminal
  - start / 启动会话
  - reconnect / 重连会话
  - stop / 停止会话
- terminal 面板显示页面级不可用状态，例如“正在刷新会话状态”。
- 不创建 terminal iframe。
- 不根据 cached `running / disconnected / stopped` 展示启动、重连或运行中状态。

当 `sessionRuntimeStateVerified === true`：

- session list 和 terminal panel 使用 refreshed `running / disconnected / stopped / failed` 状态。
- running session 可打开 iframe。
- disconnected session 显示“重连会话”。
- stopped session 显示“启动会话”。

### create/start/stop/delete 与 verified 状态的关系

create/start/stop/delete 是用户主动触发的 happy path 操作，后端返回同步操作结果，仍按现有局部响应更新策略处理。

但 cached tree 的旧 session 在 live refresh 完成前不可操作。

建议策略：

1. live refresh 未完成前，禁止对旧 session 执行 start / reconnect / stop / open terminal。
2. create 是否允许可以保持现状；create 成功返回的是 fresh running session，不来自 cached tree。
3. start 如果只能从旧 session 入口触发，则因为旧 session 操作被禁用，必须等待 live refresh 完成后再触发。
4. create/start 成功返回的 fresh session 可以通过局部响应立即进入可用状态；这是 fresh operation response，不是 `refresh=false` 缓存状态。
5. stop/delete 成功后继续局部更新本地状态。

如果实现阶段希望进一步简化，也可以选择：只要 `sessionRuntimeStateVerified === false`，除 create 外禁用所有 session runtime 操作。这样最符合“状态没有 refresh 完就是不可用”。

## Implementation steps

### 1. 后端删除 `SessionStatus.STARTING`

文件：`src/termbridge/models.py`

1. 从 `SessionStatus` enum 删除：

   ```py
   STARTING = "starting"
   ```

2. 保留状态集合：

   ```text
   running
   disconnected
   stopped
   failed
   ```

3. 不增加 `starting` 历史兼容解析逻辑。
4. 不修改 repository 做迁移；如果状态文件仍有 `starting`，Pydantic 加载失败是预期行为。

### 2. 调整 `create()`，不再构造 starting entry

文件：`src/termbridge/services.py`

1. `SessionService.create()` 创建 tmux window 后，构造 entry 草稿时不使用 `SessionStatus.STARTING`。
2. 草稿 entry 可使用 `SessionStatus.STOPPED` 作为内部初始值，因为它不会在 `_start_entry()` 成功前持久化。
3. `_start_entry()` 成功后返回 `SessionStatus.RUNNING` entry。
4. 成功后再把 running entry 写入 repository。
5. 失败时继续调用 `_cleanup_started_entry(workspace, entry)` 清理已创建的 tmux window / ttyd process。
6. 不引入对外可见的 starting 状态。

### 3. stopped entry 跳过 live refresh

文件：`src/termbridge/services.py`

1. `_refresh_entry()` 调整为：
   - `FAILED` 直接返回。
   - `STOPPED` 直接返回。
   - 仅 `RUNNING` / `DISCONNECTED` 进入 tmux window + ttyd port 检查。
2. `_refresh_entry_from_tmux_listing()` 调整为：
   - `FAILED` 直接返回。
   - `STOPPED` 直接返回。
   - `tmux_listing_unknown` 继续保守返回原 entry。
   - 仅 `RUNNING` / `DISCONNECTED` 使用批量 tmux listing 结果刷新。
3. `get()`、`terminal_proxy_target()` 仍调用 `_refresh_entry()`，因此 stopped entry 会被直接拒绝，不会因为历史 port 可连接而恢复 running。
4. `list_tree(refresh=true)` 批量刷新时不检查 stopped entry 的 tmux / ttyd。

### 4. 调整状态刷新字段规范化

文件：`src/termbridge/services.py`

1. `_refresh_entry_with_window_state()` 继续负责把 live 状态推导为：
   - tmux window exists + ttyd port available => `RUNNING`
   - tmux window exists + ttyd port unavailable => `DISCONNECTED`
   - tmux window missing => `STOPPED`
2. 状态不变时保持 no-op。
3. 状态变化时更新 `status` 和 `updated_at`。
4. refresh 降级到 `STOPPED` 时不清空 `tmux_window_id`。
5. refresh 降级到 `STOPPED` 时不依赖历史 `port` / `url` / `pid`；这些字段是否残留不影响 terminal proxy、UI 可用性或端口分配。
6. stop happy path 仍由 `_stop_entry()` 负责资源关闭后的 stopped 写入，保持现有清理语义。

### 5. 端口分配跳过 stopped entries

文件：`src/termbridge/services.py`

1. 修改 `_start_entry()` 的 `used_ports` 收集逻辑。
2. 仅把非当前 entry、非 stopped、port 非零的 session 当成业务占用：

   ```py
   used_ports = [
       item.port
       for _, item in self._repository.list_entries()
       if item.id != entry.id and item.status != SessionStatus.STOPPED and item.port
   ]
   ```

3. 保持 `PortAllocator.allocate()` 的 socket availability 检查不变，用于排除 OS 层面仍被占用的 orphan port。

### 6. 删除后端 starting 分支

文件：`src/termbridge/services.py`

1. `_workspace_response()` 删除 `SessionStatus.STARTING` 优先级。
2. 聚合优先级变为：

   ```text
   running > disconnected > failed > stopped
   ```

3. 删除 `_refresh_entry()` / `_refresh_entry_from_tmux_listing()` 中对 `SessionStatus.STARTING` 的跳过逻辑。
4. 搜索并删除其它 `SessionStatus.STARTING` 引用。

### 7. 前端类型和状态分支删除 starting

文件：

- `web/src/types/sessions.ts`
- `web/src/components/AppShell.vue`
- `web/src/components/SessionList.vue`
- `web/src/components/SessionTerminal.vue`
- `web/src/i18n/locales/en-US.json`
- `web/src/i18n/locales/zh-CN.json`

步骤：

1. `SessionStatus` union 删除 `'starting'`。
2. `AppShell.vue` 的 workspace 聚合删除 starting 判断。
3. `SessionList.vue` 删除业务状态 `session.status === 'starting'` 的可打开判断和颜色分支。
4. `SessionTerminal.vue` 不增加业务 starting 分支。
5. i18n 删除或停止引用 `session.status.starting`。
6. 保留 `startingSessionId`，因为它表示 start action pending，不是业务状态。

### 8. 实现 `/session` runtime state verified 管理

文件：

- `web/src/components/AppShell.vue`
- `web/src/components/SessionList.vue`
- `web/src/components/SessionTerminal.vue`
- `web/src/i18n/locales/en-US.json`
- `web/src/i18n/locales/zh-CN.json`

计划采用 AppShell 统一管理，不把 refresh gate 下沉到 `SessionTerminal`：

1. 在 `AppShell.vue` 增加状态：

   ```ts
   const sessionRuntimeStateVerified = ref(false)
   const sessionRuntimeStateRefreshing = ref(false)
   ```

   可以复用现有 `sessionStatusRefreshing`，但需要补充“是否已经成功完成 live refresh”的 verified 语义。不要只用 refreshing boolean 表示可信度，因为失败后 `refreshing=false` 但状态仍不可信。

2. `refresh()` 开始时把 `sessionRuntimeStateVerified` 设为 false。
3. `loadStoredSessions()` 应用 `refresh=false` 数据后保持 `sessionRuntimeStateVerified=false`。
4. `refreshLiveSessions()` 成功应用 live 数据后设置 `sessionRuntimeStateVerified=true`。
5. `refreshLiveSessions()` 失败时保持 `sessionRuntimeStateVerified=false`。
6. `SessionList.vue` 接收 runtime state 是否 verified 的 prop，用于：
   - 显示“状态检查中”。
   - 禁用 start / reconnect / stop / open terminal 等依赖 runtime 状态的按钮或点击行为。
   - 避免根据 cached status 显示 running/disconnected/stopped 的可用性样式。
7. `AppShell.vue` 的 open terminal 行为在未 verified 时拒绝打开旧 session：
   - 不把 session id 加入 `openTerminalSessionIds`。
   - 或者打开 terminal panel 但传入 `session` 为 undefined / 显示统一刷新状态。
   - 以不让 `SessionTerminal` 判断 cached status 为准。
8. `SessionTerminal.vue` 不接收 live refresh gate prop；它只处理传入的可信 sessions。
9. terminal 主区域在未 verified 且用户尚无 fresh operation session 时，由 `AppShell` 或父级布局显示“正在刷新会话状态”。如果现有结构必须复用 `SessionTerminal`，则传入空 sessions / no active session，而不是让它判断 session 是否可信。
10. create 成功返回的 fresh session 可立即局部更新并打开；这是 fresh operation response，不是 cached state。
11. start 操作本身从旧 session 触发，旧 session 未 verified 时禁用；verified 后 start 成功返回 running session，再按现有局部更新打开。
12. stop/delete 对旧 session 未 verified 时禁用；verified 后继续沿用现有局部响应更新。

### 9. 更新后端测试

文件：`tests/test_services.py`

更新或新增测试：

1. create 成功返回 `running`，且代码不再依赖 `SessionStatus.STARTING`。
2. `list_tree(refresh=true)` 对 stopped entry 不调用 ttyd port checker，不因历史 tmux_window_id / port 恢复为 disconnected/running。
3. `get()` 对 stopped entry 不做 live 恢复。
4. `terminal_proxy_target()` 对 stopped entry 直接拒绝。
5. running/disconnected entry：tmux exists + port open => running。
6. running/disconnected entry：tmux exists + port closed => disconnected。
7. running/disconnected entry：tmux missing => stopped，且不清空 `tmux_window_id`。
8. `_start_entry()` 端口分配跳过 stopped entry 的历史 port。
9. stopped 历史 port 被跳过时，如果 OS 层面实际占用该 port，`PortAllocator` 仍会跳过该 port。
10. workspace 聚合优先级为 `running > disconnected > failed > stopped`。

需要同步调整已有与新规则冲突的测试，例如“stopped entry with existing window promotes to disconnected”应改为“stopped entry is not live-refreshed”。

### 10. 更新前端检查覆盖

当前项目未从已读配置中确认有组件测试入口，因此本计划优先通过 typecheck / lint 验证前端行为约束。

如已有或后续发现前端测试框架，再补充组件测试：

1. `refresh=false` 数据应用后，session list 展示结构但 runtime 操作不可用。
2. live refresh 失败时，`sessionRuntimeStateVerified` 保持 false，cached status 不被当成可用状态。
3. live refresh 成功后，session list 和 terminal panel 使用 refreshed status。
4. 未 verified 时，点击旧 session 不会创建 terminal iframe 或打开 terminal session。
5. create 成功返回的 fresh session 可以通过局部响应打开。
6. start/stop/delete 在旧 session 未 verified 时不可触发；verified 后按现有局部响应更新。

## Files to change

### Process documents

- `docs/spec/20260617-session-runtime-state-consistency.md`
  - 已按用户决策标记 Accepted 并修正技术决策。
- `docs/plan/20260617-session-runtime-state-consistency.md`
  - 当前 Plan 文档。

### Backend

- `src/termbridge/models.py`
- `src/termbridge/services.py`
- `tests/test_services.py`

可能涉及：

- `tests/test_api.py`：如果 API schema/status 断言包含 starting。

### Frontend

- `web/src/types/sessions.ts`
- `web/src/components/AppShell.vue`
- `web/src/components/SessionList.vue`
- `web/src/components/SessionTerminal.vue`
- `web/src/i18n/locales/en-US.json`
- `web/src/i18n/locales/zh-CN.json`

## Verification plan

后端：

1. 定向服务测试：

   ```powershell
   uv run pytest tests/test_services.py
   ```

2. 后端全量测试：

   ```powershell
   uv run pytest
   ```

3. 后端 lint：

   ```powershell
   uv run ruff check src tests
   ```

4. 后端类型检查：

   ```powershell
   uv run mypy src
   ```

前端：

1. 类型检查：

   ```powershell
   npm --prefix web run typecheck
   ```

2. lint：

   ```powershell
   npm --prefix web run lint
   ```

3. 如需要覆盖构建链路：

   ```powershell
   npm --prefix web run build
   ```

手工检查建议：

1. 清理或确认 `.termbridge/sessions.json` 中不存在历史 `status="starting"`，因为本任务明确不做兼容。
2. 打开 `/session`，确认首屏可快速显示 session tree 结构。
3. 在 live refresh 未完成前，旧 session 显示“状态检查中”或等价不可用状态。
4. 在 live refresh 未完成前，旧 session 的 start / reconnect / stop / open terminal 不可用。
5. live refresh 成功后，真实 running session 可打开 iframe。
6. live refresh 失败时，cached `running/url` 不会打开 iframe，cached `disconnected/stopped` 不会显示可操作入口。
7. FastAPI 重启场景：tmux window 存在、ttyd 不存在时 live refresh 后显示 disconnected / 重连会话。
8. tmux/server 重启场景：tmux window 不存在时 live refresh 后显示 stopped / 启动会话。
9. create 成功后，无需重新拉 `/api/session-tree` 也能打开新返回的 running session。
10. verified 后 start/stop/delete 继续沿用现有局部响应更新。

## Assumptions

1. 本任务不负责清理历史 `status="starting"` 的本地状态文件。
2. stopped 历史 `port` / `url` / `tmux_window_id` 即使残留，也不会被 terminal proxy、端口分配或 UI runtime availability 判断使用。
3. `PortAllocator._is_available()` 能继续作为 OS 层面端口占用的最终保护。
4. 当前 `tmux_window_id + ttyd port` 的 live proxy 判断模型保持不变。
5. `startingSessionId` 继续表示前端 action loading，不属于业务 status。
6. `refresh=false` 的 cached status 不是前端 runtime availability 的输入，只是持久化结构中的字段。

## Risks

1. 不做历史 starting 兼容会让包含 `status="starting"` 的本地状态文件加载失败；这是用户确认的取舍，需要在验证前检查或清理测试数据。
2. stopped entry 不参与 refresh 后，历史 stopped 但资源仍存活的脏现场不会被自动恢复；这符合需求，但可能需要用户手工清理 orphan tmux/ttyd。
3. 如果只在 terminal iframe 处做 gate，会漏掉 start / reconnect / stop 等其它 runtime 操作；因此本计划要求在 `AppShell` / `SessionList` 层统一处理 runtime unavailable。
4. live refresh 失败时不能把 `refreshing=false` 误解为状态可信；必须单独维护 verified 语义。
5. create 返回 fresh running session 与 cached stale session 的可用性来源不同，实现时需要避免把“fresh operation response”误归类为未验证缓存数据。
6. 删除 starting union 后，前端所有 `session.status.*` 动态 i18n key 必须仍覆盖 remaining statuses。
7. 后端 refresh 降级 stopped 不清空 `tmux_window_id`，后续维护者可能误以为该字段仍可用于 stopped 业务判断；测试和注释应围绕“不依赖 stopped runtime fields”表达清楚。

## Rollback plan

如果实现后发现状态刷新或 UI unavailable 策略有严重回归：

1. 回退本任务的产品代码改动，恢复原 `starting` enum 和前端 union。
2. 保留过程文档中的设计讨论，不作为运行时代码依据。
3. 若仅前端 runtime unavailable 策略出现 UI 回归，可单独回退前端 verified-state 改动，后端状态模型改动不必一起回退。
4. 若仅后端状态模型导致历史数据加载问题，可按用户重新确认的策略再补充一次状态文件清理或兼容方案；当前 Plan 不主动实现该兼容。

## User review notes

- 用户确认 Spec，要求进入 Plan。
- 用户明确历史 `status="starting"` JSON 不做兼容或迁移。
- 用户明确 refresh 降级到 stopped 时不清空 `tmux_window_id`。
- 用户指出“状态没有 refresh 完是不可用的”，不希望 `SessionTerminal` 承担过多责任。
- 本 Plan 已调整为：`refresh=false` 仅用于结构展示；runtime state verified 由 `AppShell` 统一管理；未 verified 前旧 session runtime 操作不可用。
- 用户通过 `/specflow 开始实现` 接受 Plan 并进入 Implementation。