# 工作区中心的 tmux 会话模型计划

Review status: Accepted

当前：严格模式 / strict，计划阶段 / Plan

## Source documents

- Requirement: `docs/requirement/20260610-workspace-tmux-session-model.md`（Accepted）
- Spec: `docs/spec/20260610-workspace-tmux-session-model.md`（Accepted）

## Scope

本计划实现 TermBridge 的工作区中心 tmux 模型：

```text
运行环境
└── 工作目录 / workspace = tmux session
    └── 会话入口 / entry = managed tmux window
```

实施目标：

1. 后端不再使用用户输入名称作为 tmux session identity。
2. 同一 `host + workspace` 复用同一个 workspace tmux session。
3. 同一 workspace 下的会话入口映射到 managed tmux window。
4. 停止 entry 时保留 TermBridge record，但移除对应 managed tmux window。
5. 后端重启后不提供手动扫描入口，仅在用户点击 entry 时懒恢复。
6. 前端左侧导航改为环境 -> 目录 -> 会话入口的树型结构。
7. tmux window id/current window name 不在 UI 显式展示，仅作为内部诊断信息。

## Non-scope

1. 不自动导入用户手工创建的 tmux window。
2. 不支持同一 host + workspace 的第二个独立 workspace 实例。
3. 不设计 tmux pane/tabs。
4. 不提供手动“重新扫描 tmux 状态”入口。
5. 不把 TermBridge 或 ttyd 移入 WSL。
6. 不在 UI 中暴露 tmux window id/current window name。

## Implementation strategy

采用分层迁移，先建立后端模型和 tmux 命令能力，再调整 API 和前端树型导航。

推荐避免同时保留两套长期模型。新实现直接替换为 workspace/entry 模型；不向后兼容旧 flat `SessionRecord`，也不做数据迁移。

## Key decisions for implementation

1. **workspace identity**
   - 使用 `host + normalized_workspace_path` 作为逻辑 identity。
   - `workspace_id` 可由 `host + normalized_workspace_path` 的稳定 hash 派生。
   - `tmux_session_name` 使用安全前缀 + hash，例如 `tb_<host-short>_<hash>`。
   - hash 不需要可逆；诊断时通过 record 中的 host/workspace 反查。

2. **entry identity**
   - entry 保持独立 id，例如沿用 `sess_<uuid>` 形式或改名为 `entry_<uuid>`。
   - 用户输入 `name` 是 entry display name，不参与 tmux session identity。

3. **tmux window identity**
   - entry record 保存内部字段 `tmux_window_id`。
   - UI 不显示 window id/current name。
   - window id 失效时，entry 状态降级为 stopped/invalid；重启时写入新的 window id。

4. **list API shape**
   - 后端直接返回树型结构，前端只负责渲染和搜索过滤。
   - 理由：状态聚合和 workspace identity 属于后端语义，放在后端可减少前端重复推导。

5. **search**
   - 本阶段前端本地搜索即可。
   - 搜索保留树上下文，高亮/展开匹配节点及其祖先。
   - 后端搜索留作未来大量记录优化。

6. **legacy records**
   - 不向后兼容旧 flat `SessionRecord`。
   - 不做数据迁移。
   - 新代码可以假设持久化 session registry 使用新的 workspace/entry 结构。

## Implementation steps

### Step 1: Extend fastapi models

Files:

- `src/termbridge/models.py`
- `web/src/types/sessions.ts`（后续同步）
- Tests: `tests/test_services.py`

fastapi model direction:

- 增加 workspace response / entry response 类型：
  - workspace: id、host、path、display name、tmux session name、status、entries。
  - entry: id、name、shortcut id/name、status、url、created/updated、workspace id。
- 保留 `SessionResponse` 兼容现有 terminal area 选择逻辑，或将其收敛为 entry response。
- 增加内部持久字段：workspace id、workspace tmux session name、tmux window id。
- tmux window id/current name 不进 UI response，除非作为内部 debug-only 字段且前端不使用。

Test scenarios:

1. 同 host + 同 workspace 生成同一个 workspace id/tmux session name。
2. 同 host + 不同 workspace 生成不同 tmux session name。
3. 不同 host + 同 workspace 文本生成不同 workspace id。
4. 新 session registry 使用 workspace/entry 结构保存和读取。

### Step 2: Add tmux workspace/window command primitives

Files:

- `src/termbridge/services.py`
- Tests: `tests/test_terminal_service.py`

在 `TerminalService` 中拆出 host-aware tmux 操作能力，而不是只返回 `tmux new-session -A -s <session> <command>`：

- ensure workspace tmux session exists。
- create managed window in workspace tmux session and capture window id。
- attach/switch to existing window。
- kill managed window。
- check session/window exists。
- kill workspace session。

命令语义方向：

- Cygwin/Linux：通过 shell `-lc` 执行 tmux command；需要保留 workspace `cd`。
- WSL：继续使用 `wsl --cd <Windows path> sh -lc <tmux command>`。
- 创建 window 后需要从 tmux 输出捕获 window id；Plan 阶段允许实现时选择 `tmux new-window -P -F '#{window_id}' ...` 或等价命令。

Test scenarios:

1. Cygwin workspace session name 不来自用户 display name。
2. WSL 命令使用 `wsl --cd <Windows path>`，不调用 `wslpath`。
3. Linux 命令在 workspace 中创建/连接 tmux session/window。
4. 创建 window 命令返回并记录 window id。
5. kill entry 只 kill window，不 kill workspace session。
6. kill workspace session 只在 workspace 删除或无保留 entry 时触发。

### Step 3: Refactor SessionService lifecycle around workspace/entry

Files:

- `src/termbridge/services.py`
- `src/termbridge/repositories.py`
- Tests: `tests/test_services.py`

Create flow:

1. 校验 workspace path。
2. resolve shortcut 和 host readiness。
3. resolve or create workspace record for `host + workspace`。
4. ensure workspace tmux session。
5. create managed window for entry。
6. start ttyd attach command targeting workspace session/window。
7. persist entry record with stopped/running state, ttyd pid/port/url, shortcut metadata, internal window id。

Select/reconnect flow:

1. 如果 ttyd process running：返回现有 url。
2. 如果 ttyd stopped 但 tmux window exists：创建 ttyd attach process，不重启 shortcut command。
3. 如果 tmux window missing：entry remains stopped；restart creates new window。
4. 如果 workspace tmux session missing：restart recreates workspace session and window。

Stop flow:

1. terminate ttyd process if running。
2. kill managed tmux window if present。
3. keep TermBridge entry record。
4. mark entry stopped and clear pid/port/url/window id as appropriate。

Delete entry flow:

1. terminate ttyd process if running。
2. kill managed tmux window if present。
3. delete entry record。
4. if workspace has no remaining entries needing preserved state, kill workspace tmux session and remove workspace record if appropriate。

Restart flow:

1. if entry running: no-op or return current entry。
2. ensure workspace tmux session。
3. create new managed window using original shortcut。
4. start ttyd attach。
5. update entry with new window id/pid/port/url/status。

Test scenarios:

1. Creating second entry in same host/workspace reuses workspace tmux session name。
2. Same display name in different workspaces does not reuse tmux session。
3. Restart stopped entry creates new window and keeps same entry record。
4. Stop entry keeps record and kills only window。
5. Delete last entry kills workspace tmux session。
6. Delete one of multiple entries does not kill workspace tmux session。
7. fastapi restart simulated by missing process adapter state: click/select reconnects if window exists。
8. Missing window yields stopped state until restart。
9. Missing workspace session recreates on restart。

### Step 4: Adjust API semantics

Files:

- `src/termbridge/api.py`
- `web/src/api/sessions.ts`
- Tests: existing API tests if present; otherwise add service-level coverage and keep API thin.

API direction:

- `GET /api/sessions` may either be replaced by or complemented with a tree response.
- Prefer a new tree endpoint or evolved response that front-end can consume directly:
  - environments
  - workspaces
  - entries
- Preserve create/restart/delete endpoints as entry-level operations where possible to limit web churn。
- Add stop entry endpoint if current delete/restart semantics are insufficient:
  - `POST /api/sessions/{entry_id}/stop`
- Reconnect can be implemented as select/get/restart behavior depending on endpoint design, but must not restart shortcut command when window exists。

Test scenarios:

1. Create returns entry with workspace grouping metadata。
2. List returns environment/workspace/entry tree。
3. Stop endpoint keeps entry visible as stopped。
4. Delete endpoint removes entry and cleans window。
5. Restart endpoint recreates missing window。

### Step 5: Build web tree navigation

Files:

- `web/src/components/SessionList.vue`
- `web/src/components/SessionCard.vue` or replacement entry component
- `web/src/App.vue`
- `web/src/types/sessions.ts`
- `web/src/api/sessions.ts`
- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`

Implementation direction:

- Replace flat `SessionCard` list with a tree view using existing styling and Reka UI Tree if practical.
- Tree levels:
  1. environment label。
  2. workspace directory display name/path。
  3. entry display name + shortcut/status/actions。
- Keep selected entry behavior: clicking entry shows terminal/attaches/reconnects according to fastapi state。
- Add search input above tree; filter by environment, workspace path/name, entry name, shortcut name。
- Preserve existing create button, settings menu, collapsed sidebar behavior。
- Do not show tmux window id/current window name。

Test/manual scenarios:

1. Empty state with no ready environment remains understandable。
2. Multiple entries under same workspace appear grouped。
3. Same entry names under different workspaces are distinguishable by tree context。
4. Searching workspace path expands matching ancestors。
5. Clicking entry while create panel is open closes create panel and shows terminal。
6. Stopped entry shows restart action。
7. Stop action keeps entry visible as stopped。

### Step 6: Update terminal display and actions

Files:

- `web/src/components/SessionTerminal.vue`
- `web/src/App.vue`
- i18n locale files

Implementation direction:

- Treat active item as entry, not flat session。
- Keep terminal iframe/url behavior for running entries。
- For stopped/invalid entries, show action based on state: reconnect if only ttyd lost, restart if window missing/session missing。
- Stop action should be explicit and separate from delete。
- Delete dialog copy should clarify entry deletion vs workspace termination where relevant。

Test/manual scenarios:

1. Running entry renders iframe。
2. Stopped entry renders restart CTA。
3. Connection-lost entry renders reconnect CTA if fastapi exposes that state。
4. Delete copy does not imply killing the entire workspace unless it is last entry/workspace delete。

### Step 7: Documentation cleanup

Files:

- `docs/spec/20260609-tmux-session-persistence.md`
- `docs/spec/20260610-windows-wsl-runtime-support.md`
- Possibly README if user-facing behavior is documented there。

Implementation direction:

- Add note that older per-session tmux persistence design is superseded by workspace tmux session + managed window model。
- Ensure WSL docs say Windows path is passed through `wsl --cd <Windows path>`。

## Verification plan

fastapi commands:

- `python -m pytest tests/test_terminal_service.py tests/test_services.py -q`
- `python -m pytest -q`
- `python -m ruff check src tests`
- `python -m mypy src`

web commands:

- `yarn --cwd web typecheck`
- `yarn --cwd web lint`
- `yarn --cwd web format:check`
- `yarn --cwd web build`

Manual UI verification:

1. Start dev server or packaged web according to current project workflow。
2. Create entries in same environment + same directory with different shortcuts; verify tree grouping。
3. Create same display name in different directories; verify separate workspace nodes and no cross attach。
4. Stop an entry; verify record remains and tmux window is removed。
5. Restart stopped entry; verify new window is created and terminal opens。
6. Delete one entry in multi-entry workspace; verify workspace remains。
7. Delete last entry; verify workspace session cleanup behavior。
8. Restart fastapi; click existing entry; verify lazy recovery/reconnect behavior。
9. Search by path fragment, environment, shortcut, entry name。

## Rollback plan

- Since state model changes are significant, keep implementation in small commits or reviewable patches。
- If workspace model breaks create/list, revert fastapi model/API changes together with web type changes。
- If tree UI proves unstable, temporarily render tree response as grouped sections without Reka Tree while preserving fastapi workspace semantics。
- Keep old flat record read compatibility until the new model has been verified against existing local `.termbridge` state。

## Risks

1. tmux command quoting and window-id capture may differ across Cygwin/WSL/Linux。
2. Old flat session data may not contain enough tmux window information; treat as stopped/unknown rather than guessing。
3. Status naming may need more nuance than current `starting/running/stopped/failed`。
4. web tree migration can become large; avoid redesigning unrelated layout。
5. Lazy recovery means list status can be stale until user clicks an entry。
6. File repository migration must avoid corrupting existing `sessions.json`。

## Open implementation decisions

1. Exact model names: whether to introduce `WorkspaceRecord`/`SessionEntryRecord` or evolve `SessionRecord` with workspace fields。
2. Exact API shape: new `/api/session-tree` endpoint vs evolving `GET /api/sessions`。
3. Exact tmux command sequence for create window + capture id + attach/switch。
4. Exact status enum expansion for connection lost/window missing/workspace missing。

These are implementation-owned decisions and should be resolved in Plan review or early implementation before editing product code.

## User review notes

- 用户要求开始 Plan。
- 用户确认不在 UI 中显式展示 tmux window id/current window name。
- 用户确认后端重启后不提供手动扫描入口，只在点击 entry 时懒恢复。
