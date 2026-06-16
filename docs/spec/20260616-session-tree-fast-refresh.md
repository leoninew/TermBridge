# session-tree 快速刷新与批量状态检查规格
最后修改时间: 2026-06-16 22:45:22

- Flow mode: strict
- Stage: Spec
- Review status: Accepted
- Date: 2026-06-16

## Requirement basis

基于 `docs/requirement/20260616-session-tree-fast-refresh.md`，本规格解决 session 页面刷新时等待真实 tmux / ttyd 状态检查导致首屏迟迟不可用的问题。

已确认的需求约束：

1. `GET /api/session-tree?refresh=false` 快速返回持久化记录，不做真实状态检查。
2. `GET /api/session-tree` 无 query 时保持兼容，仍执行真实状态刷新。
3. 前端初始加载显式使用 `refresh=false`，快速恢复记录后再调用无 query 的 `GET /api/session-tree` 获取真实状态。
4. 快速记录返回前，加载遮挡层覆盖完整页面，避免用户新建会话或触发其他会话写操作。
5. 真实状态刷新使用 `tmux list-windows -a` 批量判断 tmux window 是否存在。
6. 只有 tmux window 存在的 session 才继续检查 ttyd 状态。

## Overview

实现拆为三个协作点：

1. **API 查询参数**：`/api/session-tree` 增加 `refresh: bool = True` 查询参数。`refresh=false` 走快速路径；无 query 或 `refresh=true` 走现有真实刷新路径。
2. **后端批量刷新**：`SessionService.list_tree(refresh=True)` 在真实刷新时先调用 `TerminalService` 的批量 tmux window 列表能力，解析 `tmux list-windows -a` 的每一行，得到当前 tmux server 中仍存在的 workspace tmux session / window 信息，再刷新每个 entry。entry 的 ttyd port 检查只在对应 tmux window 仍存在时执行。
3. **前端双阶段加载**：`AppShell.refresh()` 先显示全页面遮挡并调用 `listSessionTree({ refresh: false })`，成功后移除遮挡并渲染记录；随后调用 `listSessionTree()` 进行真实刷新，成功则更新树，失败则保留快速记录并 toast。

## Existing no-query `/api/session-tree` usages

当前代码中无 query 调用位置如下：

1. `web/src/api/sessions.ts:86`：`listSessionTree()` 固定请求 `'/api/session-tree'`。
   - 规格：改为可选参数，例如 `listSessionTree(options?: { refresh?: boolean })`。
   - 默认无参数时继续请求 `'/api/session-tree'`，保持真实刷新。
   - `refresh=false` 时请求 `'/api/session-tree?refresh=false'`。

2. `web/src/components/AppShell.vue:118`：`loadSessions()` 调用 `listSessionTree()`。
   - 规格：拆分为快速加载和真实刷新两个调用。
   - 初始加载路径先调用 `listSessionTree({ refresh: false })`。
   - 后续真实刷新调用 `listSessionTree()`，保持无 query。

3. `tests/test_api.py:300`：API route 测试调用 `client.get("/api/session-tree")`。
   - 规格：保留该测试语义为默认真实刷新，并新增 `client.get("/api/session-tree?refresh=false")` 覆盖快速路径。

4. `src/termbridge/api.py:295`：FastAPI route `@router.get("/api/session-tree")` 当前没有 query 参数。
   - 规格：增加 `refresh: bool = True` 参数，并传给 service。

5. 文档中的历史引用（如 `docs/verification/20260616-session-reconnect-status.md`）仅描述过往行为，不参与代码改动。

`PUT /api/session-tree/environments/{host}/workspaces/order` 不是 GET session-tree 列表接口，不属于本次 `refresh` query 范围。

## Design decisions

### 1. API 兼容策略

- `GET /api/session-tree`：默认真实刷新，行为兼容当前调用方。
- `GET /api/session-tree?refresh=true`：等价于无 query。
- `GET /api/session-tree?refresh=false`：快速返回持久化记录，不调用 tmux/ttyd 检查。

FastAPI route 形态建议：

```python
@router.get("/api/session-tree", response_model=SessionTreeResponse)
def list_session_tree(service: SessionServiceDep, refresh: bool = True) -> SessionTreeResponse:
    return service.list_tree(refresh=refresh)
```

`SessionService.list_tree()` 增加参数：

```python
def list_tree(self, *, refresh: bool = True) -> SessionTreeResponse:
    workspaces = self._repository.list_workspaces()
    if refresh:
        workspaces = self._refresh_workspaces(workspaces)
    return self._tree_response(workspaces)
```

为避免 `list_tree()` 继续膨胀，可将构建 `SessionTreeResponse` 的逻辑提取为私有方法，例如 `_tree_response(workspaces)`。

### 2. 快速路径不做真实检查

`refresh=false` 必须满足：

- 不调用 `TerminalService.tmux_window_exists()`。
- 不调用新的批量 tmux list 方法。
- 不调用 `_ttyd_port_checker()`。
- 不更新 repository 中 entry 状态。

它只把 repository 当前保存的 workspace / entry 记录转换为 response。

### 3. 批量 tmux window 查询

新增 `TerminalService` 方法，直接执行并解析原始 `tmux list-windows -a` 输出，不使用 `-F`：

```python
@dataclass(frozen=True)
class TmuxWindowListing:
    tmux_session_name: str
    window_index: str
    window_name: str


def list_tmux_windows(self, host: ShortcutHost) -> list[TmuxWindowListing]:
    result = self._run_tmux_command_in_home(host, "tmux list-windows -a")
    if result.returncode != 0:
        raise TmuxListWindowsError(result.stderr.strip() or "tmux list-windows failed")
    return [parse_tmux_window_line(line) for line in result.stdout.splitlines() if line.strip()]
```

用户提供的实际输出格式：

```text
tb_cyg_3d134fa1d1d50ef3:0: 特性开发* (1 panes) [230x54]
tb_cyg_7b32d42b4912fb37:0: 特性开发* (1 panes) [230x54]
```

解析规则：

- 第一个冒号前的字段是 tmux session name，例如 `tb_cyg_3d134fa1d1d50ef3`。
- 该字段可直接与 TermBridge 持久化记录中的 `workspace.tmux_session_name` 匹配。
- 第二个字段是 window index。
- 第二个冒号后的窗口标题包含 TermBridge entry/window 名称；需要去除 tmux 活动标记（如尾部 `*`、`-` 等）和 pane/layout 描述后再用于匹配 entry 名称。

执行位置：

- 不从某个 workspace path 执行。
- `tmux list-windows -a` 直接在对应 runtime 的 home 目录执行。
- 因此不需要“选择一个 workspace path 作为 shell cwd”。

host 粒度：

- 不同 host（Cygwin、WSL、Linux）对应不同 runtime shell / tmux server，因此仍按 host 调用一次。
- 每个 host 的调用都是批量调用：一次 `tmux list-windows -a` 返回该 host 可见的目录和会话相关窗口。
- 如果某个 host 没有保存的 workspace，无需调用。

### 4. tmux 命令失败的保守处理

用户已采纳保守策略：如果 `tmux list-windows -a` 命令失败、超时或输出无法解析，不应把该 host 下所有会话误降级为 `stopped`。

规格要求：

- 记录 warning / error log。
- 对该 host 下受影响 entry 保留原状态和原 `tmux_window_id`，不执行 ttyd 检查，不更新 repository。
- API 仍应尽量返回 session tree；前端真实刷新请求可成功返回“保守保留”的旧状态。
- 如果实现上需要向前端提示状态刷新不完整，可后续扩展；本次不新增 response 字段。

### 5. 真实刷新算法

目标是让 tmux 检查次数从“每个 session 一次”降到“每个有 session 的 host 一次”。

建议流程：

1. `workspaces = repository.list_workspaces()`。
2. 按 `workspace.host` 分组。
3. 对每个 host：
   - 在该 host 的 home 目录执行 `tmux list-windows -a`。
   - 解析得到 `TmuxWindowListing` 列表。
   - 以 `tmux_session_name` 和 `window_name` 建立索引。
   - 如果命令失败，记录该 host 为“状态未知”，刷新该 host 下 entry 时保留旧状态。
4. 遍历每个 workspace / entry：
   - `starting` / `failed` 沿用当前逻辑，不刷新。
   - 如果 workspace 所属 host 的 tmux list 失败：保留 entry，不检查 ttyd，不更新 repository。
   - 否则根据批量 listing 判断 window 是否存在：
     - 首先匹配 `workspace.tmux_session_name`，也就是 `tmux list-windows -a` 每行第一个冒号前字段。
     - 再在该 tmux session 下匹配 entry/window 名称；本需求保持用户方案，不使用 `-F`，不依赖 `#{window_id}` 输出。
   - 如果 tmux window 不存在：
     - 不调用 `_ttyd_port_checker()`。
     - 状态设为 `stopped`。
     - `pid=None`，`url=""`，`tmux_window_id=None`。
   - 如果 tmux window 存在：
     - 调用 `_ttyd_port_checker(entry.port)`。
     - ttyd 可用 => `running`，保留/重建 url。
     - ttyd 不可用 => `disconnected`，`pid=None`，`url=""`，保留 `tmux_window_id`。
5. 对有变化的 entry 更新 repository。

可通过新增 helper 降低变更面，例如：

```python
def _refresh_workspaces(self, workspaces: list[WorkspaceRecord]) -> list[WorkspaceRecord]:
    listings_by_host = self._tmux_windows_by_host(workspaces)
    return [self._refresh_workspace(workspace, listings_by_host.get(workspace.host)) for workspace in workspaces]
```

`_refresh_entry()` 可以改为接收已计算的 host listing / unknown 状态，避免内部再次调用 `tmux_window_exists()`。

### 6. ttyd 检查跳过规则

`_ttyd_port_checker()` 只在以下条件同时成立时调用：

- entry 不处于 `starting` / `failed`。
- host 的批量 tmux list 成功。
- 批量 tmux listing 表明该 entry 对应 tmux window 仍存在。
- `entry.port > 0`。

这满足“window 都没有的就不用检查了”。

### 7. 前端加载状态

新增两个概念状态更清晰：

- `initialSessionTreeLoading`：只覆盖 `refresh=false` 快速请求阶段。
- `sessionStatusRefreshing`：快速记录已返回后的真实状态刷新阶段。

初始加载流程建议：

```ts
async function refresh() {
  initialSessionTreeLoading.value = true
  error.value = ''
  try {
    await Promise.all([loadStoredSessions(), environmentStore.ensureLoaded()])
  } finally {
    initialSessionTreeLoading.value = false
  }

  await refreshLiveSessions()
}

async function loadStoredSessions() {
  applySessionTree((await listSessionTree({ refresh: false })).environments)
}

async function refreshLiveSessions() {
  sessionStatusRefreshing.value = true
  try {
    applySessionTree((await listSessionTree()).environments)
  } catch (err) {
    toast.show({ title: errorTitle(err, t('app.errors.loadSessions')), variant: 'error' })
  } finally {
    sessionStatusRefreshing.value = false
  }
}
```

注意：

- 用户已采纳：覆盖完整页面的遮挡层只绑定 `initialSessionTreeLoading`。
- 真实状态刷新失败时不清空快速记录。
- 真实状态刷新期间可以在侧栏保留小型 loading/spinner 或文案，但不再遮挡完整页面。
- 用户已采纳：前端新增内部 `sessionStatusRefreshing` 状态；对 `SessionList` 仍复用现有 `loading` prop 表达真实状态刷新中，减少组件接口改动。

### 8. 全页面遮挡层

在 `AppShell.vue` 顶层 `<main>` 内新增全屏绝对/固定遮挡层：

- 覆盖完整 viewport。
- z-index 高于 sidebar / create panel / terminal。
- 显示 spinner 和文案，例如“正在恢复会话...”或复用 i18n。
- 仅在 `refresh=false` 快速请求未完成时展示。
- 不等待无 query `GET /api/session-tree` 的真实状态刷新完成。

遮挡层的目的不是等待真实状态检查完成，而是防止记录尚未恢复时用户新建会话。

### 9. i18n

需要新增或复用文案：

- zh-CN：`正在恢复会话...` 或 `正在恢复会话记录...`
- en-US：`Restoring sessions...`

可以放在 `session.list.restoring` 或 `app.loading.restoringSessions`，Plan 阶段按现有 i18n 结构选择。

## Affected components

### Backend

- `src/termbridge/api.py`
  - `/api/session-tree` 增加 `refresh` query 参数。

- `src/termbridge/services.py`
  - `SessionService.list_tree(refresh=True)`。
  - 拆出 response 构建 helper。
  - `_refresh_workspaces()` 改为使用批量 tmux window listing。
  - `_refresh_entry()` 改为接收批量 listing / host unknown 状态，并在 window 不存在或 host 状态未知时跳过 ttyd 检查。
  - `TerminalService` 增加从 home 目录执行 `tmux list-windows -a` 并解析 listing 的方法。

- `tests/test_api.py`
  - Fake service 支持 `list_tree(refresh=True)` 参数。
  - 增加 `refresh=false` route 测试。

- `tests/test_services.py`
  - Fake terminal service 增加批量 window listing 能力。
  - 增加/调整状态刷新测试，验证批量 tmux、跳过 ttyd、快速路径不刷新、tmux list 失败时保守保留旧状态。

### Frontend

- `web/src/api/sessions.ts`
  - `listSessionTree()` 支持可选 `refresh` 参数。
  - 无参数保持请求 `/api/session-tree`。
  - `refresh=false` 请求 `/api/session-tree?refresh=false`。

- `web/src/components/AppShell.vue`
  - 初始加载拆成快速记录加载和真实状态刷新。
  - 新增全页面遮挡层。
  - 真实状态刷新失败时保留快速记录并 toast。

- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`
  - 新增加载遮挡文案。

## Interfaces

### GET /api/session-tree

Query:

| 参数 | 类型 | 默认 | 含义 |
| --- | --- | --- | --- |
| `refresh` | boolean | `true` | 是否在返回前刷新真实 tmux / ttyd 状态 |

Response: 保持现有 `SessionTreeResponse` 不变。

行为：

- `refresh=true` / query 缺省：读取记录后刷新真实状态，再返回。
- `refresh=false`：读取记录后直接返回，不检查真实状态，不更新记录。

### listSessionTree frontend helper

建议接口：

```ts
export function listSessionTree(options?: { refresh?: boolean }): Promise<SessionTreeResponse>
```

URL 生成规则：

- `listSessionTree()` => `/api/session-tree`
- `listSessionTree({ refresh: true })` => `/api/session-tree?refresh=true` 或直接 `/api/session-tree`；建议保持简单，可省略 true query。
- `listSessionTree({ refresh: false })` => `/api/session-tree?refresh=false`

## Technical questions

暂无阻塞问题。用户已确认：状态刷新后继续逐 entry 更新 repository，不做 workspace 级批量保存。

## Risks

1. 快速记录返回的是旧状态，真实刷新完成前 UI 可能短暂显示过期状态。
2. `refresh=false` 快速路径若不小心复用现有 `list_tree()` 的刷新逻辑，会失去本需求核心收益，需要测试显式覆盖。
3. tmux window 名称如果包含 tmux 活动标记或与 entry 名称不完全一致，默认输出解析可能误判；Plan 阶段应集中封装原始输出解析和 window name 清洗逻辑。
4. `tmux list-windows -a` 失败时保守保留旧状态会避免误降级，但也可能让 UI 短时间继续展示过期状态；需要 logging 便于排查。

## Alternatives considered

1. **新增 `/api/session-tree/status` endpoint**：被用户否决；真实状态刷新使用无 query 的 `GET /api/session-tree`。
2. **改默认 `/api/session-tree` 为快速返回**：被用户否决；默认保持真实刷新以兼容现有调用方。
3. **继续逐 session 调用 `tmux_window_exists()` 并只优化前端 loading**：不能解决真实性能瓶颈，不满足批量检查要求。
4. **新增 `checking` 状态**：当前不需要；会扩大 API 和 UI 状态枚举改动。
5. **用 TTL 缓存状态检查**：当前为 non-goal，可作为后续优化。
6. **从任意 workspace path 执行 `tmux list-windows -a`**：已废弃；用户确认可直接从 home 目录执行，无需选择 workspace 作为 cwd。
7. **使用 `tmux list-windows -a -F ...` 稳定格式输出**：已废弃；用户要求保持原方案，读取 `tmux list-windows -a` 默认结果，再找目录和会话。

## User review notes

- 2026-06-16：用户采纳 tmux list 失败时保守处理，采纳遮挡层只覆盖快速加载阶段；同时确认 `tmux list-windows -a` 可直接在 home 目录执行，输出第一个冒号前字段可匹配存储的 `tmux_session_name`，不需要选择 workspace path 作为 cwd。
- 2026-06-16：用户明确不使用 `-F`，保持读取 `tmux list-windows -a` 默认输出后再找目录和会话的方案。
- 2026-06-16：用户采纳前端真实状态刷新期间新增内部状态、但对 `SessionList` 复用现有 `loading` prop 的方案。
- 2026-06-16：用户确认状态刷新后继续逐 entry 更新 repository，不做 workspace 级批量保存，并要求进入 Plan。