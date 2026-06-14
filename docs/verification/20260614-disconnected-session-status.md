# disconnected 会话状态语义验证

- Flow mode: strict
- Stage: Verification
- Review status: Draft
- Date: 2026-06-14

## Requirement alignment

Requirement: `docs/requirement/20260614-disconnected-session-status.md`

| Requirement | Result | Notes |
| --- | --- | --- |
| 增加 `disconnected` 状态 | Pass | `src/termbridge/models.py` 和 `web/src/types/sessions.ts` 已增加该状态。 |
| ttyd proxy 不可用但 tmux window 存在时显示 `disconnected` | Pass | `_refresh_entry()` 会在 process 不可用但 tmux window 存在时设置 `SessionStatus.DISCONNECTED`。 |
| `stopped` 表示没有可复用 tmux window | Pass | tmux window 不存在时刷新为 `STOPPED` 并清空 `tmux_window_id`。 |
| 历史 `stopped + tmux_window_id` 可升级为 `disconnected` | Pass | `tests/test_services.py` 覆盖 stopped 记录升级。 |
| `start()` 对 disconnected 复用 tmux window | Pass | 复用现有非 running 启动路径；测试覆盖不创建新 window 并 attach 原 window。 |
| terminal proxy 只允许 running + pid | Pass | `terminal_proxy_target()` 逻辑保持，测试覆盖 disconnected 拒绝 proxy。 |
| 会话列表使用 unplug icon，显示启动和删除按钮 | Pass | `SessionList.vue` 引入 `Unplug` 和 `Play`，disconnected 同时显示启动和删除操作。 |
| 终端区域显示 disconnected 专用文案 | Pass | `SessionTerminal.vue` 对 disconnected 使用 `session.terminal.disconnected`。 |
| API response 只使用 `status=disconnected` | Pass | 未新增 `has_tmux_window` 等额外字段。 |

## Spec alignment

Spec: `docs/spec/20260614-disconnected-session-status.md`

- 状态表已按 `running` / `disconnected` / `stopped` 区分 ttyd proxy 和 tmux window。
- `_refresh_entry()` 覆盖 running、disconnected、historical stopped 三类状态刷新。
- `_workspace_response()` 聚合优先级实现为：`running > disconnected > starting > failed > stopped`。
- stop/delete/close_all 显式清理语义未改动。
- 前端 i18n、类型、列表 UI、终端 UI、SessionCard 均已补齐 disconnected 分支。

## Plan alignment

Plan: `docs/plan/20260614-disconnected-session-status.md`

| Planned area | Actual files | Result |
| --- | --- | --- |
| 共享状态模型 | `src/termbridge/models.py`, `web/src/types/sessions.ts` | Pass |
| 后端状态刷新 | `src/termbridge/services.py` | Pass |
| 启动/停止/proxy 语义核对 | `src/termbridge/services.py`, `tests/test_services.py` | Pass |
| 前端 i18n 和状态样式 | `web/src/i18n/locales/*.json`, `SessionList.vue`, `SessionTerminal.vue`, `SessionCard.vue` | Pass |
| 测试 | `tests/test_services.py`, planned backend checks | Pass |

## Actual diff summary

Feature-scoped diff:

```text
src/termbridge/models.py               |   1 +
src/termbridge/services.py             |  45 ++++++++++-----
tests/test_services.py                 | 100 +++++++++++++++++++++++++++------
web/src/components/SessionCard.vue     |  13 ++++-
web/src/components/SessionList.vue     |  41 +++++++++++++-
web/src/components/SessionTerminal.vue |   7 ++-
web/src/i18n/locales/en-US.json        |   2 +
web/src/i18n/locales/zh-CN.json        |   2 +
web/src/types/sessions.ts              |   2 +-
9 files changed, 173 insertions(+), 40 deletions(-)
```

SpecFlow docs added:

- `docs/requirement/20260614-disconnected-session-status.md`
- `docs/spec/20260614-disconnected-session-status.md`
- `docs/plan/20260614-disconnected-session-status.md`
- `docs/verification/20260614-disconnected-session-status.md`

## Acceptance checklist

| Acceptance | Result | Evidence |
| --- | --- | --- |
| `SessionStatus` 增加 `disconnected` | Pass | Python enum and TS union updated. |
| ttyd pid 存活且 tmux window 存在 => `running` | Pass | Existing behavior preserved; list tree test asserts running workspace. |
| ttyd pid 不可用但 tmux window 存在 => `disconnected` | Pass | `test_service_refresh_disconnects_entry_when_ttyd_process_stops`。 |
| ttyd pid 不可用且 tmux window 不存在 => `stopped` | Pass | `test_service_refresh_stops_entry_when_tmux_window_disappears`。 |
| historical stopped + existing tmux window => `disconnected` | Pass | `test_service_refresh_promotes_stopped_entry_with_existing_window_to_disconnected`。 |
| disconnected + missing tmux window => `stopped` | Pass | `test_service_refresh_stops_disconnected_entry_when_tmux_window_disappears`。 |
| disconnected start 复用 tmux window | Pass | `test_service_starts_disconnected_entry_with_existing_window`。 |
| disconnected terminal proxy 拒绝 | Pass | `test_service_rejects_terminal_proxy_for_disconnected_entry`。 |
| workspace 聚合 disconnected | Pass | `test_service_list_tree_reports_disconnected_workspace_status`。 |
| 前端类型/i18n/组件逻辑更新 | Pass | frontend lint/typecheck passed. |

## Commands

Backend:

```bash
uv run ruff check src/termbridge/models.py src/termbridge/services.py tests/test_services.py tests/test_api.py && uv run mypy src/termbridge/models.py src/termbridge/services.py tests/test_services.py tests/test_api.py && uv run pytest tests/test_services.py tests/test_api.py
```

Result:

```text
ruff: passed
mypy: passed
pytest tests/test_services.py tests/test_api.py: 47 passed, 1 warning
```

Frontend:

```bash
cd /d/SourceCodes/mywork/term-bridge/web && yarn lint && yarn typecheck
```

Result:

```text
eslint: passed
vue-tsc --noEmit: passed
```

## Missed or expanded scope

- No extra API field was added, matching the requirement.
- `tests/test_api.py` was included in verification commands to guard API behavior, but feature-specific API test changes were not necessary.
- `SessionCard.vue` was updated because the frontend status union requires exhaustive `Record<Session['status'], string>` coverage and to avoid stale stopped-only start behavior.

## Risks and incomplete items

- Browser manual verification was not executed in this turn. Recommended manual checks:
  1. Kill ttyd process while preserving tmux window; verify UI shows “连接断开” with unplug icon, start and delete buttons.
  2. Click start; verify ttyd reattaches to the original tmux window content.
  3. Delete the tmux window externally; verify refresh changes status to stopped.
- New persisted `status=disconnected` records will not be readable by older code that lacks the enum value.
- The broader working tree may include other feature work from the same session; review commit boundaries before committing.

## Conclusion

Implementation aligns with accepted Requirement, Spec, and Plan. Automated backend and frontend checks passed. Manual browser verification remains recommended for the full UI experience.
