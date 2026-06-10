# Cygwin tmux 会话持久化规格

Review status: Accepted

当前：严格模式 / strict，规格 / Spec

## Requirement basis

基于 `docs/requirement/20260609-tmux-session-persistence.md`，需求已接受。核心目标是在 Cygwin 终端上提供可选 tmux persistence，让浏览器刷新后重新连接同一个前端 session 时 attach 到同一个 tmux session，从而保留终端状态。

## Overview

当前 session 生命周期是：

```text
frontend session -> backend SessionRecord -> ttyd process -> child terminal process
```

问题在于 ttyd 1.7.7 不提供 reconnect/resume 参数，刷新 iframe 后 child terminal 会重建。

新方案将启用 persistence 的 Cygwin 终端改为：

```text
frontend session -> backend SessionRecord -> ttyd process -> cygwin bash -lc -> tmux new-session -A -s <session_id> <terminal command>
```

这样刷新后 ttyd 即使重新启动 child command，也只是重新 attach 到同一个 tmux session。

## Design decisions

### 1. tmux availability detection

Cygwin 环境中不保证安装 `tmux`，因此后端必须提供检测能力，前端配置也必须体现该状态。

检测方式：

```bash
<cygwin_bash_path> -lc "command -v tmux && tmux -V"
```

语义：

- 检测成功：返回 `available=true`、`path`、`version`。
- 检测失败：返回 `available=false` 和用户可读原因。
- 检测超时或 bash 不可执行：按 unavailable 处理，不抛出 500。
- 保存启用 tmux persistence 的 Cygwin 终端时，后端应校验 tmux 可用；不可用则拒绝保存并返回明确错误。

### 2. Persistence 配置粒度

配置放在 `TerminalDefinition` 上，而不是全局设置或单个 session 表单上。

理由：

- Cygwin 终端适合 tmux，Windows direct 终端不适合。
- 用户可以创建多个 Cygwin 终端：有的启用 tmux，有的不启用。
- session 创建时只需继承所选 terminal 的行为。

字段：

```py
session_persistence: Literal["none", "tmux"] = "none"
```

适用模型：

- `TerminalDefinition`
- `CreateTerminalRequest`
- `UpdateTerminalRequest`

### 3. 支持范围

仅当满足以下条件时启用 tmux 包装：

- `terminal.launch_type == "cygwin"`
- `terminal.session_persistence == "tmux"`
- `SessionService.create()` 提供稳定 `session_name`

其他情况保持现有命令不变。

### 4. tmux session name

直接使用后端 `session_id`，例如：

```text
sess_abcdef123
```

该值由后端生成，字符安全、稳定、唯一。

### 5. 命令包装

原 Cygwin command：

```bash
cd '<workspace>' && exec <terminal.command>
```

启用 tmux 后：

```bash
cd '<workspace>' && exec tmux new-session -A -s <session_id> '<terminal.command>'
```

实现注意：

- workspace 使用现有 `_to_forward_slash()`。
- workspace、session name、terminal command 使用 `shlex.quote()`。
- 当前只包装 Cygwin 自定义终端的单字符串 `terminal.command`。

### 6. 删除清理

删除启用 tmux persistence 的 session 时，后端应尝试清理 tmux session：

```bash
<cygwin_bash_path> -lc "tmux kill-session -t <session_id>"
```

语义：

- kill 失败只记录 warning，不阻止删除后端 session record。
- 清理在 terminate ttyd process 后执行，或在删除 record 前执行均可；建议顺序：先 terminate ttyd，再 kill tmux，再 delete record。

为了执行清理，`SessionRecord` 需要记录足够信息：

- `session_persistence`
- `terminal_launch_type` 或更窄地记录 `tmux_bash_path`

推荐最小字段：

```py
session_persistence: Literal["none", "tmux"] = "none"
tmux_bash_path: str | None = None
```

只有 Cygwin tmux session 写入 `tmux_bash_path`。

### 7. 前端配置

`TerminalManagement.vue` 的新建/编辑自定义终端弹窗中：

- 当 `launch_type === "cygwin"` 时显示 tmux persistence 选项。
- Cygwin bash path 填写后，应提供 tmux 检测入口或自动检测状态。
- tmux 可用时，显示检测到的版本，例如 `tmux 3.2`。
- tmux 不可用时，禁用/阻止启用 persistence，并显示原因，例如未安装 tmux、bash 路径不可用、检测超时。
- 可用文案：
  - Label：`启用 tmux 持久会话`
  - Help：`刷新页面后尝试恢复同一个 tmux 会话，仅适用于 Cygwin 且需安装 tmux。`
  - Detect：`检测 tmux`
- direct 模式隐藏该选项，并提交为 `none`。

需要同步类型：

- `frontend/src/types/sessions.ts`
- `frontend/src/api/sessions.ts` 只要复用 payload 类型，无需新增 API。

### 8. i18n

当前前端已开始使用 `vue-i18n`。新增文案应写入现有 locale 文件，而不是硬编码中文。需要先定位 locale 文件结构后再实施。

## Affected components

### Backend

- `src/cc_ttyd/models.py`
  - 增加 persistence 字段。
  - 增加 tmux availability 检测响应模型。
  - `SessionRecord` 增加 tmux 清理所需字段。
- `src/cc_ttyd/services.py`
  - `TerminalService` 增加 Cygwin tmux 检测方法。
  - 创建/更新启用 tmux persistence 的 Cygwin 终端时校验 tmux 可用。
  - `TerminalService.resolve_terminal_command()` 接收 `session_name`。
  - Cygwin + tmux 时包装 command。
  - `SessionService.create()` 先生成 `session_id`，再 resolve command。
  - `SessionService.delete()` 增加 tmux cleanup。
- `src/cc_ttyd/api.py`
  - 增加 Cygwin tmux 检测 API，供终端管理 UI 使用。
- `tests/test_terminal_service.py`
  - 覆盖 Cygwin tmux command wrapping。
  - 覆盖 tmux availability 检测成功、未安装、bash 不可用/超时。
  - 覆盖 tmux 不可用时拒绝保存启用 persistence 的终端。
- `tests/test_services.py`
  - 覆盖 session_id 传递和删除清理。

### Frontend

- `frontend/src/types/sessions.ts`
  - 增加 `session_persistence` 字段。
- `frontend/src/components/TerminalManagement.vue`
  - form 增加字段。
  - 新建/编辑时读写字段。
  - Cygwin 模式显示配置项。
  - Cygwin 设置区域显示 tmux 检测入口、检测结果和不可用原因。
  - tmux 不可用时禁止保存 `session_persistence="tmux"`。
- locale files
  - 新增 tmux persistence 文案。

## Risks

- tmux session 里运行的 command quoting 需要保持简单清晰；复杂 shell 命令本身仍由用户负责。
- Cygwin 不一定安装 tmux；必须在保存配置前检测并在 UI 中明确提示。
- tmux 检测依赖用户填写的 Cygwin bash path；bash path 错误时需要给出可理解反馈。
- kill tmux session 失败不能影响删除 session，否则可能导致 UI 上无法删除记录。
- 后端重启后 `_processes` 丢失仍会使 session status 变为 stopped；本任务不解决跨后端重启恢复。
- 如果同一个 tmux session 被多个浏览器窗口 attach，会共享画面和输入，这是 tmux 的预期行为。

## Alternatives considered

- ttyd reconnect 参数：当前 ttyd 1.7.7 无该参数，不可用。
- screen：可行但暂不做，减少分支和验证成本。
- 全局强制 tmux：不适合 Windows direct terminal，也会改变默认行为。

## User review notes

- 用户要求 Open questions 采用建议方式并进入 Spec。
