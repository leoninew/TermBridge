# 简化 stopped 会话语义范围说明

Review status: Accepted

当前：轻量模式 / light，范围说明 / Scope note

## Goal

- 简化会话状态语义：`stopped` 统一表示 ttyd 连接已经停止；手动 Stop 会清理对应 managed tmux window，但 Start 允许复用仍存在的记录 window 或同名 window。
- Stop 操作应停止 ttyd process、kill managed tmux window，并清空 `tmux_window_id` / URL / pid。
- Start stopped 会话时优先复用已记录且仍存在的 managed tmux window；记录 id 缺失或失效时，允许按同 workspace tmux session 下的同名 window 复用；都不存在时再创建新的 managed tmux window，然后启动 ttyd attach。
- 减少 UI 和用户理解成本，不再区分 “stopped 但 window 保留” 与 “stopped 且 window 缺失”。
- 会话状态、操作 icon 和文案与 tmux window 生命周期保持一致。

## Non-goal

- 不改变 workspace tmux session 的一级结构：同一环境 + 目录仍对应一个 workspace tmux session。
- 不改变 `.termbridge/sessions.json` 的三层 schema。
- 不引入 `tmux_window_status` 或额外状态字段。
- 不恢复旧 schema 兼容或迁移逻辑。

## Acceptance

- `SessionService.stop()` / `_stop_entry()` 停止会话时会清理 managed tmux window，并将 entry 标记为 `stopped`、清空 `tmux_window_id`、`pid`、`url`。
- `SessionService.start()` / `POST /api/sessions/{session_id}/start` 承载 start stopped session 语义：不保留 restart API；优先复用记录 id 对应的 managed window，其次按同 workspace session 下的同名 window 复用，最后创建新的 managed tmux window，并更新 `tmux_window_id`。
- `close_all()` 与 stop/start 新语义一致，保持 records 但清理 tmux resources。
- 前端 running 会话的停止操作使用 play-off 语义 icon；stopped 会话使用 Play 启动会话。
- 文案避免暗示 stopped 状态仍保留 tmux window，也避免使用“重新开始/重新启动”暗示恢复旧 window。
- 测试覆盖 stop 清理 window、start stopped session 复用已有 window、按同名 window 复用、缺失时新建 window、close all 保留 records 但清理 resources。

## Risk

- 该需求会覆盖上一轮“停止后恢复复用原 managed tmux window”的设计决策，需要同步更新相关 spec/verification 文档中被覆盖的描述。
- Stop 后 tmux window 内容不再保留；这是本次简化语义的有意行为。
- 若用户希望保留运行上下文，应通过 tmux/session 内部机制或未来单独能力处理，不由 stopped 状态承担。

## User review notes

- 用户认为 stopped 语义应简化：停止就表示 tmux window 没有了，不区分 `stopped` 与 `stopped + tmux_window_id = null`。
- 用户随后确认 start 需要考虑已有 tmux window：如果同目录同名 window 存在，说明用户知道自己在做什么，可以复用该 window。
