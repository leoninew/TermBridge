# disconnected 会话状态语义规格

- Flow mode: strict
- Stage: Spec
- Review status: Accepted
- Date: 2026-06-14

## Requirement basis

基于已接受的需求文档：

- `docs/requirement/20260614-disconnected-session-status.md`

目标是在现有 `running` / `stopped` 之间增加 `disconnected` 状态，用于表达：TermBridge 管理的 ttyd proxy 进程不可用，但底层 tmux window 仍存在，用户可以恢复连接。

## Overview

现有会话状态实际同时承载两类资源状态：

1. ttyd proxy 进程是否存活，决定 iframe/Web terminal 是否可用。
2. tmux window 是否存在，决定底层会话内容是否可恢复。

新增 `disconnected` 后，状态语义调整为：

| 状态 | ttyd proxy / pid | tmux window | 用户语义 |
| --- | --- | --- | --- |
| `starting` | 正在创建 | 未定/准备中 | 正在启动 |
| `running` | 存活 | 存在 | 终端可用 |
| `disconnected` | 不可用 | 存在 | 连接断开，可恢复 |
| `stopped` | 不可用 | 不存在 | 已停止 |
| `failed` | 启动失败或异常 | 未定 | 失败 |

`disconnected` 只通过 API response 的 `status=disconnected` 表达，不新增 `has_tmux_window` 字段。

## Design decisions

### 1. Status enum

在 `src/termbridge/models.py` 的 `SessionStatus` 中增加：

```py
DISCONNECTED = "disconnected"
```

该状态会进入持久化 JSON 和 API response。Pydantic enum 反序列化会兼容已有旧状态；新增状态不需要迁移旧文件格式。

### 2. Backend status refresh

核心变更点是 `SessionService._refresh_entry()`。

当前逻辑只刷新 `RUNNING + pid` 的 entry。新逻辑需要覆盖：

1. `RUNNING`：
   - pid alive 且 tmux window exists => 保持 `running`。
   - pid dead/missing 且 tmux window exists => `disconnected`，清空 `pid` 和 `url`，保留 `tmux_window_id`。
   - pid dead/missing 且 tmux window missing => `stopped`，清空 `pid`、`url`、`tmux_window_id`。
2. `DISCONNECTED`：
   - tmux window exists => 保持 `disconnected`。
   - tmux window missing => `stopped`，清空 `tmux_window_id`。
3. 历史 `STOPPED + tmux_window_id`：
   - tmux window exists => 升级为 `disconnected`。
   - tmux window missing => 保持/刷新为 `stopped` 并清空 `tmux_window_id`。
4. `STARTING` 和 `FAILED`：
   - 不在本次需求中引入额外刷新语义，保持现有行为，除非测试发现现有行为已经依赖 stopped/running 二元判断。

为避免重复执行 tmux 命令，Spec 建议在 `_refresh_entry()` 内仅当 `entry.tmux_window_id` 非空时调用 `tmux_window_exists()`。

### 3. `start()` behavior

`SessionService.start()` 当前已经在非 running 时检查 tmux window：

```py
if not terminal_service.tmux_window_exists(...):
    find by name or create window
```

新增 `disconnected` 后沿用该路径：

- `disconnected` 且 tmux window exists：直接 `_start_entry()`，复用原 `tmux_window_id`。
- `disconnected` 但 tmux window 已被外部删除：刷新为 stopped，然后通过现有 find/create 逻辑恢复或创建 window。
- `running` 仍返回当前 response，不重复启动 ttyd。

### 4. `terminal_proxy_target()` behavior

保持严格要求：

```text
status == running AND pid is not None
```

`disconnected` 不提供 proxy target，应继续抛出 `SessionTerminalUnavailableError`，让前端展示恢复入口。

### 5. Stop / delete / close all behavior

显式停止和删除仍是破坏性会话资源操作，语义不变：

- `stop(session)`：终止 ttyd pid，并 kill 对应 tmux window，最终状态为 `stopped`，`tmux_window_id=None`。
- `delete(session)`：终止 ttyd pid，kill 对应 tmux window，并从 repository 删除 entry。
- `close_all()`：终止所有 ttyd pid，kill 所有 tmux windows/sessions，并把 remaining entries 写为 `stopped`。

这保证 `disconnected` 不会改变用户显式关闭/删除时的清理语义。

### 6. Workspace aggregated status

`SessionWorkspaceResponse.status` 需要考虑 `disconnected`：

优先级建议：

```text
running > disconnected > starting > failed > stopped
```

更保守的实现也可使用：

```text
running > disconnected > stopped
```

但因为现有 UI/数据模型已有 `starting`、`failed`，Spec 建议完整实现优先级，避免 workspace 在只有 disconnected entries 时被误显示为 stopped。

### 7. Frontend type and i18n

`web/src/types/sessions.ts`：

```ts
export type SessionStatus = 'starting' | 'running' | 'disconnected' | 'stopped' | 'failed'
```

`web/src/i18n/locales/zh-CN.json`：

```json
"disconnected": "连接断开"
```

`en-US.json`：

```json
"disconnected": "Disconnected"
```

终端区域新增 disconnected 专用文案，例如：

```json
"disconnected": "终端连接已断开，底层会话仍在，可恢复连接。"
```

英文对应：

```json
"disconnected": "The terminal connection is disconnected; the underlying session still exists and can be restored."
```

### 8. Frontend session list UI

`web/src/components/SessionList.vue`：

- `disconnected` 状态 icon 使用 lucide `Unplug`。
- `disconnected` 状态文字颜色建议使用 amber/orange，区别于 stopped 的 slate 和 failed 的 red。
- `disconnected` session node 同时显示：
  - 启动 icon 按钮：`Play` / loading `Loader2`。
  - 删除 icon 按钮：`Trash2`。
- `running` 仍显示 stop `Ban`。
- `stopped` 仍显示启动或删除按钮的现有语义需要在 Plan 阶段结合当前 UI 再核对；需求明确的是 disconnected 必须同时有启动和删除。

### 9. Frontend terminal UI

`web/src/components/SessionTerminal.vue`：

- `item.status !== 'running'` 的通用提示保留为 fallback。
- 对 `item.status === 'disconnected'` 单独显示“连接断开”语义文案。
- disconnected 状态应显示启动/恢复按钮，调用现有 `start` emit；按钮文案可沿用“启动会话”或新增“恢复连接”。需求目前只要求有启动入口，不强制改按钮文案。

### 10. API compatibility

不新增 response 字段。客户端只通过 `status` 分辨。

历史 JSON 中不存在 `disconnected` 的记录无需迁移；刷新时若满足 `stopped + tmux_window_id exists + tmux window exists`，会自动变为 `disconnected` 并保存。

## Affected components

### Backend

- `src/termbridge/models.py`
  - 增加 `SessionStatus.DISCONNECTED`。
- `src/termbridge/services.py`
  - 调整 `_refresh_entry()` 状态刷新。
  - 调整 `_workspace_response()` 聚合状态。
  - 核对 `start()` / `terminal_proxy_target()` / `stop()` / `delete()` / `close_all()` 是否符合新语义。
- `tests/test_services.py`
  - 增加 disconnected 刷新、历史 stopped 升级、tmux window missing 降级、start 复用窗口等测试。
- `tests/test_api.py`
  - 如 API schema 或 UI-facing behavior 需要，可补充 response status 测试。

### Frontend

- `web/src/types/sessions.ts`
  - 增加 status union 值。
- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`
  - 增加 `disconnected` 状态和终端提示文案。
- `web/src/components/SessionList.vue`
  - 引入 `Unplug` / `Play` 或复用已有图标。
  - 调整状态 icon、状态颜色和操作按钮。
- `web/src/components/SessionTerminal.vue`
  - disconnected 专用提示和启动入口。
- `web/src/components/SessionCard.vue`
  - 若该组件仍在页面使用，需要增加 disconnected badge 和操作按钮逻辑，避免类型不完整。

## Interfaces

### SessionStatus

新增枚举值：

```text
disconnected
```

### SessionResponse

不新增字段，仅可能返回：

```json
{
  "status": "disconnected"
}
```

### Frontend status labels

中文：

```text
连接断开
```

英文：

```text
Disconnected
```

## Alternatives considered

1. **使用 `detached` 命名**
   - 优点：贴近 tmux 语义。
   - 缺点：用户指定使用 `disconnected`，且 `disconnected` 对 UI 更直观。

2. **不新增状态，只新增 `has_tmux_window` 字段**
   - 优点：不扩展 enum。
   - 缺点：前端需要组合字段判断，API 语义分散；用户已决定只使用 `status=disconnected`。

3. **把 stopped + tmux_window_id 当作可恢复，不更新状态**
   - 优点：改动小。
   - 缺点：继续保留“已停止”误导，不满足需求。

4. **后台自动重启 ttyd**
   - 优点：用户可能不看到 disconnected。
   - 缺点：引入守护和资源策略，不在本需求范围。

## Technical questions

暂无阻塞问题。Plan 阶段需要进一步落到具体测试用例和 UI 按钮条件。

## Risks

1. 刷新 stopped + tmux_window_id 记录时会新增一次 tmux 探测，但只在 `tmux_window_id` 存在时执行，成本可控。
2. 如果外部 tmux window 被重命名但 window id 仍存在，应仍识别为 disconnected，因为恢复依赖 window id，不依赖名字。
3. 如果历史记录中 `tmux_window_id` 错误指向其他窗口，系统会按现有 window id 行为恢复；这是现有持久化数据可信度问题，本需求不新增校验。
4. 当前工作区存在其他未提交改动；后续 Plan/Verification 需要明确本 feature 的文件边界和验证范围。
