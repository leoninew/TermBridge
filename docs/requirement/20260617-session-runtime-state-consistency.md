# 会话运行时状态一致性需求
最后修改时间: 2026-06-17 15:58:44

- Flow mode: strict
- Stage: Requirement
- Review status: Accepted
- Date: 2026-06-17

## Background

当前 TermBridge 的业务会话状态存在不自洽问题：持久化记录中的 `status`、`pid`、`port`、`url`、`tmux_window_id` 会与 live tmux / ttyd 资源不一致，导致 `/terminal/{session_id}/...` 偶发返回 `{"code":"conflict","error":"Session terminal is not running"}`，或者 UI 将实际可用/可恢复的会话显示为 stopped。

现场观察到的关键问题包括：

1. live `tmux list-windows -a` 中仍存在业务窗口，但持久化状态可能是 `stopped`。
2. live ttyd 进程和端口仍存在并响应 HTTP，但对应 session entry 可能仍标记为 `stopped`。
3. stopped 状态下历史 `pid`、`port`、`url`、`tmux_window_id` 可能仍残留，但业务语义上 stopped 会话不应依赖这些运行时字段。
4. 当前 `/session` 页为了性能首先加载会话列表；会话新建、启动、停止、删除操作也直接返回会话数据并更新前端状态。这些路径需要在保持性能的同时避免传播不自洽状态。
5. 历史 `disconnected` 设计已经区分 ttyd proxy 和底层 tmux window，但仍缺少统一的业务状态判定模型和规范化策略。
6. 现有 `starting` 语义不符合当前业务：新建会话是同步操作，不需要对外暴露 `starting` 状态。

本任务目标是重新定义并实现自洽的业务会话状态模型：业务会话是 TermBridge 持久化的 session entry；tmux window 和 ttyd process/port 是运行时资源，持久化中的运行时字段只能作为线索，不能作为最终真相。

## Goals

1. 明确定义业务意义上的“会话”状态：由 live tmux window 和 live ttyd proxy 资源推导，而不是相信 persisted `status`。
2. 将 `running`、`disconnected`、`stopped` 的业务语义和字段使用规则固定下来。
3. 消除 `starting` 状态语义；新建会话成功后直接返回 `running`，失败则返回错误，不产生需要用户感知的 starting 中间态。
4. 在 refresh / list / get / terminal proxy / create / start / stop / delete 等路径中消除状态不一致。
5. 防止非法持久化状态影响业务判断，例如 `status=stopped` 仍保留历史 `pid` / `port` / `url` / `tmux_window_id` 时，业务逻辑不应继续依赖这些字段。
6. 明确 stopped 会话不参与 `/session` 页 live 状态检查，也不应因历史运行时字段影响端口分配或 UI 展示。
7. 检查并调整 `/session` 页面数据策略，支持首屏两阶段加载，同时保持 create/start/stop/delete 操作沿用现有局部响应更新策略。
8. 保持性能目标：`/session` 初始渲染不能退回到对每个 session 做高成本串行探测；需要设计批量 refresh / 快速刷新策略。

## Non-goals

1. 不改变用户可见的业务入口概念：用户仍通过 `/session` 管理和打开会话。
2. 不改变 tmux session/window 的基础命名规则。
3. 不引入后台守护进程持续保活或自动重启 ttyd。
4. 不主动修改用户 tmux pane 内正在运行的业务命令。
5. 不把普通 WebSocket 瞬时断开直接定义为 `disconnected`；`disconnected` 表示 TermBridge 管理的 ttyd proxy 不可用但底层 tmux window 仍可恢复。
6. 不以牺牲 `/session` 页面性能为代价简单粗暴地在每个 UI 更新点全量串行探测所有 session。
7. 不要求 create/start/stop/delete 操作后统一重新拉取 `/api/session-tree`；这些 happy path 操作继续沿用现有返回数据更新前端的策略。

## User scenarios

### Happy path

1. 用户新建会话：
   - 系统创建业务 session entry。
   - 系统创建或复用 workspace 对应的 tmux session。
   - 系统创建 tmux window。
   - 系统同步启动 ttyd process 并分配 port。
   - 成功后业务状态为 `running`，终端可直接打开。
   - 失败则返回错误，不对外暴露 `starting` 状态。

2. 用户停止会话：
   - 系统关闭对应 ttyd process 和 port。
   - 系统关闭对应 tmux window。
   - 如果该 tmux window 是所在 tmux session 的最后一个 window，tmux session 也应关闭或不再存在。
   - 业务 session entry 保留，但状态为 `stopped`。
   - `/session` 页不再检查 stopped 会话是否仍有历史 live 资源；stopped 的历史运行时字段不参与 UI 可用性判断。

3. 用户删除会话：
   - 删除是业务操作。
   - 如果 session 仍有运行时资源，应先完成等价于“停止”的资源清理。
   - 然后删除业务 session entry。
   - 删除本身不再引入新的运行时状态语义。

4. 用户启动 stopped 会话：
   - 系统按业务 session entry 重新创建 tmux window 和 ttyd proxy。
   - 成功后返回 `running`。
   - 失败则返回错误，不产生 `starting`。

### Edge cases

1. 用户会话使用中 FastAPI / TermBridge backend 重启：
   - ttyd process 和 port 消失。
   - tmux host/session/window 仍存在。
   - persisted `status`、`pid`、`port` 不可信。
   - 业务状态应刷新为 `disconnected`。
   - UI 展示“重连会话”。

2. 用户会话使用中服务器或 tmux host 重启：
   - ttyd 和 tmux 资源全部消失。
   - persisted `status`、`pid`、`port`、`tmux_window_id` 均不可信。
   - 业务状态应刷新为 `stopped`。
   - UI 展示“启动会话”。

3. 持久化记录为 `stopped` 但历史 `tmux_window_id` 或 `port` 仍有值：
   - 对业务逻辑而言 stopped 会话的这些运行时字段没有意义。
   - `/session` 页不检查 stopped 会话是否真实存活。
   - 端口分配和 terminal proxy 判断不能因为 stopped 会话的历史 port 非零而认为该会话占用或可用。

4. 持久化记录为 `running` 或 `disconnected`：
   - 系统可以基于 `tmux_window_id + ttyd port` 的现有模型刷新状态。
   - live tmux window 存在且 ttyd port 可用 => `running`。
   - live tmux window 存在但 ttyd port 不可用 => `disconnected`。
   - live tmux window 不存在 => `stopped`。

5. 多个 session entry 指向同一个 `tmux_window_id`：
   - stopped 状态的 session 不依赖其历史 `tmux_window_id`。
   - running 状态的 session 在正确业务流中不应出现重复 `tmux_window_id`。
   - 如果实现中发现 running/disconnected 的重复归属，需要阻止错误继续传播或规范化为 stopped。

6. `/session` 页面初始加载：
   - 接受两阶段加载策略：先快速展示持久化/缓存会话树，再异步刷新 live 状态。
   - 前端必须避免刷新前使用陈旧 `running/url` 打开 iframe。
   - 刷新完成后更新会话状态与终端区域展示。

7. create/start/stop/delete 操作返回数据：
   - 继续沿用现有 happy path 策略：操作 API 返回对应数据，前端局部更新。
   - 不要求这些操作后统一重新拉 `/api/session-tree`。
   - 后端返回数据仍应符合该操作的同步结果，例如 create/start 成功为 `running`，stop 成功为 `stopped`，delete 成功删除业务记录。

## Acceptance criteria

1. 对外业务状态不再包含 `starting` 语义：
   - 新建/启动会话是同步操作。
   - 成功直接返回 `running`。
   - 失败直接返回错误。
   - 前端不再需要展示 `starting` 状态。

2. 业务状态判定有统一模型：
   - live tmux window 存在且 live ttyd proxy 可用 => `running`。
   - live tmux window 存在但 live ttyd proxy 不可用 => `disconnected`。
   - live tmux window 不存在 => `stopped`。

3. stopped 状态语义：
   - 表示业务会话没有可用/可恢复的 live tmux window。
   - `/session` 页不检查 stopped 会话是否真实存活。
   - stopped 会话的历史 `pid`、`port`、`url`、`tmux_window_id` 不参与 terminal proxy、UI 可用性或端口占用判断。
   - happy path 的 stop 操作应尽量写出规范 stopped 状态。

4. disconnected 状态语义：
   - 表示 live tmux window 存在但 ttyd proxy 不可用。
   - UI 展示“重连会话”。
   - 基于现有 `tmux_window_id + ttyd port` 模型判断即可，不额外要求 pid、command line、credential 或日志归属验证。

5. running 状态语义：
   - 必须有可用 ttyd proxy target。
   - 必须有 live tmux window。
   - `url` 指向可代理终端。
   - 正确业务流中 running 会话的 `tmux_window_id` 不应重复。

6. `terminal_proxy_target()` 不只相信 persisted `status`；它必须在返回 proxy target 前基于统一 refresh 结果确认 session 当前为 `running`。

7. `/api/session-tree` / `/api/sessions` 的列表加载策略支持 `/session` 首屏两阶段加载：
   - 初始返回路径满足性能要求。
   - 后续 live refresh 更新 running/disconnected/stopped。
   - 前端不能在 refresh 前使用陈旧 running/url 打开 iframe。

8. create/start/stop/delete 操作继续沿用现有局部响应更新策略，不强制重新拉 `/api/session-tree`。

9. stop/delete 操作必须实现资源清理和业务记录清理的边界：
   - stop 关闭 ttyd 和 tmux window，然后保留业务记录为 `stopped`。
   - delete 确保资源清理后删除业务记录。

10. FastAPI/backend 重启后，如果 tmux window 仍存在，会话应显示为 `disconnected` 并可重连。

11. 服务器/tmux host 重启后，如果 tmux window 不存在，会话应显示为 `stopped` 并可启动。

12. 端口分配不能因为 stopped 会话保留历史 `port` 而跳过可用端口；端口是否清零不是验收要求。

13. 增加后端测试覆盖状态推导、去除 starting 语义、FastAPI 重启、服务器重启、stop/delete 语义、stopped 历史运行时字段不参与判断。

14. 增加或更新前端测试/类型检查，覆盖 `/session` 两阶段加载和 create/start/stop/delete 后局部响应更新策略。

15. 验证时需要覆盖性能相关风险：不能引入明显的 per-session 串行 tmux 探测导致 `/session` 初始加载退化。

## Decisions

1. 业务 session 是 TermBridge 持久化的 session entry；tmux window 和 ttyd process/port 是运行时资源。
2. 持久化 `status`、`pid`、`port`、`url`、`tmux_window_id` 只能作为缓存或定位线索，不是最终真相。
3. `starting` 语义取消；新建/启动会话同步完成，成功即 `running`，失败即错误。
4. `disconnected` 的业务含义是 ttyd proxy 不可用但底层 tmux window 仍存在，可执行“重连会话”。
5. `stopped` 的业务含义是没有可用/可恢复的 live tmux window；用户可执行“启动会话”。
6. stopped 会话的历史 `tmux_window_id`、`pid`、`port` 不再作为业务判断依据；端口是否清零不作为要求。
7. live ttyd proxy 归属沿用当前 `tmux_window_id + ttyd port` 模型，不额外要求 command line / credential / 日志验证。
8. running 状态的会话在正确业务流中不应重复 `tmux_window_id`；stopped 状态会话不依赖历史 `tmux_window_id`。
9. `/session` 首屏接受两阶段加载。
10. create/start/stop/delete 后前端继续沿用现有局部响应更新策略，不强制重新拉 `/api/session-tree`。
11. delete 是业务记录删除操作；资源关闭语义应由 stop/ensure-stopped 完成。
12. 本任务使用 strict / 严格模式，需要进入 Spec 阶段后再确定具体实现方案。

## Open questions

暂无。

## Risks

1. 状态判定如果每个 session 单独调用 tmux，会破坏 `/session` 页性能，需要批量列出 live tmux windows 和端口/process 状态。
2. 两阶段加载如果前端保护不足，可能在 refresh 前使用陈旧 running/url 打开 iframe。
3. 取消 `starting` 语义需要检查后端 enum、前端类型、i18n、测试和 UI 分支，避免残留不可达状态。
4. stopped 会话历史 port 不清零时，端口分配必须显式跳过 stopped 会话，否则会继续造成端口占用误判。
5. 当前已有历史状态文件可能包含非法组合，刷新和 UI 展示必须兼容。

## User review notes

- 用户已明确要求按严格模式开始新任务。
- 用户要求同时检查 `/session` 页面的性能策略：初始加载会话列表，以及 create/start/stop/delete 操作返回数据对状态一致性的影响，都需要纳入本任务。
- 用户明确要求消除 `starting` 语义：新建会话是同步的，不需要 starting。
- 用户确认 port 在 stopped / disconnected 下是否清零不影响业务；端口分配跳过 stopped 会话即可。
- 用户确认 live ttyd proxy 归属沿用当前 `tmux_window_id + ttyd port` 判断，足够使用。
- 用户确认 stopped 状态不依赖历史 `tmux_window_id`；running 状态的 `tmux_window_id` 正常不应重复。
- 用户确认 `/session` 首屏接受两阶段加载。
- 用户确认 create/start/stop/delete 后前端状态策略继续沿用现有局部响应更新实现，不需要重新拉 `/api/session-tree`。
