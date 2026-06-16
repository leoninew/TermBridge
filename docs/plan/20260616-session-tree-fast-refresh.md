# session-tree 快速刷新与批量状态检查计划
最后修改时间: 2026-06-16 22:48:19

- Flow mode: strict
- Stage: Plan
- Review status: Draft
- Date: 2026-06-16

## Requirement / Spec basis

- Requirement: `docs/requirement/20260616-session-tree-fast-refresh.md`，Review status: Accepted
- Spec: `docs/spec/20260616-session-tree-fast-refresh.md`，Review status: Accepted

本计划按已接受的规格实施：

1. `GET /api/session-tree` 默认保持真实刷新。
2. `GET /api/session-tree?refresh=false` 快速返回持久化记录，不做 tmux / ttyd 检查。
3. 前端初始加载先用 `refresh=false`，快速记录返回前显示覆盖完整页面的遮挡层。
4. 快速记录返回后调用无 query `GET /api/session-tree` 进行真实状态刷新。
5. 真实刷新使用原始 `tmux list-windows -a` 输出，不使用 `-F`。
6. `tmux list-windows -a` 在 runtime home 目录执行，不选择 workspace path 作为 cwd。
7. 用输出第一个冒号前字段匹配 `workspace.tmux_session_name`，再匹配 window / entry 名称。
8. tmux list 命令真正失败时保守保留旧状态，不误降级为 `stopped`。
9. `tmux list-windows -a` 返回 `no server running ...` 且退出码为 1 时，视为“当前没有 tmux windows”的正常空列表，不视为未知失败。
10. 状态变化继续逐 entry 更新 repository。

## Implementation steps

### 1. 后端 API 增加 refresh query

文件：`src/termbridge/api.py`

1. 修改 `list_session_tree()` route：

   ```python
   @router.get("/api/session-tree", response_model=SessionTreeResponse)
   def list_session_tree(service: SessionServiceDep, refresh: bool = True) -> SessionTreeResponse:
       return service.list_tree(refresh=refresh)
   ```

2. 保持无 query 行为为 `refresh=True`。
3. 不新增 `/api/session-tree/status` endpoint。

### 2. SessionService 拆分快速路径和真实刷新路径

文件：`src/termbridge/services.py`

1. 修改 `SessionService.list_tree()` 签名为：

   ```python
   def list_tree(self, *, refresh: bool = True) -> SessionTreeResponse:
   ```

2. `refresh=False` 时：
   - 直接读取 `self._repository.list_workspaces()`。
   - 不调用 `_refresh_workspaces()`。
   - 不调用 tmux 批量 list。
   - 不调用 `_ttyd_port_checker()`。
   - 不更新 repository。

3. 将现有构建 `SessionTreeResponse` 的逻辑提取为 helper，例如：

   ```python
   def _tree_response(self, workspaces: list[WorkspaceRecord]) -> SessionTreeResponse:
   ```

4. `list_sessions()`、`get()`、`start()` 等现有路径仍保持真实刷新语义，不引入 `refresh=false`。

### 3. TerminalService 增加 home 目录 tmux list 能力

文件：`src/termbridge/services.py`

1. 增加数据结构，例如：

   ```python
   @dataclass(frozen=True)
   class TmuxWindowListing:
       tmux_session_name: str
       window_index: str
       window_name: str
   ```

2. 增加异常或内部错误表达，例如：

   ```python
   class TmuxListWindowsError(Exception):
       pass
   ```

   如果项目中已有合适异常，也可使用内部 helper 返回 failure marker，避免扩大公开异常面。

3. 增加方法：

   ```python
   def list_tmux_windows(self, host: ShortcutHost) -> list[TmuxWindowListing]:
   ```

4. 命令执行：
   - Cygwin：`[bash_path, "-lc", "tmux list-windows -a"]`，不 `cd` workspace。
   - WSL：使用 WSL 的 home 目录执行，不传 workspace path；可采用 `wsl sh -lc "tmux list-windows -a"`。
   - Linux：`[shell_path, "-lc", "tmux list-windows -a"]`。
   - Windows/Cygwin 仍使用 `runtime_process_env(host)` / `_cygwin_process_env()` 保持环境一致。
   - timeout 沿用当前 `tmux_command_timeout_seconds`。
   - 如果退出码为 1 且 stderr/stdout 包含 `no server running`，按空 tmux window 列表处理，表示当前没有 tmux server / 没有可恢复窗口。

5. 不复用当前 `_runtime_shell_command(host, workspace, command)`，因为该方法要求 workspace，并且 WSL 分支会拼 `wsl --cd <workspace>`。
   - 可新增 `_runtime_home_shell_command(host, command)`。
   - 或新增 `_run_tmux_command_in_home(host, command)`，内部直接调用 subprocess。

### 4. 解析原始 tmux list-windows 输出

文件：`src/termbridge/services.py`

1. 增加 parser helper，例如：

   ```python
   def parse_tmux_window_line(line: str) -> TmuxWindowListing | None:
   ```

2. 输入示例：

   ```text
   tb_cyg_3d134fa1d1d50ef3:0: 特性开发* (1 panes) [230x54]
   ```

3. 解析策略：
   - 用前两个冒号切分：`session_name`, `window_index`, `rest`。
   - `session_name` 直接匹配 `workspace.tmux_session_name`。
   - `window_index` 保留备用。
   - `rest` 提取 window name：
     - 去掉首尾空白。
     - 去掉末尾 pane/layout 描述，例如 ` (1 panes) [230x54]`。
     - 去掉 tmux window active/previous marker，例如末尾 `*`、`-`。
   - 得到 `window_name` 后用于匹配 `entry.name`。

4. 如果单行无法解析：
   - 记录 warning。
   - 建议忽略该行，不让单个异常行导致整个 host 状态未知。
   - 如果全部输出都无法解析或命令失败，才按 host 状态未知处理。

### 5. 批量刷新状态

文件：`src/termbridge/services.py`

1. 修改 `_refresh_workspaces()`：
   - 先按 host 收集有 entries 的 workspaces。
   - 每个 host 调用一次 `terminal_service.list_tmux_windows(host)`。
   - 成功时得到 listing index。
   - `no server running` 场景得到空 listing index，host 仍是 known。
   - 其他失败时记录该 host 为 unknown。

2. listing index 建议结构：

   ```python
   dict[ShortcutHost, dict[str, set[str]]]
   # host -> tmux_session_name -> window_names
   ```

3. 修改 `_refresh_workspace()` / `_refresh_entry()`：
   - `_refresh_entry()` 接收该 workspace 所属 host 的 listing 状态。
   - `starting` / `failed` 不刷新。
   - host unknown：直接返回原 entry，不检查 ttyd，不更新 repository。
   - host known：
     - `tmux_window_exists = entry.name in window_names_by_session.get(workspace.tmux_session_name, set())`
     - window 不存在：状态变为 `stopped`，`pid=None`，`url=""`，`tmux_window_id=None`，跳过 ttyd。
     - window 存在：仅此时检查 `_ttyd_port_checker(entry.port)`。
       - true => `running`，`url=self._build_url(entry.id)`。
       - false => `disconnected`，`pid=None`，`url=""`，保留 `tmux_window_id`。

4. 逐 entry 更新 repository：
   - 沿用当前 `_refresh_entry()` 内部 `self._repository.update_entry(updated)` 的方式。
   - 不做 workspace 级批量保存。

5. 注意 start/get 路径：
   - `get()` 仍可调用 `_refresh_entry()`；如果没有批量 listing 上下文，Plan 建议保留单 entry fallback 或让 `get()` 使用当前单 entry 检查。
   - 为控制范围，可以将批量刷新只用于 `_refresh_workspaces()` / `list_tree()`，保留 `get()`、`terminal_proxy_target()`、`start()` 对 `_refresh_entry()` 的现有单 entry 检查语义。
   - 若实现上统一 `_refresh_entry()` 签名，应提供兼容 wrapper，避免影响启动/重连逻辑。

### 6. 前端 API helper 支持 refresh 参数

文件：`web/src/api/sessions.ts`

1. 修改：

   ```ts
   export function listSessionTree(options?: { refresh?: boolean }): Promise<SessionTreeResponse>
   ```

2. URL 规则：
   - 无参数：`/api/session-tree`
   - `refresh: true`：可继续 `/api/session-tree`
   - `refresh: false`：`/api/session-tree?refresh=false`

3. 不影响 reorder endpoints。

### 7. AppShell 双阶段加载和全页面遮挡

文件：`web/src/components/AppShell.vue`

1. 新增状态：

   ```ts
   const initialSessionTreeLoading = ref(false)
   const sessionStatusRefreshing = ref(false)
   ```

2. 调整 `refresh()`：
   - 设置 `initialSessionTreeLoading=true`。
   - 并行执行 `listSessionTree({ refresh: false })` 和 `environmentStore.ensureLoaded()`。
   - 快速记录加载成功后 `applySessionTree()`。
   - 在 finally 中 `initialSessionTreeLoading=false`。
   - 然后调用无 query `listSessionTree()` 真实刷新。

3. 真实刷新：
   - 设置 `sessionStatusRefreshing=true`。
   - 成功后 `applySessionTree()`。
   - 失败时 toast，保留快速记录视图。
   - finally 设置 `sessionStatusRefreshing=false`。

4. 对 `SessionList` 的 `loading` prop：
   - 使用 `sessionStatusRefreshing` 或兼容表达；用户已采纳“新增内部状态，但对 SessionList 复用现有 loading prop”。
   - 遮挡层不依赖 `sessionStatusRefreshing`。

5. 新增全页面遮挡层：
   - 放在 `<main>` 内，使用 fixed/absolute 覆盖 viewport。
   - `v-if="initialSessionTreeLoading"`。
   - z-index 高于 sidebar、create panel、terminal。
   - 显示 spinner 和 i18n 文案。

6. 如果 `refresh=false` 失败且本地没有任何记录：
   - 设置 `error`。
   - 移除遮挡，显示现有错误状态。
   - 不继续真实刷新，避免重复错误提示。

### 8. i18n 文案

文件：

- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`

新增文案建议：

- `app.loading.restoreSessions`: `正在恢复会话...`
- `app.loading.restoreSessions`: `Restoring sessions...`

也可放在 `session.list.restoring`，实施时按现有 JSON 结构选择最小改动。

### 9. 后端测试

文件：`tests/test_api.py`

1. 修改 `FakeSessionService.list_tree()` 支持 `refresh: bool = True` 参数。
2. 增加断言：
   - `GET /api/session-tree` 调用 `list_tree(refresh=True)`。
   - `GET /api/session-tree?refresh=false` 调用 `list_tree(refresh=False)`。

文件：`tests/test_services.py`

1. 扩展 `FakeShortcutService`：
   - 增加 `list_tmux_windows(host)`。
   - 记录调用次数，验证批量调用。
   - 支持模拟失败。

2. 增加测试：
   - `list_tree(refresh=False)` 不调用 tmux list、不调用 ttyd checker、不更新状态。
   - `list_tree()` 对多个 session 只调用一次 tmux list（按 host）。
   - tmux list 显示 window 不存在时跳过 ttyd checker，并将 entry 更新为 `stopped`。
   - tmux list 显示 window 存在且 ttyd 可用 => `running`。
   - tmux list 显示 window 存在但 ttyd 不可用 => `disconnected`。
   - tmux list 真正失败时保留旧状态、不检查 ttyd、不清空 `tmux_window_id`。
   - tmux list 输出 `no server running ...` 且退出码为 1 时按空列表处理，已有 entry 应刷新为 `stopped` 且跳过 ttyd。
   - parser 能解析用户提供的输出格式，并清洗 `*` marker 和 pane/layout 描述。

### 10. 前端检查

当前项目未看到现成前端单元测试配置。实施后通过项目脚本验证：

- `npm run lint`（在 `web/`）
- `npm run typecheck`（在 `web/`）
- `npm run build`（在 `web/`，如果时间允许）

后端通过：

- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy src tests`

## Files to change

### Product code

- `src/termbridge/api.py`
- `src/termbridge/services.py`
- `web/src/api/sessions.ts`
- `web/src/components/AppShell.vue`
- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`

### Tests

- `tests/test_api.py`
- `tests/test_services.py`

### Process docs

- `docs/plan/20260616-session-tree-fast-refresh.md`
- 后续 Verification 阶段创建：`docs/verification/20260616-session-tree-fast-refresh.md`

## Verification plan

1. 后端行为验证：
   - `GET /api/session-tree?refresh=false` 不触发真实检查。
   - `GET /api/session-tree` 仍触发真实检查。
   - 批量 tmux list 替代 list tree 中逐 session `tmux_window_exists()`。
   - window 不存在时跳过 ttyd checker。
   - tmux list 真正失败时保守保留旧状态。
   - tmux list 返回 `no server running` 时按空窗口列表处理。

2. 前端行为验证：
   - 初始加载请求 `refresh=false`。
   - `refresh=false` 完成前出现全页面遮挡层。
   - 遮挡层在快速记录返回后消失，不等待真实刷新。
   - 真实刷新失败不清空已加载记录。

3. 命令验证：
   - `uv run pytest`
   - `uv run ruff check .`
   - `uv run mypy src tests`
   - `cd web && npm run lint`
   - `cd web && npm run typecheck`
   - `cd web && npm run build`（如果 lint/typecheck 已通过且时间允许）

## Blockers

暂无实现阻塞项。

## Assumptions

1. `tmux list-windows -a` 默认输出格式稳定为：`<tmux_session_name>:<window_index>: <window_name...>`。
2. `workspace.tmux_session_name` 与输出第一个冒号前字段一致。
3. entry/window 名称可通过清洗默认输出后匹配 `entry.name`。
4. 单个 host 下执行一次 `tmux list-windows -a` 能看到该 host 下所有相关 workspace tmux sessions/windows。
5. `no server running on /tmp/tmux-.../default` 且退出码为 1 是 tmux 无 server 的正常空状态，而不是命令异常。
6. 前端没有现成单元测试时，以 lint/typecheck/build 作为本轮前端验证主路径。

## Risks

1. 默认 tmux 输出解析比 `-F` 更脆弱；需要集中封装 parser 并加测试覆盖用户给出的样例。
2. 如果 window name 与 `entry.name` 不完全一致，可能误判为 stopped；实现时应尽量复用已有创建 window 时的名称规则。
3. tmux list 真正失败时保留旧状态可能让 UI 短时间展示过期状态，但这是避免误降级的有意权衡。
4. 必须区分 `no server running` 和真正失败；前者应刷新为无窗口状态，不能保守保留旧状态。
5. WSL home 目录执行命令的参数需要小心，不应继续使用 `wsl --cd <workspace>`。
5. 前端双阶段加载需要避免重复 toast 或无限 loading。

## Rollback

如实现后出现问题，可回滚到当前行为：

1. 前端 `listSessionTree()` 恢复固定请求 `/api/session-tree`。
2. `AppShell.refresh()` 恢复单阶段 `loadSessions()`。
3. 后端 `/api/session-tree` 移除或忽略 `refresh` 参数。
4. `SessionService._refresh_workspaces()` 恢复逐 entry `_refresh_entry()`。
5. 保留新增测试时需同步移除或调整。