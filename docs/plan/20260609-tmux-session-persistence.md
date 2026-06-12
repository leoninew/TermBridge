# Cygwin tmux 会话持久化实施计划

Review status: Accepted

当前：严格模式 / strict，计划 / Plan

## Requirement / Spec basis

- Requirement: `docs/requirement/20260609-tmux-session-persistence.md`，已接受。
- Spec: `docs/spec/20260609-tmux-session-persistence.md`，已接受。

目标是在 Cygwin 终端上提供可选 tmux persistence，让浏览器刷新后重新 attach 到同一个 tmux session，并在终端配置中检测和展示 tmux 可用性。

## Current partial state

当前代码已存在一部分探索性实现和测试：

- `src/cc_ttyd/models.py` 已增加 `session_persistence` 字段。
- `src/cc_ttyd/services.py` 已支持 Cygwin tmux command wrapping 的基础路径。
- `tests/test_terminal_service.py` 已有 tmux wrapping 单元测试。

实施阶段需要在此基础上补齐检测、删除清理、API、前端入口和完整测试；如发现探索性实现与本 plan 冲突，以本 plan 为准修正。

## Implementation steps

### 1. fastapi models

文件：`src/cc_ttyd/models.py`

- 确认并保留：
  - `TerminalDefinition.session_persistence: Literal["none", "tmux"] = "none"`
  - `CreateTerminalRequest.session_persistence`
  - `UpdateTerminalRequest.session_persistence`
- 扩展 `SessionRecord`：
  - `session_persistence: Literal["none", "tmux"] = "none"`
  - `tmux_bash_path: str | None = None`
- 新增 tmux 检测响应模型：
  - `TmuxAvailabilityResponse`
    - `available: bool`
    - `path: str | None = None`
    - `version: str | None = None`
    - `reason: str | None = None`

### 2. fastapi terminal service

文件：`src/cc_ttyd/services.py`

- 在 `TerminalService` 中新增：
  - `check_tmux(cygwin_bash_path: str) -> TmuxAvailabilityResponse`
- 检测命令：
  - `[cygwin_bash_path, "-lc", "command -v tmux && tmux -V"]`
  - `timeout=5`
  - 成功时解析第一行为 path，第二行为 version。
  - 失败、超时、OSError 返回 `available=False` 和原因。
- 在 `_validate_terminal()` 或保存路径中增加校验：
  - 只有 `launch_type="cygwin"` 可启用 `tmux`。
  - 启用 `tmux` 时必须有 `cygwin_bash_path`。
  - 启用 `tmux` 时检测必须 available，否则抛 `InvalidTerminalConfigError`。
- `resolve_terminal_command()`：
  - 保持 `session_name` 参数。
  - Cygwin + tmux 时包装：`tmux new-session -A -s <session_name> <quoted terminal.command>`。
  - 非 tmux 路径保持原行为。

### 3. fastapi session lifecycle

文件：`src/cc_ttyd/services.py`

- `SessionService.create()`：
  - 先生成 `session_id`，再 resolve terminal command。
  - 若所选 terminal 启用 tmux，写入 `SessionRecord.session_persistence="tmux"` 和 `tmux_bash_path`。
- `SessionService.delete()`：
  - 先 terminate ttyd process。
  - 如果 `session.session_persistence == "tmux"` 且 `tmux_bash_path` 存在，则执行：
    - `[tmux_bash_path, "-lc", f"tmux kill-session -t {shlex.quote(session.id)}"]`
  - kill 失败仅 `logger.warning`，继续删除 session record。

### 4. fastapi API

文件：`src/cc_ttyd/api.py`

- 新增检测 API：
  - `POST /api/terminals/tmux/check`
- Request 可复用轻量模型或新增：
  - `cygwin_bash_path: str`
- Response：`TmuxAvailabilityResponse`
- API 失败语义：检测失败返回 200 + `available=false`，只有请求格式错误才返回 422。

### 5. web types and API

文件：

- `web/src/types/sessions.ts`
- `web/src/api/sessions.ts`

改动：

- 类型增加 `session_persistence: 'none' | 'tmux'`。
- payload 增加该字段。
- 新增：`checkTmux(cygwin_bash_path: string)`。

### 6. web terminal management UI

文件：`web/src/components/TerminalManagement.vue`

- form 增加：`session_persistence: 'none' | 'tmux'`。
- `resetForm()` 默认 `none`。
- `edit()` 读取 terminal 的 persistence。
- `normalizePayload()`：
  - direct 模式强制 `session_persistence: 'none'`。
  - cygwin 模式使用表单值。
- Cygwin 设置区域增加：
  - `检测 tmux`按钮，调用 `checkTmux()`。
  - 检测结果：available/path/version 或 unavailable reason。
  - `启用 tmux 持久会话`选项。
  - tmux 不可用时禁用或阻止保存 tmux persistence。
- 所有新增文案使用 i18n。

### 7. i18n

先定位当前 locale 文件，再添加：

- tmux label/help/detect/status/version/unavailable/save error 文案。

### 8. Tests

fastapi:

- `tests/test_terminal_service.py`
  - tmux 检测成功。
  - tmux 未安装 / command failure。
  - bash 不存在 / OSError。
  - timeout。
  - tmux 不可用时拒绝保存启用 persistence 的 Cygwin 终端。
  - direct terminal 启用 tmux 被拒绝。
  - Cygwin tmux command wrapping。
- `tests/test_services.py`
  - create 写入 tmux metadata。
  - delete 尝试 kill tmux session。
  - kill 失败仍删除 session。
- API tests：
  - tmux check API returns available false/true via fake service override。

web:

- 至少运行：
  - `yarn lint`
  - `yarn format:check`
  - `yarn typecheck`

### 9. Manual verification

1. 确认 Cygwin tmux：
   - `D:/ProgramFiles/Cygwin64/bin/bash.exe -lc 'command -v tmux && tmux -V'`
2. 在终端管理中新建 Cygwin 终端。
3. 输入 Cygwin bash path 后检测 tmux，应显示版本。
4. 启用 tmux persistence 并保存。
5. 使用该终端创建 session。
6. 输入命令，刷新页面。
7. 验证回到同一个 tmux session，终端状态保留。
8. 删除 session 后，验证 tmux session 被清理。

## Rollback

- 如果 tmux integration 出现问题，保留模型字段但前端隐藏 tmux persistence 入口，并让所有保存 payload 使用 `none`。
- 后端 `none` 路径保持现有行为，不影响原 terminal/session 使用。

## Risks

- tmux command quoting 对复杂 shell 命令仍可能有边界，先限制在 Cygwin 单字符串 command。
- tmux 检测依赖用户配置的 bash path。
- 后端重启后的 session/process 恢复不在本任务范围内。
