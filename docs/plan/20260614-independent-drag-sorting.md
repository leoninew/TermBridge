# 独立拖动排序能力计划

- Flow mode: standard
- Stage: Plan
- Review status: Accepted
- Date: 2026-06-14

## Requirement Basis

- `docs/requirement/20260614-independent-drag-sorting.md`
- Requirement status: Accepted

## Goal

新增 3 块互不干扰的拖动排序能力：

1. 特定环境下的目录列表排序。
2. 特定目录下的会话列表排序。
3. 终端 tab 页头排序。

目录和会话排序通过 `.termbridge/sessions.json` 的现有有序结构持久化；不新增独立 session storage，也不通过额外排序字段表达顺序。终端 tab 排序仅保存在当前前端状态中，无需持久化。

## Implementation Steps

1. 新增前端拖拽依赖
   - 在 `web/package.json` 增加 `vue-draggable-plus`。
   - 更新 `web/yarn.lock`。
   - 在 Vue 组件中按库约定导入 draggable 组件。

2. 后端增加排序请求模型
   - 在 `src/termbridge/models.py` 新增目录排序请求，例如 `ReorderWorkspacesRequest`，字段为有序 `workspace_ids: list[str]`。
   - 新增会话排序请求，例如 `ReorderSessionsRequest`，字段为有序 `session_ids: list[str]`。
   - 请求只表达当前排序区域内的完整 id 列表，不表达跨区域移动。

3. 后端 repository 按 `.termbridge/sessions.json` 现有顺序结构重排
   - 在 `src/termbridge/repositories.py` 为 `FileSessionRepository` 增加目录排序写入能力。
   - 目录排序通过重建 `SessionState.workspaces` 字典的插入顺序实现，限定在指定 host 的 workspace 子集内；其他 host 和未参与排序的 workspace 保持原相对顺序。
   - 在同一 workspace 内会话排序通过重建 `WorkspaceRecord.entries` list 顺序实现。
   - 写回仍走现有 `_write_state()` / `_encode_state()`，让 `.termbridge/sessions.json` 中 `environments[host]` 下的 workspace object 顺序，以及每个 workspace 的 `sessions` object 顺序反映用户排序。
   - 不新增 `sort_order`、`position` 或单独排序 storage。

4. 后端 service/API 增加排序入口
   - 在 `src/termbridge/services.py` 的 `SessionService` 增加目录排序方法，例如 `reorder_workspaces(host, workspace_ids)`。
   - 该方法校验：所有 id 都存在、都属于指定 host、请求 id 集合与该 host 当前 workspace 集合一致；失败时返回 400/404 类型错误，避免跨环境移动或丢失目录。
   - 增加会话排序方法，例如 `reorder_sessions(workspace_id, session_ids)`。
   - 该方法校验：workspace 存在、所有 session id 都属于该 workspace、请求 id 集合与当前 entries 集合一致；失败时返回 400/404 类型错误，避免跨目录移动或丢失会话。
   - 在 `src/termbridge/api.py` 增加两个接口，例如：
     - `PUT /api/session-tree/environments/{host}/workspaces/order`
     - `PUT /api/session-workspaces/{workspace_id}/sessions/order`
   - 接口返回更新后的 `SessionTreeResponse` 或对应 workspace/tree 结果，前端可用来刷新本地树。

5. 前端 API 和类型补齐
   - 在 `web/src/types/sessions.ts` 增加排序 payload 类型。
   - 在 `web/src/api/sessions.ts` 增加：
     - `reorderEnvironmentWorkspaces(host, workspaceIds)`
     - `reorderWorkspaceSessions(workspaceId, sessionIds)`
   - API 方法使用 JSON body 提交当前区域的完整有序 id 列表。

6. `AppShell.vue` 承接持久化排序
   - 将排序事件从 `SessionList.vue` 向上抛到 `AppShell.vue`。
   - `AppShell.vue` 调用对应 API，成功后用返回结果或 `loadSessions()` 刷新 `sessionTree` / `sessions`。
   - 排序失败时显示 toast，并重新加载 session tree 还原到后端真实顺序。
   - 不把目录/会话排序状态另存在前端 store；以 `.termbridge/sessions.json` 返回顺序为准。

7. `SessionList.vue` 实现目录和会话拖动排序
   - 保持当前“固定环境分组 + 目录/会话树”信息架构。
   - 对每个环境分组下的 workspace 第一层使用 draggable，group 配置禁止跨环境拖动。
   - 对每个 workspace 下的 session 列表使用 draggable，group 配置禁止跨 workspace 拖动。
   - 拖动结束后只 emit 当前区域完整有序 id 列表：
     - 目录：`reorderWorkspaces(host, workspaceIds)`
     - 会话：`reorderSessions(workspaceId, sessionIds)`
   - 事件处理要隔离点击选择和拖动排序：拖动 session 不应触发 `select`，点击 session 仍应选择/打开。
   - 保持目录 hover 新建/删除按钮、会话启动/停止/删除按钮可点击；通过按钮过滤和事件隔离避免操作按钮区域误拖。
   - 保持目录 label basename/消歧、完整路径 tooltip、完整路径搜索和 active session 选中态。
   - 如果 draggable 与 Reka `TreeRoot` 的 flatten 渲染模型冲突，优先改为显式渲染两层结构：环境分组下 draggable workspace list，workspace 展开区域内 draggable session list；保留现有视觉和必要的展开状态，而不是强行把 draggable 包在 `TreeRoot` flatten items 上。

8. `SessionTerminal.vue` 实现 tab 页头拖动排序
   - 对已打开的 `sessions` tab 列表使用 draggable；“新建会话”加号 tab 不参与排序，固定在末尾。
   - 拖动结束后 emit 新的 open terminal session id 顺序，例如 `reorderTabs(sessionIds)`。
   - `AppShell.vue` 仅更新 `openTerminalSessionIds` 的当前前端顺序，不调用后端持久化。
   - active tab 使用 session id 保持不变；拖动后仍激活同一个 session。
   - 保留关闭按钮点击隔离，避免拖动或关闭误触发 tab 选择。

9. 测试与兼容性
   - 为 repository/service 增加目录排序和会话排序测试，覆盖：正常重排、跨 host/workspace id 拒绝、缺失 id/多余 id 拒绝、写回后读取顺序保持。
   - 为 API 增加排序接口测试，覆盖成功和错误输入。
   - 前端通过 lint/typecheck 覆盖新增 props/emits/API 类型和 draggable 引入。

## Files to Change

- `web/package.json`
  - 新增 `vue-draggable-plus` 依赖。

- `web/yarn.lock`
  - 更新依赖锁定。

- `src/termbridge/models.py`
  - 新增目录/会话排序请求模型。

- `src/termbridge/repositories.py`
  - 在 `FileSessionRepository` 中新增基于现有 ordered JSON 结构的 workspace/session 重排方法。

- `src/termbridge/services.py`
  - 在 `SessionService` 中新增排序校验和调用 repository 的服务方法。

- `src/termbridge/api.py`
  - 新增目录排序和会话排序 HTTP API。

- `web/src/types/sessions.ts`
  - 新增排序 payload 类型。

- `web/src/api/sessions.ts`
  - 新增排序 API client 方法。

- `web/src/components/AppShell.vue`
  - 接收 `SessionList` / `SessionTerminal` 排序事件，调用 API 或更新 tab 顺序。

- `web/src/components/SessionList.vue`
  - 引入 draggable，实现环境内目录排序和目录内会话排序。

- `web/src/components/SessionTerminal.vue`
  - 引入 draggable，实现 terminal tab 排序；create tab 固定末尾。

- `tests/test_session_repository.py`
  - 增加 `.termbridge/sessions.json` 顺序写回/读取测试。

- `tests/test_services.py`
  - 增加 `SessionService` 排序校验和结果测试。

- `tests/test_api.py`
  - 增加排序接口测试。

## Verification Plan

1. 依赖和静态检查
   - `yarn --cwd web install` 或项目当前约定的 yarn 安装命令，用于更新 `web/yarn.lock`。
   - `npm --prefix web run lint`
   - `npm --prefix web run typecheck`

2. 后端测试
   - `uv run pytest tests/test_session_repository.py tests/test_services.py tests/test_api.py`
   - 如相关改动影响更广，再运行 `uv run pytest`。

3. 手动 UI 验证：目录排序
   - 打开 `/session`。
   - 在同一个环境分组下拖动目录。
   - 确认目录只在当前环境内重排，不能拖到其他环境。
   - 刷新页面或重新加载 session tree 后，确认目录顺序保持。
   - 检查 `.termbridge/sessions.json` 中对应 `environments[host]` 下 workspace object 的顺序发生变化。

4. 手动 UI 验证：会话排序
   - 在同一个目录下拖动会话。
   - 确认会话只在当前目录内重排，不能拖到其他目录。
   - 刷新页面或重新加载 session tree 后，确认会话顺序保持。
   - 检查 `.termbridge/sessions.json` 中对应 workspace 的 `sessions` object 顺序发生变化。

5. 手动 UI 验证：终端 tab 排序
   - 打开多个 terminal tab。
   - 拖动 tab 页头重排。
   - 确认 active tab 仍是同一个 session。
   - 确认关闭按钮、新建 tab 加号仍可用，且加号固定在末尾。
   - 刷新页面后无需保持 tab 顺序。

6. 回归验证
   - 点击左侧 session 仍能打开/激活终端。
   - 目录新建/删除按钮仍可用。
   - 会话启动/停止/删除按钮仍可用。
   - 搜索完整路径仍能过滤目录。
   - 浅色/暗色主题下拖动反馈可读。

## Risks

1. `vue-draggable-plus` 与 Reka `TreeRoot` 的 flatten item 渲染可能不自然；Plan 采用“必要时显式渲染两层结构”的兜底，避免拖拽库和树组件争夺 DOM 顺序。
2. `.termbridge/sessions.json` 使用 JSON object 顺序承载 workspace/session 顺序；Python 和浏览器当前都保持对象插入顺序，但实现必须避免无意按 key 排序。
3. 用完整 id 列表提交排序可以避免跨区域移动，但前后端都要严格校验集合一致性，否则可能误删或遗漏条目。
4. 拖动手势可能与行内按钮冲突；实现时应使用按钮过滤或事件保护，优先保证现有按钮操作不倒退。
5. 安装新依赖会改动 lockfile；需要确保包管理器与项目现有 yarn 工作流一致。

## Rollback

如果拖动排序引入交互不稳定或依赖兼容问题，可以：

1. 回退前端 draggable 集成和 `vue-draggable-plus` 依赖。
2. 保留或删除后端排序 API；如果 API 已合入但前端暂不使用，必须确保不影响现有 session tree 返回顺序。
3. `.termbridge/sessions.json` 不需要迁移回滚，因为本方案不新增字段，只改变 object/list 顺序。

## User Review Notes

- 2026-06-14: 用户要求进入 Plan / 计划阶段，并澄清目录和会话排序使用 `.termbridge/sessions.json` 持久化，tab 排序无需持久化。
- 2026-06-14: 用户进一步澄清 `.termbridge/sessions.json` 本身就是有序的，和 session storage 无关；计划已按“重排现有 JSON 顺序，不新增排序字段或额外 storage”处理。
- 2026-06-14: 用户要求进入 Implementation / 实现阶段，Plan 已更新为 Accepted。
