# 独立拖动排序能力验证

- Flow mode: standard
- Stage: Verification
- Review status: Draft
- Date: 2026-06-14

## Requirement Alignment

| Requirement | Result | Notes |
| --- | --- | --- |
| 特定环境下目录列表支持拖动排序 | Pass | `SessionList.vue` 为每个环境分组的 workspace list 引入 `vue-draggable-plus`，排序后通过 `reorderWorkspaces` 事件提交该环境内完整 workspace id 顺序。 |
| 特定目录下会话列表支持拖动排序 | Pass | `SessionList.vue` 为每个 workspace 的 session list 引入 `vue-draggable-plus`，排序后通过 `reorderSessions` 事件提交该目录内完整 session id 顺序。 |
| 终端 tab 页头支持拖动排序 | Pass | `SessionTerminal.vue` 为已打开 terminal tabs 引入 `vue-draggable-plus`，新建 tab 固定在末尾。 |
| 三块排序互不干扰 | Pass | 目录排序调用 workspace order API；会话排序调用 workspace session order API；tab 排序仅更新 `openTerminalSessionIds`。 |
| 基于 `vue-draggable-plus` 实现 | Pass | 新增 `vue-draggable-plus@0.6.1` 依赖并更新 lockfile；组件使用 `VueDraggable v-model` 方式。 |
| 目录/会话排序通过 `.termbridge/sessions.json` 持久化 | Pass | repository 通过重建现有 `SessionState.workspaces` dict 顺序和 `WorkspaceRecord.entries` list 顺序写回，不新增排序字段或额外 storage。 |
| 终端 tab 排序无需持久化 | Pass | tab 排序只更新前端内存状态，不调用后端。 |
| 保持现有选择、启动、停止、删除、新建行为 | Mostly Pass | 代码保留现有操作入口，并通过按钮过滤与事件隔离避免拖动影响按钮操作；静态检查、类型检查和 build 通过。仍建议进行一次浏览器手动验证。 |

## Plan Alignment

| Plan item | Result | Notes |
| --- | --- | --- |
| 新增前端拖拽依赖 | Pass | `web/package.json` / `web/yarn.lock` 已更新为 `vue-draggable-plus`。 |
| 后端排序请求模型 | Pass | `ReorderWorkspacesRequest` / `ReorderSessionsRequest` 已新增。 |
| repository 按现有 JSON 顺序重排 | Pass | `FileSessionRepository.reorder_workspaces()` 和 `reorder_entries()` 已新增。 |
| service/API 排序入口 | Pass | 新增目录排序和会话排序 API，返回 `SessionTreeResponse`。 |
| 前端 API 和类型 | Pass | `web/src/types/sessions.ts` 和 `web/src/api/sessions.ts` 已新增排序 payload/API client。 |
| `AppShell.vue` 承接排序 | Pass | 持久化排序调用后端 API；tab 排序仅更新本地顺序；失败时 toast 并 reload。 |
| `SessionList.vue` 目录/会话拖动 | Pass | 已改为显式两层 `VueDraggable` 渲染，规避 Reka `TreeRoot` flatten 与 draggable 的 DOM 顺序冲突；filtered view 会合并回完整 id 列表提交。 |
| `SessionTerminal.vue` tab 拖动 | Pass | 已打开 tabs 使用 `VueDraggable v-model`；create tab 固定在末尾。 |
| 后端测试与前端检查 | Pass | ruff、mypy、frontend lint/typecheck/build、targeted pytest 均通过。 |

## Actual Diff Summary

当前 diff 范围集中在独立拖动排序功能、过程文档、以及若干前端文件的格式化类改动：

- 新增过程文档：
  - `docs/requirement/20260614-independent-drag-sorting.md`
  - `docs/plan/20260614-independent-drag-sorting.md`
  - `docs/verification/20260614-independent-drag-sorting.md`
- 后端：
  - `src/termbridge/models.py`
  - `src/termbridge/repositories.py`
  - `src/termbridge/services.py`
  - `src/termbridge/api.py`
- 后端测试：
  - `tests/test_session_repository.py`
  - `tests/test_services.py`
  - `tests/test_api.py`
- 前端功能：
  - `web/package.json`
  - `web/yarn.lock`
  - `web/src/types/sessions.ts`
  - `web/src/api/sessions.ts`
  - `web/src/components/AppShell.vue`
  - `web/src/components/SessionList.vue`
  - `web/src/components/SessionTerminal.vue`
- 额外前端格式化类变更：
  - `web/src/components/AppStatus.vue`
  - `web/src/components/EnvironmentHelp.vue`
  - `web/src/components/EnvironmentManagement.vue`
  - `web/src/components/HomeOnboarding.vue`
  - `web/src/components/SessionCreateForm.vue`
  - `web/src/components/ShortcutManagement.vue`
  - `web/src/components/WorkspaceBrowser.vue`

Current diff stat:

```text
docs/plan/20260614-independent-drag-sorting.md     | 191 ++++++++++++
docs/requirement/20260614-independent-drag-sorting.md | 84 ++++++
docs/verification/20260614-independent-drag-sorting.md | 151 +++++++++
src/termbridge/api.py                              | 17 ++
src/termbridge/models.py                           | 8 +
src/termbridge/repositories.py                     | 32 ++
src/termbridge/services.py                         | 21 ++
tests/test_api.py                                  | 21 ++
tests/test_services.py                             | 43 ++-
tests/test_session_repository.py                   | 59 ++++
web/package.json                                   | 1 +
web/src/api/sessions.ts                            | 28 ++
web/src/components/AppShell.vue                    | 117 +++++--
web/src/components/AppStatus.vue                   | 5 +-
web/src/components/EnvironmentHelp.vue             | 8 +-
web/src/components/EnvironmentManagement.vue       | 19 +-
web/src/components/HomeOnboarding.vue              | 45 ++-
web/src/components/SessionCreateForm.vue           | 30 +-
web/src/components/SessionList.vue                 | 336 +++++++++++++++------
web/src/components/SessionTerminal.vue             | 113 +++++--
web/src/components/ShortcutManagement.vue          | 46 ++-
web/src/components/WorkspaceBrowser.vue            | 11 +-
web/src/types/sessions.ts                          | 8 +
web/yarn.lock                                      | 12 +
24 files changed, 1222 insertions(+), 184 deletions(-)
```

## Planned vs Actual Changed Files

| Planned file | Actual | Notes |
| --- | --- | --- |
| `web/package.json` | Changed | Added `vue-draggable-plus`. |
| `web/yarn.lock` | Changed | Added `vue-draggable-plus` and its dependency graph. |
| `src/termbridge/models.py` | Changed | Added request models. |
| `src/termbridge/repositories.py` | Changed | Added ordered JSON rewrite methods. |
| `src/termbridge/services.py` | Changed | Added service ordering methods and validation mapping. |
| `src/termbridge/api.py` | Changed | Added ordering endpoints. |
| `web/src/types/sessions.ts` | Changed | Added payload interfaces. |
| `web/src/api/sessions.ts` | Changed | Added ordering API methods. |
| `web/src/components/AppShell.vue` | Changed | Handles persistent and tab-local ordering. |
| `web/src/components/SessionList.vue` | Changed | Implements workspace/session draggable lists with `VueDraggable`. |
| `web/src/components/SessionTerminal.vue` | Changed | Implements terminal tab draggable list with `VueDraggable`. |
| `tests/test_session_repository.py` | Changed | Added ordered JSON persistence tests. |
| `tests/test_services.py` | Changed | Added service ordering tests. |
| `tests/test_api.py` | Changed | Added API route coverage in session API test. |
| Several other `web/src/components/*.vue` files | Expanded scope | Diff shows formatting-only changes outside the original feature file list. They do not appear to add product behavior, but they expand the commit boundary and should be reviewed or split if a narrow commit is desired. |

## Acceptance Criteria Checklist

1. Pass — 每个环境分组下的目录列表可在该环境内拖动排序。
2. Pass — 后端接口按 host 校验完整 workspace id 集合，避免跨环境或丢失目录。
3. Pass — 每个目录节点下的会话列表可在该目录内拖动排序。
4. Pass — 后端接口按 workspace 校验完整 session id 集合，避免跨目录或丢失会话。
5. Pass — 终端 tab 页头可对已打开 tab 排序。
6. Pass — tab 排序仅更新 `openTerminalSessionIds`，不影响左侧 tree。
7. Pass — 左侧排序调用后端 tree API，不更新 terminal tab 顺序。
8. Pass — 使用整行/整 tab 拖动和单一 ghost class 提供拖动反馈；避免了 `DOMTokenList.add()` 多 class token 运行时错误。
9. Mostly Pass — session 文本点击仍走 `handleTreeSelect`；按钮区域通过过滤与事件隔离避免误拖。建议手动 UI 验证确认无误触。
10. Pass — active tab 基于 session id；tab 重排不改变 active session id。
11. Mostly Pass — 现有操作按钮保留；建议手动 UI 验证 hover/点击细节。
12. Pass — 基于 `vue-draggable-plus` 实现并纳入依赖。
13. Mostly Pass — 浅色/暗色 class 已覆盖拖动项和 ghost；建议手动视觉确认。
14. Pass — 目录/会话排序写回 `.termbridge/sessions.json` 现有顺序结构，测试覆盖读取顺序。
15. Pass — tab 排序不持久化，仅当前前端会话内生效。

## Test Results

已执行：

```bash
cd /d/SourceCodes/mywork/term-bridge/web && yarn lint && yarn typecheck && yarn build
cd /d/SourceCodes/mywork/term-bridge && uv run ruff check src/ tests/ && uv run mypy src/ tests/ && uv run pytest tests/test_session_repository.py tests/test_services.py tests/test_api.py
```

结果：

```text
Frontend lint: passed
Frontend typecheck: passed
Frontend build: passed
Backend ruff: passed
Backend mypy: passed
Backend targeted tests: 50 passed, 1 warning
```

Frontend build warnings:

```text
[INVALID_ANNOTATION] A comment "/* #__PURE__ */" in "node_modules/@vueuse/core/dist/index.js" contains an annotation that Rolldown cannot interpret due to the position of the comment.
[plugin builtin:vite-reporter] Some chunks are larger than 500 kB after minification.
```

以上 warning 来自第三方依赖 / bundle 体积提示，build 成功。

Backend pytest warning:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

该 warning 来自现有测试依赖链，不是本次排序实现引入的功能失败。

## Missed or Expanded Scope

- 未执行浏览器手动拖拽验证；当前验证覆盖 lint、typecheck、production build、后端静态检查和后端行为测试。
- 为解决 draggable 与 Reka `TreeRoot` flatten 渲染的 DOM 顺序冲突风险，`SessionList.vue` 实际采用显式两层结构渲染目录和会话列表。这符合 Plan 中的兜底方案，但可能改变部分 TreeRoot 内建键盘导航行为。
- Diff 中包含若干原 Plan 未列出的前端组件格式化类变更（如 `HomeOnboarding.vue`、`ShortcutManagement.vue`、`WorkspaceBrowser.vue` 等）。建议在提交前确认是否保留在同一 commit。
- 未新增专门的前端组件测试；当前项目前端验证以 lint/typecheck/build 为主。

## Risks

1. `SessionList.vue` 从 Reka `TreeRoot` flatten 渲染切换为显式两层 draggable 结构后，键盘树导航能力可能和原 TreeRoot 不完全一致，需要手动体验确认。
2. 拖动与点击/按钮操作已通过按钮过滤与事件隔离保护，但仍建议在真实浏览器中验证：点击 session、拖动 session、点击启动/停止/删除按钮互不干扰。
3. JSON object 顺序承载目录和会话顺序，符合当前用户澄清和实现约束；后续如引入会重排 object key 的格式化/迁移工具，需要避免破坏顺序。
4. `vue-draggable-plus` 的 Sortable option（如 `ghost-class`）要求单个 CSS class token；当前已改为 `session-list-ghost`，后续维护时应避免传入 Tailwind 多 class 字符串。

## Incomplete Items

- 手动 UI 验证未执行：目录拖动、会话拖动、tab 拖动、浅色/暗色视觉反馈、刷新后顺序保持。
- 未运行全量 `uv run pytest`；本次运行了计划中的相关 targeted tests。

## Conclusion

实现与已接受的 Requirement / Plan 基本一致，自动化验证通过。建议在进入提交前补一次浏览器手动验证，重点确认拖动手感、按钮点击隔离、暗色主题视觉和刷新后 `.termbridge/sessions.json` 顺序保持；同时确认额外前端格式化类变更是否需要拆分。