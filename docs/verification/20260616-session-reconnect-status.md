# 会话重连状态修复验证

Review status: Draft

## What changed

- 后端会话刷新不再依赖 `ProcessAdapter.is_running()` / `self._processes` 判断真实状态。
- 后端基于 ttyd 端口可连接性判断 ttyd 会话是否可用，基于 tmux window 检查判断终端窗口是否存在。
- 后端状态降级规则：ttyd 端口可用且 tmux window 存在为 `running`；ttyd 不可用但 tmux window 存在为 `disconnected`；tmux window 不存在为 `stopped`。
- `terminal_proxy_target` 不再要求记录中存在 pid；只要刷新后的状态为 `running` 且端口有效即可代理。
- 前端启动、停止、重连会话后，使用对应 POST 响应中的 session 局部更新 `sessions` 和 `sessionTree`，不再为这些动作重新请求 `GET /api/session-tree`。
- 增加回归测试覆盖新服务实例 / 无进程缓存但 ttyd 端口可用时仍返回 `running`。

## Acceptance

- [x] 启动 / 重连后前端不再立即调用 `GET /api/session-tree`，而是用 start 响应更新会话列表状态。
- [x] 停止后前端不再立即调用 `GET /api/session-tree`，而是用 stop 响应更新会话列表状态。
- [x] 后端真实状态检查不依赖 `self._processes` 作为 running 判定依据。
- [x] `sessions.json` 中的记录不作为真实运行状态权威来源；接口返回前通过 ttyd 端口和 tmux window 重新判断。
- [x] ttyd 不可用但 tmux window 存在时返回 `disconnected`。
- [x] tmux window 不存在时返回 `stopped`。
- [x] 新服务实例 / 无进程缓存但 ttyd 端口可用时返回 `running`。

## Commands

- `pytest tests/test_services.py`
  - 结果：40 passed
- `npm --prefix web run typecheck`
  - 结果：通过
- `ruff check src/termbridge/services.py tests/test_services.py`
  - 结果：All checks passed

## Remaining risk

- 端口检查只能确认目标端口可连接，不能单独证明该端口一定属于本会话的 ttyd；当前方案按用户要求以 ttyd 端口可用性作为 ttyd 会话可用判断。
- 删除会话、删除工作区、close-all、排序等会改变树结构的动作仍保留完整 session-tree 刷新或接口返回整棵树，不属于本次“启动、停止、重连”的局部更新范围。
