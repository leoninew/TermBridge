# disconnected 会话状态语义

- Flow mode: strict
- Stage: Requirement
- Review status: Accepted
- Date: 2026-06-14

## Background

当前 TermBridge 的会话状态把 Web terminal proxy（ttyd 进程）和底层 tmux window 的状态折叠在 `running` / `stopped` 中。实际使用中存在一种重要中间态：ttyd 进程不可用，但对应的 tmux window 仍存在。例如用户在目录 `D:\SourceCodes\mywork\pomelo-orbit` 的“代码提交”会话界面看到“当前状态为 已停止，终端暂不可用”，但 `tmux list-windows -a` 仍能看到对应窗口：

```text
tb_cyg_3d134fa1d1d50ef3:1: 代码提交- (1 panes) [201x50]
```

这种情况下点击启动会话后，系统会复用原有 tmux window 重新启动 ttyd attach，而不是创建全新的底层会话。现有 `stopped` 文案和删除 icon 容易让用户误解为底层会话已经停止或只能删除。

## Goals

1. 增加一个明确的 `disconnected` 会话状态，表示：Web terminal proxy / ttyd 当前不可用，但底层 tmux window 仍存在，可恢复连接。
2. 将 `stopped` 语义收敛为：Web terminal proxy 不可用，并且没有可复用的 tmux window。
3. 前端会话列表和终端区域应把 `disconnected` 展示为“连接断开”语义，而不是普通“已停止”。
4. 对 `disconnected` 会话执行启动操作时，应复用已存在的 tmux window 并重新启动 ttyd proxy。
5. 如果原本 `disconnected` 的会话对应 tmux window 后续不存在，应刷新为 `stopped`。
6. 兼容既有持久化数据中 `status=stopped` 但仍保留 `tmux_window_id` 且 tmux window 实际存在的记录，使其可被识别为 `disconnected`。

## Non-goals

1. 不改变 tmux session/window 的命名规则。
2. 不改变 ttyd 启动命令、认证、端口分配和 terminal proxy 路由语义，除非实现状态识别时发现必要的最小调整。
3. 不引入自动重连或后台守护进程来持续重启 ttyd。
4. 不修改用户的 tmux window 内容或主动关闭可恢复的 tmux window。
5. 不把 `disconnected` 设计成 WebSocket 瞬时断线状态；它描述的是 TermBridge 管理的 ttyd proxy 进程不可用但 tmux window 仍存在。

## User scenarios

1. 用户打开已有会话列表，某个会话的 ttyd 进程已经不存在，但 tmux window 仍存在；界面应显示“连接断开”状态，并同时提供启动和删除 icon 按钮。
2. 用户点击 `disconnected` 会话的恢复/启动入口后，应重新启动 ttyd 并 attach 到原 tmux window，原窗口内容保留。
3. 用户手动在 tmux 中删除了某个 previously disconnected 的 window 后，TermBridge 下次刷新应将该会话变为 `stopped`。
4. 用户关闭所有会话或删除会话时，仍应按显式操作清理 ttyd 进程和 tmux window。

## Acceptance criteria

1. `SessionStatus` 增加 `disconnected`，API response 和前端类型均支持该状态。
2. 后端刷新状态时能识别：
   - ttyd pid 存活且 tmux window 存在 => `running`。
   - ttyd pid 不存在/不可用但 tmux window 存在 => `disconnected`。
   - ttyd pid 不存在/不可用且 tmux window 不存在 => `stopped`。
3. 既有 `status=stopped` 且 `tmux_window_id` 存在的记录，如果 tmux window 实际存在，应刷新为 `disconnected`。
4. `start()` 对 `disconnected` 会话复用原 tmux window 重新启动 ttyd proxy。
5. `terminal_proxy_target()` 仍只允许 `running` 且有有效 pid 的会话提供 terminal proxy target。
6. 会话列表中 `disconnected` 状态使用 unplug icon 表示连接断开，并同时显示启动和删除 icon 按钮。
7. 终端区域中 `disconnected` 状态应显示区别于 `stopped` 的文案，例如“终端连接已断开，底层会话仍在，可恢复连接”。
8. workspace 聚合状态应考虑 `disconnected`：如果没有 running 但存在 disconnected，会话组不应被简单视为完全 stopped。
9. 增加后端测试覆盖状态刷新、历史 stopped 记录升级、start 复用 tmux window。
10. 增加或更新前端类型/i18n/组件逻辑，并通过项目 lint/typecheck。

## Decisions

- 状态命名使用 `disconnected`，不用 `detached` 或 `recoverable`。
- `disconnected` 表示 ttyd proxy 不可用但 tmux window 存在，不表示普通 WebSocket 临时断开。
- 当前阶段只做状态表达和恢复入口，不做后台自动重启 ttyd。
- `disconnected` 在会话列表中使用 unplug icon，同时显示启动和删除 icon 按钮。
- 中文状态文案使用“连接断开”。
- API response 只通过 `status=disconnected` 表达该状态，不额外增加 `has_tmux_window` 字段。

## Risks and assumptions

1. `tmux_window_exists` 的调用成本依赖具体 host/runtime 实现；当前代码已在刷新 running entry 时调用该方法，预计新增 disconnected 识别成本可控。
2. 对历史 `stopped + tmux_window_id` 记录做 tmux 探测可能比当前逻辑多一次外部命令调用；需要在 Spec 阶段评估是否只在有 `tmux_window_id` 时探测。
3. 前端已有若干位置根据 `status === 'stopped'` 决定按钮和样式，新增状态需要逐一检查，避免出现不可恢复或误删入口。
4. 当前工作区已有拖拽排序、ttyd 主题和 UI 样式相关未提交改动；本需求应保持文档和代码边界清晰，验证时明确 diff 范围。

## Open questions

暂无必须阻塞进入 Spec 的问题。以下事项已由用户确认：

1. `disconnected` 的列表状态 icon 使用 unplug icon。
2. `disconnected` 会话列表操作同时显示启动和删除 icon 按钮。
3. 中文状态文案使用“连接断开”。
4. API response 只使用 `status=disconnected`，不额外暴露 `has_tmux_window`。
