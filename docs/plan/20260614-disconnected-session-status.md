# disconnected 会话状态语义实施计划

- Flow mode: strict
- Stage: Plan
- Review status: Accepted
- Date: 2026-06-14

## Requirement and Spec basis

- Requirement: `docs/requirement/20260614-disconnected-session-status.md`，状态 `Accepted`。
- Spec: `docs/spec/20260614-disconnected-session-status.md`，状态 `Accepted`。

本计划实现 `disconnected` 会话状态，用于表达 ttyd proxy 不可用但 tmux window 仍存在、可恢复连接的中间态。

## Implementation steps

### 1. 扩展共享状态模型

修改：

- `src/termbridge/models.py`
- `web/src/types/sessions.ts`

内容：

1. 在 Python `SessionStatus` 中增加：
   ```py
   DISCONNECTED = "disconnected"
   ```
2. 在前端 `SessionStatus` union 中增加：
   ```ts
   'disconnected'
   ```

注意：该值会进入 `.termbridge/sessions.json` 持久化数据和 API response。无需单独迁移旧数据，因为旧数据不包含该值；旧的 `stopped + tmux_window_id` 记录由状态刷新逻辑识别。

### 2. 重写后端状态刷新逻辑

修改：

- `src/termbridge/services.py`

重点函数：

- `SessionService._refresh_entry()`
- `SessionService._workspace_response()`

计划：

1. 在 `_refresh_entry()` 中新增 helper 式局部判断，避免重复 tmux 探测：
   - 仅当 `entry.tmux_window_id` 非空时调用 `terminal_service.tmux_window_exists(...)`。
   - `entry.status == RUNNING and entry.pid is not None` 时额外检查 `process_adapter.is_running(...)`。
2. 状态转换：
   - running + process alive + tmux exists => 保持 running。
   - running + process missing + tmux exists => disconnected，清空 `pid`/`url`，保留 `tmux_window_id`。
   - running + process missing + tmux missing => stopped，清空 `pid`/`url`/`tmux_window_id`。
   - disconnected + tmux exists => 保持 disconnected。
   - disconnected + tmux missing => stopped，清空 `tmux_window_id`。
   - stopped + tmux_window_id + tmux exists => disconnected。
   - stopped + tmux_window_id + tmux missing => stopped，清空 `tmux_window_id`。
3. `STARTING` / `FAILED` 暂不新增刷新行为，除非现有代码路径要求清理。
4. `_workspace_response()` 聚合优先级调整为：
   ```text
   running > disconnected > starting > failed > stopped
   ```
   这样只有 disconnected entries 的 workspace 不会被显示为 stopped。

### 3. 核对启动、停止、删除和 proxy 语义

修改：

- `src/termbridge/services.py`

计划：

1. `start()`：
   - 现有非 running 路径应可复用 disconnected 的 `tmux_window_id`。
   - 保留“如果 window 不存在，则 find by name 或 create”的兜底。
   - 如有必要，在 `_refresh_entry()` 后确保 disconnected 能进入 `_start_entry()`。
2. `terminal_proxy_target()`：
   - 保持 `entry.status != RUNNING or entry.pid is None` 时拒绝。
   - 不允许 disconnected 直接 proxy。
3. `stop()` / `delete()` / `close_all()`：
   - 保持显式清理 tmux window 的现有语义。
   - close_all 写回 `stopped` 并清空 `tmux_window_id`。

### 4. 更新前端 i18n 和状态样式

修改：

- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`
- `web/src/components/SessionList.vue`
- `web/src/components/SessionTerminal.vue`
- `web/src/components/SessionCard.vue`

计划：

1. i18n 状态文案：
   - zh-CN: `session.status.disconnected = "连接断开"`
   - en-US: `session.status.disconnected = "Disconnected"`
2. 终端区域增加 disconnected 专用文案：
   - zh-CN: `终端连接已断开，底层会话仍在，可恢复连接。`
   - en-US: `The terminal connection is disconnected; the underlying session still exists and can be restored.`
3. `SessionList.vue`：
   - 从 `@lucide/vue` 引入 `Unplug` 和 `Play`（若 `Play` 已在该组件不存在则新增）。
   - `sessionStatusIconClass()` 为 disconnected 返回 amber/orange 色。
   - session 节点 icon：`disconnected` 使用 `Unplug`，其他状态保持现有图标或按现有逻辑。
   - disconnected 操作区同时显示启动按钮和删除按钮。
   - running 仍显示停止按钮。
   - starting 仍显示 loading。
4. `SessionTerminal.vue`：
   - `item.status === 'disconnected'` 时显示专用文案。
   - disconnected 状态显示启动按钮，行为复用 `emit('start', item)`。
5. `SessionCard.vue`：
   - 补充 `statusClass.disconnected`，避免 Record 类型缺值。
   - disconnected 显示启动按钮，同时保留删除按钮。

### 5. 更新测试

修改：

- `tests/test_services.py`
- 视需要修改 `tests/test_api.py`

后端测试用例计划：

1. running entry 的 ttyd process dead 但 tmux window exists => 刷新为 disconnected，保留 `tmux_window_id`，清空 `pid` 和 `url`。
2. running entry 的 ttyd process dead 且 tmux window missing => 刷新为 stopped，清空 `tmux_window_id`。
3. historical stopped entry with `tmux_window_id` and existing tmux window => 刷新为 disconnected。
4. disconnected entry with missing tmux window => 刷新为 stopped。
5. `start()` disconnected entry with existing window => 不创建新 window，复用原 window 启动 ttyd attach。
6. `terminal_proxy_target()` disconnected entry => raises `SessionTerminalUnavailableError`。
7. workspace aggregation：只有 disconnected entries 时 workspace status 为 disconnected；有 running 时为 running。

前端检查通过 typecheck 覆盖 `SessionStatus` union 和 `Record<Session['status'], string>` 完整性。必要时增加组件测试；当前项目如果没有现有组件测试入口，则不新增测试框架。

### 6. 更新过程文档

后续 Verification 阶段更新：

- `docs/verification/20260614-disconnected-session-status.md`

记录：

- 实际 diff summary。
- requirement/spec/plan alignment。
- 测试、lint、typecheck 结果。
- 未完成的浏览器手动验证项。
- 建议 commit message。

## Files to change

### Product code

- `src/termbridge/models.py`
- `src/termbridge/services.py`
- `web/src/types/sessions.ts`
- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`
- `web/src/components/SessionList.vue`
- `web/src/components/SessionTerminal.vue`
- `web/src/components/SessionCard.vue`

### Tests

- `tests/test_services.py`
- `tests/test_api.py`（如 API-facing behavior 需要补充）

### SpecFlow docs

- `docs/verification/20260614-disconnected-session-status.md`（Verification 阶段）

## Verification plan

### Backend checks

从仓库根目录运行：

```bash
uv run ruff check src/termbridge/models.py src/termbridge/services.py tests/test_services.py tests/test_api.py
uv run mypy src/termbridge/models.py src/termbridge/services.py tests/test_services.py tests/test_api.py
uv run pytest tests/test_services.py tests/test_api.py
```

### Frontend checks

从 `web/` 目录运行：

```bash
yarn lint
yarn typecheck
```

### Manual verification

建议手动验证：

1. 准备一个已有 tmux window 的会话，然后终止对应 ttyd pid，不删除 tmux window。
2. 刷新 TermBridge，会话应显示 `连接断开`、unplug icon、启动按钮和删除按钮。
3. 点击启动按钮，应恢复到原 tmux window 内容。
4. 手动删除 tmux window，再刷新，应变为 stopped。
5. running 会话仍显示 terminal iframe；stopped 会话仍按原 stopped 语义显示。

## Rollback

如果实现后发现状态流转或 UI 行为异常，回滚方式：

1. 移除 `SessionStatus.DISCONNECTED` 和前端 union 值。
2. 将 `_refresh_entry()` 恢复为 running/stopped 二元刷新。
3. 移除 i18n disconnected 文案和 UI 分支。
4. 删除 disconnected 相关测试。

注意：如果已经写入 `.termbridge/sessions.json` 中的 `status=disconnected`，回滚前需要将这些记录转换回 `stopped`，否则旧代码无法解析新增 enum 值。

## Risks

1. 历史数据兼容：新增 enum 写入持久化后，旧版本代码无法读取 `disconnected`。
2. 外部 tmux 命令成本：刷新 stopped + tmux_window_id 会多一次 `tmux_window_exists` 检查，但只针对有 window id 的记录。
3. UI 操作密度：disconnected 同时显示启动和删除，列表空间较窄时需确认不会挤压会话名称。
4. 当前工作区已有拖拽排序、ttyd 主题、UI opacity/缩进等未提交改动，Verification 需要明确本功能与既有 diff 的边界。

## Blockers

暂无阻塞项。等待用户确认 Plan 后进入 Implementation。
