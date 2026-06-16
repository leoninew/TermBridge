# 会话局部状态更新与重连状态修复需求

Review status: Accepted

## Background

当前重连已存在 tmux window 和 ttyd 进程时，`POST /api/sessions/{session_id}/start` 可以返回 `running`，但随后前端刷新 `GET /api/session-tree` 时，后端可能基于进程适配器内存状态把同一会话刷新为 `disconnected`，导致 UI 仍显示 disconnected。

典型问题会话：`sess_e7e61833f23248cabe7fc0b35a159f33`。

上一个实现已让启动、停止、重连动作改用对应 POST 响应做局部更新。为了继续提高完成度，新建会话和删除会话也需要具备不依赖 `GET /api/session-tree` 完整刷新的能力。若现有接口响应数据不足，可以调整创建或删除接口的响应结构。

## Goal

1. 启动或重连单个会话后，前端应直接使用 `POST /api/sessions/{session_id}/start` 返回的被操作会话更新 UI，不应为了该动作再依赖一次完整的 `GET /api/session-tree` 刷新。
2. 停止单个会话后，前端应直接使用 `POST /api/sessions/{session_id}/stop` 返回的被操作会话更新 UI，不应为了该动作再依赖一次完整的 `GET /api/session-tree` 刷新。
3. 新建会话成功后，前端应直接使用创建接口响应把新 session 插入 `sessions` 与 `sessionTree` 中对应 workspace，不应为了新建动作再依赖一次完整的 `GET /api/session-tree` 刷新。
4. 删除单个会话成功后，前端应直接使用删除接口响应或本地上下文从 `sessions` 与 `sessionTree` 移除对应 session，并更新 workspace 状态；不应为了删除单个会话动作再依赖一次完整的 `GET /api/session-tree` 刷新。
5. `sessions.json` 仅作为会话列表和持久化元数据，不作为真实运行状态的缓存来源。
6. 会话真实状态应通过实际运行环境检查得到，例如 ttyd 端口/进程可达性、tmux window 是否存在等，而不是依赖 `self._processes` 这类单个后端对象实例中的内存缓存。
7. 重连已存在 tmux window 且 ttyd 实际可用的会话时，UI 应显示可连接状态，并保留可访问的 terminal URL。

## Non-goal

1. 不改变会话、工作区、快捷方式的数据模型语义，除非为真实状态检查或局部更新必须补充响应字段。
2. 不把 `sessions.json` 变成运行状态缓存或进程注册表。
3. 不引入依赖某一次 FastAPI 请求生命周期的状态判断。
4. 不要求本次重构整个 session-tree 加载和排序机制。
5. 不要求删除工作区、close-all、排序等会改变更大树结构的动作全部改为局部更新；这些动作可以继续完整刷新，除非实现中低成本顺带支持。

## User scenarios

1. 用户点击 disconnected 会话的“重连”。后端启动 ttyd 并返回该会话为 `running`，前端立即打开 terminal，不再因为随后刷新整棵树而回退到 disconnected。
2. 后端服务中的 `ProcessAdapter` 实例变化、请求结束或服务重启后，只要 ttyd/tmux 真实存在，状态检查仍能判断会话可用。
3. 如果 ttyd 不可达但 tmux window 还在，会话可以显示为 disconnected，提示用户可再次重连。
4. 如果 tmux window 不存在，会话应显示为 stopped，并清理不可用的运行态字段。
5. 用户在已有 workspace 下新建会话。前端把创建接口返回的 session 插入现有 workspace，并打开 terminal，不再完整刷新 session tree。
6. 用户删除单个会话。前端从当前列表和树中移除该 session，关闭对应 terminal tab，并在必要时切换 active terminal，不再完整刷新 session tree。
7. 如果新建会话落在当前树中尚未存在的 workspace 或 environment 下，前端应能基于接口返回数据创建必要的父节点，或后端返回足够的局部树片段用于插入。

## Acceptance

1. `POST /api/sessions/{session_id}/start` 成功后，前端不再立即调用 `GET /api/session-tree` 作为启动/重连动作的必要步骤；而是用 start 返回的 session 更新 `sessions`、`sessionTree` 中对应节点，并打开该 session。
2. `POST /api/sessions/{session_id}/stop` 成功后，前端同样使用 stop 返回的 session 更新 `sessions`、`sessionTree` 中对应节点，不为停止动作重新拉取完整 session-tree。
3. 新建会话成功后，前端不再立即调用 `GET /api/session-tree` 作为创建动作的必要步骤；而是使用 create 响应更新 `sessions`、`sessionTree` 和打开的 terminal。
4. 删除单个会话成功后，前端不再立即调用 `GET /api/session-tree` 作为删除动作的必要步骤；而是移除对应 session、关闭对应 terminal tab，并更新 active terminal 与 workspace 聚合状态。
5. 如 create/delete 当前响应不足以完成局部更新，可以修改后端响应：例如 create 返回完整 `SessionResponse` 加必要 workspace/environment 上下文，delete 返回被删除 session 的 id 与删除后的 workspace/environment 局部状态，或返回可直接替换的局部 workspace/tree fragment。
6. 后端刷新单个会话或 session-tree 时，不以 `self._processes` 是否包含 pid 作为唯一运行判断。
7. `sessions.json` 中的 `status` 不再被视为真实运行状态权威来源；接口返回前应执行实际检查并返回检查后的状态。
8. 覆盖回归测试：模拟“已有会话记录 + 新的服务/进程适配器实例 + 实际 ttyd/tmux 可用”时，接口应返回 running，而不是 disconnected。
9. 覆盖前端行为：启动、重连、新建、删除单个会话成功后不要求全量刷新 session-tree，且对应会话状态、URL、terminal tab 和 workspace 状态被正确更新。
10. 对不可用场景仍正确降级：ttyd 不可达但 tmux 存在为 disconnected；tmux 不存在为 stopped。

## Open questions

1. 前端局部更新 session-tree 时，是否需要保留当前工作区排序、tab 顺序和展开状态不变。
2. 新建会话如果会创建当前树中不存在的 environment/workspace，优先由后端返回完整局部父节点，还是前端基于已有类型字段自行构造父节点。
3. 删除 workspace 中最后一个 session 后，是否应保留空 workspace 节点，还是从当前树中移除该 workspace。当前倾向：与完整 session-tree 返回行为保持一致。

## Decisions

1. 用户明确要求：启动重连不需要再刷 `GET /api/session-tree`。
2. 用户明确要求：真实状态靠实际检查，不靠 `sessions.json` 或 `self._processes` 缓存。
3. 本变更按轻量模式 / light 推进，先记录需求，经接受后再进入实现。
4. ttyd 实际可用性基于端口检查；tmux window 实际可用性基于 tmux window 检查。
5. `src/termbridge/process.py` 中此前未经确认的修改已由用户自行撤销，后续实现不改该文件。
6. 用户新增要求：新建会话和删除单个会话也要达到不调用 `GET /api/session-tree` 完整刷新的能力。
7. 用户允许为达成局部更新修改接口响应数据。

## Risk

1. 真实状态检查若只检查端口，可能误判端口被其他进程占用为会话可用；实现阶段需要约束检查目标。
2. 前端跳过全量刷新后，如果后端 start/create/delete 同时改变了 workspace 级状态，需要确保局部更新也同步 workspace status。
3. 新建会话涉及 environment/workspace 父节点插入；如果前后端对 workspace 排序、environment 命名或空节点处理理解不一致，局部更新可能和完整 session-tree 结果产生偏差。
4. 删除 workspace 最后一个 session 时，需要和现有完整树行为对齐，避免留下不应展示的空 workspace 或误删仍应存在的 workspace 节点。
5. 当前工作区已有未提交修改时，实施需要避免混入无关变更。
