# Cygwin tmux 会话持久化需求

Review status: Accepted

当前：严格模式 / strict，需求 / Requirement

## Background

当前前端 session 对应一个后端 `ttyd` server 进程，但 `ttyd` 1.7.7 没有 `--reconnect` 参数。用户在 `cmd` 等终端里输入命令后刷新页面，虽然 session record 和 ttyd port 没变，但 ttyd 会为新 WebSocket 连接创建新的 child terminal，导致终端状态看起来像全新会话。

已确认：

- `ttyd --help` 没有 `--reconnect` 或等价 session resume 参数。
- Cygwin 环境存在 `tmux`：`/usr/bin/tmux`，版本 `tmux 3.2`。
- Cygwin tmux smoke test 通过：`new-session`、`has-session`、`kill-session` 可用。
- 已有后端单元测试验证 Cygwin terminal command 可以被包装成 `tmux new-session -A -s <session_id> ...`。

## Goals

1. 为 Cygwin 终端提供可选的 tmux 会话持久化能力。
2. 用户刷新前端页面后，重新连接同一个 session 时能回到同一个 tmux session，而不是全新 child terminal。
3. 保持现有默认行为不变：未启用 tmux persistence 的终端继续按当前方式启动。
4. 在终端管理中能配置 Cygwin 自定义终端是否启用 tmux persistence。
5. 删除前端 session 时，应清理对应 tmux session，避免长期残留。

## Non-goals

1. 本任务不解决原生 Windows `cmd` / `powershell` 的刷新保持问题。
2. 本任务不引入 ttyd 自身不存在的 reconnect 参数。
3. 本任务不要求跨后端重启恢复已有 tmux session 的完整生命周期管理。
4. 本任务不实现 screen 方案；先聚焦 Cygwin + tmux。
5. 本任务不改变现有 ttyd 端口分配和 session URL 结构。

## User scenarios

1. 用户创建一个启用 tmux persistence 的 Cygwin 终端配置。
2. 用户用该终端创建 session，并在终端内输入若干命令。
3. 用户刷新浏览器页面或重新进入同一个 session。
4. 页面重新连接 ttyd 后 attach 到同一个 tmux session，能看到原终端状态。
5. 用户删除该 session 后，后端尝试 kill 对应 tmux session。

## Acceptance criteria

- [ ] 终端模型支持 `session_persistence: "none" | "tmux"`，默认 `none`。
- [ ] Cygwin 终端启用 `tmux` 时，后端命令包装为 `tmux new-session -A -s <session_id> <terminal_command>`。
- [ ] direct / Windows 系统终端不受 tmux persistence 影响。
- [ ] 终端管理 UI 可以为 Cygwin 自定义终端配置 tmux persistence。
- [ ] 删除启用 tmux persistence 的 session 时，后端尝试清理对应 tmux session。
- [ ] 单元测试覆盖命令包装、默认行为、删除清理路径。
- [ ] 真实 Cygwin 环境中验证刷新页面后终端状态保持。

## Open questions

1. 删除 session 时如果 tmux kill 失败，是否只记录 warning 并继续删除 session？建议是继续删除，避免 UI 卡死。
2. tmux session name 是否直接使用后端 `session_id`？建议使用 `session_id`，因为它稳定且只包含安全字符。
3. tmux command 是否只包 terminal.command，不包 args？当前 Cygwin 自定义终端主要使用单字符串 command；如后续支持 Cygwin args，需要扩展 quoting 策略。

## Decisions

- 删除 session 时如果 tmux kill 失败，只记录 warning 并继续删除 session，避免 UI 卡死。
- tmux session name 直接使用后端 `session_id`，因为它稳定且只包含安全字符。
- tmux command 先只包装 Cygwin 自定义终端的单字符串 `terminal.command`；如后续支持 Cygwin args，再扩展 quoting 策略。
- 先只支持 Cygwin + tmux。
- 不处理 Windows 原生 cmd/powershell。
- 不使用不存在的 ttyd reconnect 参数。
- 默认行为保持 `session_persistence="none"`。
