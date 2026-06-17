# session-tree 快速刷新与批量状态检查验证
最后修改时间: 2026-06-17 08:27:06

- Flow mode: strict
- Stage: Verification
- Review status: Draft
- Date: 2026-06-17

## Requirement alignment

对照 `docs/requirement/20260616-session-tree-fast-refresh.md`：

1. `GET /api/session-tree?refresh=false` 已实现：`src/termbridge/api.py` 将 `refresh` query 参数传入 `SessionService.list_tree(refresh=refresh)`。
2. `refresh=false` 快速路径已实现：`SessionService.list_tree(refresh=False)` 只读取 repository 并构建 response，不调用 `_refresh_workspaces()`。
3. 无 query `GET /api/session-tree` 仍默认 `refresh=True`，保持真实刷新行为。
4. 前端初始加载已改为先调用 `listSessionTree({ refresh: false })`，快速恢复持久化记录。
5. 快速记录请求期间新增全页面遮挡层，绑定 `initialSessionTreeLoading`。
6. 快速记录返回后继续调用无 query `listSessionTree()` 真实刷新。
7. 真实刷新改为按 host 调用 `tmux list-windows -a`，不再在 list-tree 路径对每个 session 执行单条 tmux window 检查。
8. 只有批量 listing 判断 window 存在时才检查 ttyd；window 不存在时直接刷新为 `stopped`。
9. 真实刷新失败场景中，前端保留已有快速记录视图并显示 toast；后端 tmux list 失败时保守保留旧状态。

结论：需求目标已覆盖，未发现与 Requirement 冲突的实现。

## Spec alignment

对照 `docs/spec/20260616-session-tree-fast-refresh.md`：

1. API 兼容策略已按规格实现：`refresh` 默认值为 `True`，`refresh=false` 走快速路径。
2. `SessionService.list_tree()` 已拆出 `_tree_response()`，避免 response 构建逻辑与刷新路径耦合。
3. `TerminalService.list_tmux_windows(host)` 已新增，执行 `tmux list-windows -a`，不使用 `-F`。
4. tmux 默认输出解析已通过 `parse_tmux_window_line()` 集中封装：按前两个冒号切分，清洗 pane/layout 描述和尾部 tmux marker。
5. `tmux list-windows -a` 在 runtime home shell 中执行：Cygwin / Linux 使用 shell `-lc`，WSL 使用 `wsl sh -lc`，不拼 `--cd <workspace>`。
6. 按 host 粒度批量刷新已实现：`_tmux_window_names_by_host()` 只对有 entries 的 host 调用 `list_tmux_windows()`。
7. tmux list 失败保守处理已实现：捕获异常后将 host 标记为 unknown，刷新该 host 下 entry 时保留原状态，不检查 ttyd，不更新 repository。
8. `no server running` + return code 1 已按空 window 列表处理。
9. 前端双阶段加载已实现，并对 `SessionList` 复用 `loading` prop 表示真实状态刷新中。

结论：规格中的主要接口、算法、失败处理和 UI 状态设计均已实现。

## Plan alignment

对照 `docs/plan/20260616-session-tree-fast-refresh.md`：

1. 计划列出的产品代码文件均已改动：
   - `src/termbridge/api.py`
   - `src/termbridge/services.py`
   - `web/src/api/sessions.ts`
   - `web/src/components/AppShell.vue`
   - `web/src/i18n/locales/zh-CN.json`
   - `web/src/i18n/locales/en-US.json`
2. 计划列出的测试文件均已改动：
   - `tests/test_api.py`
   - `tests/test_services.py`
   - `tests/test_terminal_service.py`
3. 后端测试覆盖已包含：
   - `refresh=false` 不执行真实检查。
   - 每 host 一次批量 tmux list。
   - window 不存在时跳过 ttyd 并置为 `stopped`。
   - window 存在且 ttyd 不可用时置为 `disconnected`。
   - tmux list 失败时保留旧状态。
   - `no server running` 按空列表处理。
   - parser 清洗默认输出中的 `*` marker 和 pane/layout 描述。
4. 前端没有现成单元测试，按计划使用 `npm --prefix web run lint`、`npm --prefix web run typecheck`、`npm --prefix web run build` 进行静态与构建验证。

结论：实际实施范围与 Plan 基本一致；额外增加 `tests/test_terminal_service.py` 覆盖 `TerminalService.list_tmux_windows()` 行为，属于计划测试范围内的细化。

## Actual diff summary

当前实际 diff 涉及 11 个文件：

- `docs/plan/20260616-session-tree-fast-refresh.md`
  - 将 Plan 状态更新为 `Accepted`，并更新最后修改时间。
- `docs/verification/20260616-session-tree-fast-refresh.md`
  - 新增本验证文档。
- `src/termbridge/api.py`
  - `/api/session-tree` route 增加 `refresh` query 参数。
- `src/termbridge/services.py`
  - 增加 `TmuxWindowListing`、`TmuxListWindowsError`、`parse_tmux_window_line()`。
  - 增加 `TerminalService.list_tmux_windows()` 和 home-shell tmux 命令执行 helper。
  - `SessionService.list_tree()` 支持 `refresh` 参数。
  - `list_tree()` 真实刷新改为按 host 批量 tmux listing。
  - 保留 `get()` / `start()` 等单 entry fallback 刷新语义。
- `tests/test_api.py`
  - Fake service 支持 `list_tree(refresh=True)`，新增 `refresh=false` route 参数断言。
- `tests/test_services.py`
  - 扩展 fake shortcut service，新增批量刷新、快速路径和失败处理测试。
- `tests/test_terminal_service.py`
  - 新增 tmux 默认输出解析、home-shell 执行和 `no server running` 空列表测试。
- `web/src/api/sessions.ts`
  - `listSessionTree()` 支持可选 `refresh` 参数。
- `web/src/components/AppShell.vue`
  - 初始加载拆成快速记录加载和真实状态刷新。
  - 新增全页面恢复遮挡层。
  - 真实刷新失败时保留快速记录视图并 toast。
- `web/src/i18n/locales/en-US.json`
  - 新增 `app.loading.restoreSessions`。
- `web/src/i18n/locales/zh-CN.json`
  - 新增 `app.loading.restoreSessions`。

## Expected vs actual changed files

| 文件 | Plan 预期 | 实际 | 说明 |
| --- | --- | --- | --- |
| `src/termbridge/api.py` | 是 | 是 | API query 参数实现 |
| `src/termbridge/services.py` | 是 | 是 | 快速路径、批量 tmux list、刷新算法实现 |
| `web/src/api/sessions.ts` | 是 | 是 | 前端 API helper 支持 refresh 参数 |
| `web/src/components/AppShell.vue` | 是 | 是 | 双阶段加载与遮挡层 |
| `web/src/i18n/locales/zh-CN.json` | 是 | 是 | 中文恢复文案 |
| `web/src/i18n/locales/en-US.json` | 是 | 是 | 英文恢复文案 |
| `tests/test_api.py` | 是 | 是 | API route refresh 参数测试 |
| `tests/test_services.py` | 是 | 是 | SessionService 快速路径与批量刷新测试 |
| `tests/test_terminal_service.py` | 是 | 是 | 计划中未单独列名，但属于后端测试细化；覆盖 TerminalService 新方法 |
| `docs/plan/20260616-session-tree-fast-refresh.md` | 是 | 是 | 状态更新为 Accepted，并更新最后修改时间 |
| `docs/verification/20260616-session-tree-fast-refresh.md` | 是 | 是 | 本验证文档 |

范围偏差：未发现产品代码范围外的无关改动。`tests/test_terminal_service.py` 是对计划测试覆盖的合理细化。

## Acceptance criteria checklist

1. [x] API 支持 `GET /api/session-tree?refresh=false`。
2. [x] `refresh=false` 响应直接基于持久化记录构建，不调用真实 tmux / ttyd 检查。
3. [x] `GET /api/session-tree` 无 query 保持真实刷新行为。
4. [x] 真实状态刷新继续使用无 query `GET /api/session-tree`，未新增 endpoint。
5. [x] 前端初始加载先请求 `refresh=false`。
6. [x] `refresh=false` 请求完成前显示覆盖完整页面的加载遮挡层。
7. [x] `refresh=false` 请求完成后触发无 query 真实刷新，并用结果更新 session tree。
8. [x] 真实刷新使用 `tmux list-windows -a` 批量查询，list-tree 路径不再按 session 调用 `tmux_window_exists()`。
9. [x] 批量 tmux 查询结果通过 `tmux_session_name -> window_name` index 判断保存窗口是否存在。
10. [x] tmux window 不存在时不执行 ttyd port 检查。
11. [x] tmux window 存在时继续检查 ttyd，区分 `running` 与 `disconnected`。
12. [x] 状态刷新成功后前端展示真实状态。
13. [x] 真实状态刷新失败时前端保留快速记录视图并 toast；后端 tmux list 失败时保守保留旧状态。
14. [x] 后端测试覆盖快速路径、批量映射、window 不存在跳过 ttyd、失败保守处理。
15. [x] 前端通过 lint/typecheck/build 覆盖静态正确性；当前项目未发现前端单元测试配置。
16. [x] Spec 已列出现有无 query `/api/session-tree` 调用位置，并在实现中按规格处理。

## Test results

### Backend

1. `uv run pytest tests/test_services.py tests/test_terminal_service.py tests/test_api.py`
   - 结果：通过。
   - 摘要：`95 passed, 1 warning`。

2. `uv run pytest`
   - 结果：通过。
   - 摘要：`155 passed, 1 warning`。
   - warning：`fastapi.testclient` 依赖层面的 `StarletteDeprecationWarning`，与本次功能无直接关系。

3. `uv run ruff check src tests`
   - 结果：通过。
   - 摘要：`All checks passed!`

4. `uv run mypy src tests/test_services.py tests/test_terminal_service.py tests/test_api.py`
   - 结果：通过。
   - 摘要：`Success: no issues found in 18 source files`。

5. `uv run mypy src tests`
   - 结果：失败。
   - 失败原因：既有 `tests/test_settings.py` 中 2 处测试 fixture / 参数缺少类型标注：
     - `tests/test_settings.py:22`
     - `tests/test_settings.py:42`
   - 判断：与本次改动文件无关；变更相关 Python 文件的 mypy 已通过。

### Frontend

1. `npm --prefix web run lint`
   - 结果：通过。

2. `npm --prefix web run typecheck`
   - 结果：通过。

3. `npm --prefix web run build`
   - 结果：通过。
   - 输出：Vite 构建成功。
   - warning：
     - `@vueuse/core` 中 `/* #__PURE__ */` 注释位置 warning。
     - chunk size 超过 500 kB warning。
   - 判断：均为依赖 / 打包层面的 warning，不阻塞本次功能交付。

## Missed or expanded scope

- 未新增独立状态刷新 endpoint，符合范围。
- 未改变创建、启动、停止、删除会话的业务语义，符合 non-goals。
- 未改变 tmux session/window 命名规则，符合 non-goals。
- 未新增 `checking` / `unknown` session status，符合 non-goals。
- 未实现状态检查 TTL cache，符合 non-goals。
- 未新增前端单元测试；当前项目未发现现成前端测试配置，已按计划使用 lint/typecheck/build 验证。
- `tests/test_terminal_service.py` 的新增测试是对新 `TerminalService.list_tmux_windows()` 的直接覆盖，属于测试覆盖细化，不属于范围扩大。

## Risks

1. `tmux list-windows -a` 默认输出解析仍比 `-F` 脆弱；已通过集中 parser 和样例测试降低风险。
2. 当前批量刷新按 `workspace.tmux_session_name + entry.name` 匹配 window；如果未来 window name 与 entry name 规则发生变化，可能误判为 stopped。
3. tmux list 真失败时保守保留旧状态，避免误降级，但可能短时间展示过期状态；该行为符合已接受规格。
4. 前端遮挡层的行为通过静态检查和代码审查验证，未做浏览器级人工操作验证。
5. 全量 `uv run mypy src tests` 仍受既有 `tests/test_settings.py` 类型标注问题影响；本次变更相关 Python 文件 mypy 已通过。

## Incomplete items

- 无本次功能必须完成但未完成的实现项。
- 如需更高置信度，可后续用浏览器/手工方式验证页面刷新时遮挡层出现、快速记录先展示、真实状态随后更新的实际交互。

## Conclusion

本次实现与 Requirement / Spec / Plan 对齐。后端快速路径、批量 tmux list 状态刷新、失败保守处理、前端双阶段加载和全页面遮挡均已实现并通过相关测试与检查。

Verification 当前结论：可交付。等待用户 review 本验证文档后，可将 `Review status` 更新为 `Accepted`。