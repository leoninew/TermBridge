# 快捷方式 Cygwin tmux 托管规格

Review status: Accepted

当前：严格模式 / strict，计划 / Plan

## Requirement basis

- Requirement: `docs/requirement/20260609-shortcut-cygwin-tmux-hosting.md`
- Requirement status: Accepted

本规格基于已接受需求：将“终端定义 / terminal definition”一次性迁移为“快捷方式 / shortcut”，第一阶段聚焦 `cygwin_tmux` host，通过 Cygwin bash + tmux + ttyd 托管 Claude Code、Codex 等入口命令。

## Overview

Shortcut 是“如何启动”的配置。它不代表 runtime host，也不持有 ttyd path、Cygwin bash path 或固定 workspace。

新建会话时，用户选择：

1. shortcut：决定执行什么命令。
2. workspace：决定在哪个工作目录启动。

后端根据 shortcut 的 host type 执行 host-specific 启动逻辑。第一阶段只实现 `cygwin_tmux`：

1. 读取环境中的 Cygwin bash 配置。
2. 检查绑定 host 配置是否就绪。
3. 用规范化应用会话名作为 tmux session name。
4. 在 tmux session 中启动 shortcut command，并进入用户选择的 workspace。
5. 用 ttyd attach 到该 tmux session。

## Design decisions

### 1. 命名一次性迁移

- 后端模型、API、前端主要类型和 UI 文案迁移为 shortcut 语义。
- 旧 `TerminalDefinition`、`terminal_id`、`/api/terminals` 作为入口配置命名不再作为主路径保留。
- 旧 terminal definitions 数据不迁移，直接删除或在新状态结构中不读取。

### 2. Shortcut 数据模型

建议模型：

```python
ShortcutHost = Literal["windows", "cygwin", "wsl", "cygwin_tmux"]

class Shortcut(BaseModel):
    id: str
    name: str
    command: str
    host: ShortcutHost
    description: str | None = None
    icon: str | None = None
```

第一阶段 UI 只允许创建或启动 `cygwin_tmux` host；模型保留 Windows/Cygwin/WSL host 语义是为了表达“快捷方式必须绑定 host 环境”的产品规则，但未实现的 host 不能启动。

### 3. Shortcut validation

- `name` 必须非空白。
- `command` 必须非空白。
- `host` 必须是允许值。
- 第一阶段创建/更新时如只开放 `cygwin_tmux`，则 API 可以拒绝其他 host，或前端不暴露其他 host；具体取舍留给 Plan。
- 不校验 command 内容，不解析命令安全性，不限制参数。

### 4. 默认 shortcuts

首次初始化 shortcut state 时默认提供：

- Claude Code
  - command: `claude`
  - host: `cygwin_tmux`
- Codex
  - command: `codex`
  - host: `cygwin_tmux`

本阶段不区分 system/user 类别；默认 shortcuts 与用户创建的 shortcuts 一样可以修改或删除。

### 5. Workspace 由 session 创建选择

Shortcut 不保存 working directory。创建 session request 需要包含：

- `shortcut_id`
- `workspace_path`
- 可选 `session_name`

Workspace path 属于会话启动上下文，不属于 shortcut 定义。

### 6. Host 配置就绪检查

启动前只检查绑定 host 环境配置是否就绪，不额外检查进程和版本。

对 `cygwin_tmux`：

- 需要 Cygwin bash path 可从环境设置解析得到。
- 需要 ttyd executable 可从全局 ttyd settings 解析得到。
- tmux 不做额外版本检查；实际启动失败时返回启动错误。

环境管理页仍负责详细检测 Cygwin/tmux/ttyd 的可用性、路径和版本。

### 7. tmux session 命名与存储

应用会话名需要符合 tmux session name 可用规则，并且稳定存储在 session record 中。

建议规则：

- 用户可输入 display name。
- 后端生成 `tmux_session_name`，基于应用 session id 或规范化 session name。
- `tmux_session_name` 只允许安全字符，例如 `[A-Za-z0-9_.-]`。
- 如果用户输入名称包含其他字符，后端做规范化或使用 session id 作为 fallback。

Session record 应保存：

- `shortcut_id`
- `shortcut_name` 或启动时快照信息
- `workspace_path`
- `host`
- `tmux_session_name`
- `ttyd_port`
- `ttyd_pid`

切换应用 session 时，前端使用 session record 对应 URL；后端 restart/restore 时使用 `tmux_session_name` attach 到正确 tmux session。

### 8. Cygwin tmux 启动命令

后端使用 Cygwin bash 执行固定结构命令：

1. 进入 workspace。
2. 如果 tmux session 不存在，则创建 tmux session 并启动 shortcut command。
3. ttyd 执行 attach 命令连接 tmux session。

设计上避免把用户输入直接拼进外层 Windows shell；用户 command 是进入 Cygwin bash/tmux 的入口命令，本阶段只要求非空白。

### 9. API 设计

建议新增或替换为 shortcut API：

- `GET /api/shortcuts`
- `POST /api/shortcuts`
- `PUT /api/shortcuts/{shortcut_id}`
- `DELETE /api/shortcuts/{shortcut_id}`

Session 创建接口从 terminal 语义迁移到 shortcut 语义：

- `POST /api/sessions`
  - `shortcut_id`
  - `workspace_path`
  - 可选 `session_name`

保留旧 session 生命周期 API：

- list sessions
- delete session
- restart session

旧 `/api/terminals` API 在本需求中不作为主路径保留；是否直接删除 endpoint 或临时保留兼容响应由 Plan 按影响面决定，但 UI 和主要类型必须迁移为 shortcut。

### 10. Frontend structure

前端主要入口从 terminal management 改为 shortcut management：

- 列表展示快捷方式：名称、命令、host、说明、操作。
- 创建/编辑表单：名称、命令、host、说明、图标。
- 默认快捷方式和用户新增快捷方式同等展示，不显示 system/user 类别。
- 新建 session 流程要求选择 shortcut + workspace。
- UI 文案统一使用“快捷方式”，不再用“终端定义”描述入口配置。

环境管理页保持现有职责：展示和配置 ttyd、Cygwin、tmux、Windows、WSL 能力。

## Affected components

### Backend

- `src/cc_ttyd/models.py`
  - 将 terminal definition 相关模型迁移为 shortcut 模型。
  - 调整 create session request/response 中的 shortcut 字段。
  - 扩展 session record 保存 shortcut/workspace/tmux 信息。
- `src/cc_ttyd/services.py`
  - 将 terminal definition 管理逻辑迁移为 shortcut 管理逻辑。
  - 实现 `cygwin_tmux` shortcut session 启动。
  - 调整 restart/delete 使用 `tmux_session_name`。
- `src/cc_ttyd/api.py`
  - 新增或替换 shortcut API。
  - 调整 session creation request。
- tests
  - 更新 terminal definition tests 为 shortcut tests。

### Frontend

- `frontend/src/types/sessions.ts`
  - 迁移 terminal definition 类型到 shortcut 类型。
- `frontend/src/api/sessions.ts`
  - 迁移 API client 到 shortcut endpoints。
- shortcut management component
  - 将终端管理 UI 替换为快捷方式管理 UI。
- session creation UI
  - 改为选择 shortcut + workspace。
- i18n
  - 替换“终端定义”相关文案为“快捷方式”。

### Data/state

- 删除旧 terminal definitions 数据，不做迁移。
- 新状态中保存 shortcuts，初始化时写入 Claude Code 和 Codex 默认 shortcut。
- Session records 保存 shortcut 和 tmux session 相关信息。

## Interfaces

### Shortcut list response

```json
{
  "shortcuts": [
    {
      "id": "claude-code",
      "name": "Claude Code",
      "command": "claude",
      "host": "cygwin_tmux",
      "description": "Start Claude Code in Cygwin tmux",
      "icon": null
    }
  ]
}
```

### Create/update shortcut request

```json
{
  "name": "Codex",
  "command": "codex",
  "host": "cygwin_tmux",
  "description": "Start Codex in Cygwin tmux",
  "icon": null
}
```

### Create session request

```json
{
  "shortcut_id": "claude-code",
  "workspace_path": "D:/Projects/TermBridge",
  "session_name": "termbridge-claude"
}
```

### Session response additions

```json
{
  "id": "...",
  "name": "termbridge-claude",
  "shortcut_id": "claude-code",
  "shortcut_name": "Claude Code",
  "workspace_path": "D:/Projects/TermBridge",
  "host": "cygwin_tmux",
  "tmux_session_name": "termbridge-claude",
  "url": "http://127.0.0.1:..."
}
```

## Technical questions

1. API 是否直接删除 `/api/terminals`，还是先返回 410/兼容空列表？需求倾向直接迁移，但 Plan 阶段需要按前端调用点确认影响面。
2. `cygwin_tmux` 创建 tmux session 时，shortcut command 是作为 tmux shell-command 一次性执行，还是先创建 shell 再 send-keys？Plan 阶段需要结合现有 tmux persistence 实现选择。
3. Workspace path 在 Cygwin bash 内是否需要做 Windows path 到 Cygwin path 的转换，或复用已有 Cygwin 入口逻辑。
4. session restart 对已存在 tmux session 的语义：attach 现有 session，还是 kill 并重建。需要沿用现有 restart 语义确认。

## Risks

- 一次性迁移命名会影响 API、前端、测试和已有 state，改动面较大。
- 直接删除旧 terminal definitions 数据会让已有配置丢失；这是已接受需求，但需要在实现中避免误删无关 state。
- Shortcut command 允许任意非空白字符串，属于本机命令执行入口；这是产品目标，但 UI 需要避免给用户误导。
- tmux session name 规范化如果不稳定，会影响恢复和切换会话。
- Windows path 与 Cygwin path 转换可能影响 workspace 启动位置。

## Alternatives

1. 只在 UI 使用 shortcut，底层保留 `TerminalDefinition`。
   - 拒绝原因：用户已决策底层命名一次性迁移。
2. 将 workspace 存在 shortcut 中。
   - 拒绝原因：用户已决策 shortcut 表达如何启动，新建会话时选择 shortcut + workspace。
3. 默认 shortcuts 设为 system 类别禁止删除。
   - 拒绝原因：本阶段不实现 system/user 类别，也不控制默认 shortcut 能否修改或删除。
4. 启动前检测进程和版本。
   - 拒绝原因：用户已决策只检查 host 配置就绪。

## User review notes

待补充。
