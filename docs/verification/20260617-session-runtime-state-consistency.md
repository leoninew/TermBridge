# 会话运行时状态一致性验证
最后修改时间: 2026-06-17 17:06:19

- Flow mode: strict
- Stage: Verification
- Review status: Accepted
- Date: 2026-06-17

## Requirement alignment

基于已接受的需求文档：

- `docs/requirement/20260617-session-runtime-state-consistency.md`

核对结果：实现与需求目标一致。

### 验收标准核对

| # | 验收标准 | 结果 | 说明 |
|---|---|---|---|
| 1 | 对外业务状态不再包含 `starting` | 通过 | 后端 `SessionStatus` 和前端 `SessionStatus` union 均移除 `starting`；create/start 成功返回 `running`，失败走异常。 |
| 2 | 统一状态模型 | 通过 | `running/disconnected/stopped` 由 live tmux window 与 ttyd port 推导；非 stopped entry 保持现有 live refresh 模型。 |
| 3 | stopped 历史 runtime 字段不参与判断 | 通过 | stopped entry 在单 session refresh 和批量 refresh 中直接返回，不检查历史 tmux/ttyd；terminal proxy 对 stopped 拒绝。 |
| 4 | disconnected 表示 tmux 存在但 ttyd 不可用 | 通过 | 现有 refresh 逻辑保留该判定；前端继续展示“重连会话”。 |
| 5 | running 必须有可用 ttyd proxy target 和 live tmux window | 通过 | `terminal_proxy_target()` refresh 后仅允许 `RUNNING` 且 port 有效的 entry 返回 proxy target。 |
| 6 | `terminal_proxy_target()` 不只相信 persisted status | 通过 | 仍调用 `_refresh_entry()`；stopped 不会因历史 port 恢复 running。 |
| 7 | `/session` 两阶段加载且 refresh 前不打开 stale iframe | 通过 | `AppShell` 增加 runtime verified gate；`refresh=false` 数据只展示结构，旧 session 不进入 terminal iframe。 |
| 8 | create/start/stop/delete 沿用局部响应更新 | 通过 | create/start 的 fresh response 可立即打开；stop/delete 保持局部更新，不强制重新拉 tree。 |
| 9 | stop/delete 资源清理与记录边界 | 通过 | 本次未改变 stop/delete 基础清理语义；测试覆盖 stopped proxy 拒绝和 stopped 记录保留。 |
| 10 | FastAPI/backend 重启后 tmux 存在显示 disconnected | 通过 | 现有测试继续覆盖 tmux window 存在但 ttyd 不可用时标记 disconnected。 |
| 11 | tmux/server 重启后 tmux 不存在显示 stopped | 通过 | 现有测试继续覆盖 tmux window 消失时降级 stopped。 |
| 12 | stopped 历史 port 不影响端口分配 | 通过 | `_start_entry()` used ports 跳过 stopped entry；新增测试验证可复用历史 stopped port。 |
| 13 | 增加后端测试覆盖 | 通过 | `tests/test_services.py` 新增/更新 stopped refresh、start、port、proxy 等测试。 |
| 14 | 增加或更新前端测试/类型检查 | 部分通过 | 当前项目未确认组件测试入口；通过 `vue-tsc`、ESLint 和 build 验证 union、props、模板绑定和 i18n 引用。 |
| 15 | 覆盖性能风险 | 通过 | stopped entry 不参与 live checks；批量 refresh 仍使用 tmux listing，不引入首屏 per-session 串行探测。 |

## Spec alignment

基于已接受的规格文档：

- `docs/spec/20260617-session-runtime-state-consistency.md`

核对结果：实现遵循 Spec 的关键设计决策。

- `SessionStatus` 移除 `STARTING`，不增加历史 `status="starting"` 兼容或迁移。
- `create()` 不再构造对外 starting entry；内部草稿使用 `STOPPED`，成功后 `_start_entry()` 返回 `RUNNING`。
- stopped entry 在 `_refresh_entry()` 和 `_refresh_entry_from_tmux_listing()` 中跳过 live refresh。
- `_start_entry()` 的业务 used ports 跳过 stopped entries，仍保留 `PortAllocator` 的 OS 端口可用性保护。
- running/disconnected refresh 仍使用现有 tmux window + ttyd port 模型。
- refresh 状态变化更新 `updated_at`，降级 stopped 时不清空 `tmux_window_id`。
- `/api/session-tree?refresh=false` 的前端使用限制已落实为 `AppShell` 的 runtime verified gate。
- create/start/stop/delete API shape 未改变，前端继续按局部响应更新。
- 前端业务状态和 i18n 删除 `starting`；`startingSessionId` 保留为 action loading 状态。
- workspace 聚合优先级变为 `running > disconnected > failed > stopped`。

## Plan alignment

基于已接受的计划文档：

- `docs/plan/20260617-session-runtime-state-consistency.md`

核对结果：Implementation 基本按 Plan 执行。

### 已完成的 Plan steps

1. 后端删除 `SessionStatus.STARTING`。
2. `create()` 不再构造 starting entry。
3. stopped entry 跳过 live refresh。
4. 状态变化时更新 `updated_at`，降级 stopped 不清空 `tmux_window_id`。
5. 端口分配跳过 stopped entries。
6. 后端删除 starting 分支和 workspace 聚合优先级。
7. 前端类型、状态分支、i18n 删除业务 `starting`。
8. `/session` runtime state verified 由 `AppShell` 管理，`SessionTerminal` 不承担 refresh gate。
9. 后端服务测试已更新。
10. 前端通过 typecheck/lint/build 验证。

### 与 Plan 的差异

- `SessionTerminal.vue` 未修改。这符合最终职责边界：父级 `AppShell` 过滤传入的 sessions/session，并在 `/session` 未验证时显示页面级状态提示，`SessionTerminal` 不需要感知 gate。
- 未新增前端组件测试。当前验证使用现有前端命令入口 `typecheck`、`lint`、`build`；这是 Plan 中允许的路径，因为未确认项目已有组件测试入口。

## Actual diff summary

### Process documents

- 新增 `docs/requirement/20260617-session-runtime-state-consistency.md`
- 新增 `docs/spec/20260617-session-runtime-state-consistency.md`
- 新增 `docs/plan/20260617-session-runtime-state-consistency.md`
- 新增 `docs/verification/20260617-session-runtime-state-consistency.md`

### Backend

- `src/termbridge/models.py`
  - 删除 `SessionStatus.STARTING`。
- `src/termbridge/services.py`
  - create 草稿 entry 使用 `STOPPED`。
  - start stopped entry 时不信任历史 recorded window id。
  - port allocation 跳过 stopped entries。
  - stopped/failed entry 跳过 refresh。
  - 状态变化时更新 `updated_at`。
  - workspace 聚合删除 starting 优先级。
- `tests/test_services.py`
  - 增加 create 返回 running 断言。
  - 调整 stopped terminal proxy 断言。
  - 新增 stopped start、port、refresh、list_tree 相关测试。

### Frontend

- `web/src/types/sessions.ts`
  - 删除 `'starting'`。
- `web/src/components/AppShell.vue`
  - 增加 `sessionRuntimeStateVerified` 和 `freshTerminalSessionIds`。
  - live refresh 完成前禁止旧 session 打开 terminal。
  - create/start fresh response 可立即打开。
  - `/session` 未验证时显示状态检查中主面板。
  - `SessionTerminal` 仅接收 runtime 可用 sessions。
- `web/src/components/SessionList.vue`
  - 新增 `runtimeStateVerified` prop。
  - 未验证时显示 loading/neutral 状态。
  - 未验证时禁用 select/start/stop/remove 这些 runtime 操作。
  - 删除业务 `starting` 样式和 active 判断。
- `web/src/i18n/locales/en-US.json`
  - 删除 `session.status.starting`，新增 checking 文案。
- `web/src/i18n/locales/zh-CN.json`
  - 删除 `session.status.starting`，新增 checking 文案。

## Expected vs actual changed files

| Plan expected | Actual | 结果 |
|---|---|---|
| `src/termbridge/models.py` | changed | 符合 |
| `src/termbridge/services.py` | changed | 符合 |
| `tests/test_services.py` | changed | 符合 |
| `tests/test_api.py` if needed | unchanged | 未发现需要更新的 API status/schema 断言；全量测试通过 |
| `web/src/types/sessions.ts` | changed | 符合 |
| `web/src/components/AppShell.vue` | changed | 符合 |
| `web/src/components/SessionList.vue` | changed | 符合 |
| `web/src/components/SessionTerminal.vue` | unchanged | 符合最终职责边界；父级过滤，不下沉 gate |
| `web/src/i18n/locales/en-US.json` | changed | 符合 |
| `web/src/i18n/locales/zh-CN.json` | changed | 符合 |

## Command results

### Backend

```powershell
uv run pytest tests/test_services.py
```

结果：通过。

```text
49 passed in 1.78s
```

```powershell
uv run pytest
```

结果：通过。

```text
162 passed, 1 warning in 4.04s
```

warning：

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

该 warning 来自依赖/测试客户端，不是本次 session 状态逻辑回归。

```powershell
uv run ruff check src tests
```

结果：通过。

```text
All checks passed!
```

```powershell
uv run mypy src
```

结果：通过。

```text
Success: no issues found in 15 source files
```

### Frontend

```powershell
npm --prefix web run typecheck
```

结果：通过。

```text
vue-tsc --noEmit
```

```powershell
npm --prefix web run lint
```

结果：通过。

```text
eslint .
```

```powershell
npm --prefix web run build
```

结果：构建成功。

```text
vite v8.0.16 building client environment for production...
✓ 2391 modules transformed.
✓ built in 452ms
```

build 输出两个非阻塞 warning：

1. `node_modules/@vueuse/core/dist/index.js` 中 `/* #__PURE__ */` annotation 位置被 Rolldown 忽略。
2. 产物 chunk 超过 500 kB 的 Vite/Rolldown 警告。

这些 warning 来自依赖或打包体积提示，不是本次状态一致性实现引入的编译错误。

## Starting reference check

在产品代码中，业务 `starting` 状态已移除。剩余匹配分为三类：

1. 本任务和历史过程文档中的说明。
2. `startingSessionId`，表示前端 start action pending，不是业务 status。
3. 通用脚本日志文本，例如 “starting container/process”。

未发现产品模型、前端 `SessionStatus` union 或 i18n 中仍暴露 `session.status.starting`。

## Missed or expanded scope

### 未完成 / 未执行

- 未执行手工浏览器验证。原因：当前 Verification 以自动化命令和 diff 对照为主；手工场景需要实际运行服务和 UI。
- 未新增前端组件测试。原因：当前项目未确认已有组件测试入口；已通过 typecheck/lint/build 覆盖类型、模板、i18n key 和构建链路。
- 未清理 `.termbridge/sessions.json` 历史数据。原因：用户明确选择不做历史 `status="starting"` 兼容或迁移，本任务不负责状态文件清理。

### 范围扩展

- 无不合理范围扩展。
- `AppShell.vue` 的 runtime-unverified 主面板明确限定到 `/session` route，避免影响 `/environment` 和 `/shortcuts` 页面。

## Risks

1. 如果用户本地 `.termbridge/sessions.json` 仍包含 `status="starting"`，加载会失败；这是需求和 Spec 明确接受的风险。
2. stopped entry 不再 live refresh；如果历史 stopped entry 仍有 orphan tmux/ttyd 资源，系统不会自动把它恢复为 running/disconnected，需要 stop/delete/close-all 或手工清理。
3. 未做浏览器手工验证，因此视觉和交互细节仍建议用户在真实 `/session` 页面人工检查一次。
4. build chunk size warning 仍存在，但不是本任务引入的功能风险。

## Conclusion

Verification 通过。

本次实现与 Requirement / Spec / Plan 对齐：业务状态移除 `starting`，stopped 历史 runtime 字段不再参与 terminal proxy、端口分配或 UI runtime availability；`/session` 两阶段加载保留结构展示性能，同时通过 `AppShell` 的 runtime verified gate 防止 refresh 前打开 stale terminal iframe。

自动化检查全部通过：

- 后端定向测试通过。
- 后端全量测试通过。
- Python lint/typecheck 通过。
- 前端 typecheck/lint/build 通过。
