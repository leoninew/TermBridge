# 会话重连状态修复需求

Review status: Accepted

## Background

当前重连已存在 tmux window 和 ttyd 进程时，`POST /api/sessions/{session_id}/start` 可以返回 `running`，但随后前端刷新 `GET /api/session-tree` 时，后端可能基于进程适配器内存状态把同一会话刷新为 `disconnected`，导致 UI 仍显示 disconnected。

典型问题会话：`sess_e7e61833f23248cabe7fc0b35a159f33`。

## Goal

1. 启动或重连单个会话后，前端应直接使用 `POST /api/sessions/{session_id}/start` 返回的被操作会话更新 UI，不应为了该动作再依赖一次完整的 `GET /api/session-tree` 刷新。
2. `sessions.json` 仅作为会话列表和持久化元数据，不作为真实运行状态的缓存来源。
3. 会话真实状态应通过实际运行环境检查得到，例如 ttyd 端口/进程可达性、tmux window 是否存在等，而不是依赖 `self._processes` 这类单个后端对象实例中的内存缓存。
4. 重连已存在 tmux window 且 ttyd 实际可用的会话时，UI 应显示可连接状态，并保留可访问的 terminal URL。

## Non-goal

1. 不改变会话、工作区、快捷方式的数据模型语义，除非为真实状态检查必须补充字段。
2. 不把 `sessions.json` 变成运行状态缓存或进程注册表。
3. 不引入依赖某一次 FastAPI 请求生命周期的状态判断。
4. 不要求本次重构整个 session-tree 加载和排序机制。

## User scenarios

1. 用户点击 disconnected 会话的“重连”。后端启动 ttyd 并返回该会话为 `running`，前端立即打开 terminal，不再因为随后刷新整棵树而回退到 disconnected。
2. 后端服务中的 `ProcessAdapter` 实例变化、请求结束或服务重启后，只要 ttyd/tmux 真实存在，状态检查仍能判断会话可用。
3. 如果 ttyd 不可达但 tmux window 还在，会话可以显示为 disconnected，提示用户可再次重连。
4. 如果 tmux window 不存在，会话应显示为 stopped，并清理不可用的运行态字段。

## Acceptance

1. `POST /api/sessions/{session_id}/start` 成功后，前端不再立即调用 `GET /api/session-tree` 作为启动/重连动作的必要步骤；而是用 start 返回的 session 更新 `sessions`、`sessionTree` 中对应节点，并打开该 session。
2. `POST /api/sessions/{session_id}/stop` 成功后，前端同样使用 stop 返回的 session 更新 `sessions`、`sessionTree` 中对应节点，不为停止动作重新拉取完整 session-tree。
2. 后端刷新单个会话或 session-tree 时，不以 `self._processes` 是否包含 pid 作为唯一运行判断。
3. `sessions.json` 中的 `status` 不再被视为真实运行状态权威来源；接口返回前应执行实际检查并返回检查后的状态。
4. 覆盖回归测试：模拟“已有会话记录 + 新的服务/进程适配器实例 + 实际 ttyd/tmux 可用”时，接口应返回 running，而不是 disconnected。
5. 覆盖前端行为：启动/重连成功后不要求全量刷新 session-tree，且对应会话状态和 URL 被更新。
6. 对不可用场景仍正确降级：ttyd 不可达但 tmux 存在为 disconnected；tmux 不存在为 stopped。

## Open questions

1. 前端局部更新 session-tree 时，是否需要保留当前工作区排序、tab 顺序和展开状态不变。

## Decisions

1. 用户明确要求：启动重连不需要再刷 `GET /api/session-tree`。
2. 用户明确要求：真实状态靠实际检查，不靠 `sessions.json` 或 `self._processes` 缓存。
3. 本变更按轻量模式 / light 推进，先记录需求，经接受后再进入实现。
4. ttyd 实际可用性基于端口检查；tmux window 实际可用性基于 tmux window 检查。
5. `src/termbridge/process.py` 中此前未经确认的修改已由用户自行撤销，后续实现不改该文件。

## Risk

1. 真实状态检查若只检查端口，可能误判端口被其他进程占用为会话可用；实现阶段需要约束检查目标。
2. 前端跳过全量刷新后，如果后端 start 同时改变了 workspace 级状态，需要确保局部更新也同步 workspace status。
3. 当前工作区已有未提交修改，实施时需要避免混入无关变更，并明确处理此前对 `src/termbridge/process.py` 的未确认改动。
