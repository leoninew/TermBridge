# tmux window 与会话存储生命周期修复规格

Review status: Accepted

## Requirement basis

- `docs/requirement/20260611-tmux-window-storage-lifecycle.md`
- 当前模式切换为严格模式 / strict。
- 用户明确约束：不向后兼容，不迁移历史 `.termbridge/sessions.json` 数据。

## Overview

本变更同时修复两个层面：

1. tmux runtime lifecycle：workspace tmux session 不应额外产生默认 `bash` window；停止和恢复会话应围绕同一个 managed window 操作。
2. session registry：持久化结构应与 UI 树一致，使用“环境 → 标准化目录完整路径 → 会话名称”的三级结构，使目录和会话成为可直接定位的管理对象。

## Design decisions

### 1. Runtime hierarchy

- Environment：`windows_cygwin`、`windows_wsl`、`linux`。
- Workspace directory：同一 environment + 标准化目录完整路径对应一个 workspace tmux session。
- Session entry：同一 workspace 下的一个会话名称对应一个 managed tmux window。

### 2. First window creation

创建 workspace tmux session 的首个 managed window 时，不使用“先创建空 session，再 new-window”的两步命令。

采用：

- workspace session 不存在：`tmux new-session -d -P -F '#{window_id}' -s <session> -n <window> -c <cwd> <command>`
- workspace session 已存在：`tmux new-window -P -F '#{window_id}' -t <session> -n <window> -c <cwd> <command>`

这样首个 window 就是 managed window，不留下默认 `bash` window。

### 3. Stop / start / delete semantics

- Stop entry：停止 ttyd process，kill managed window，清空连接 URL 和 `tmux_window_id`，entry 标记为 stopped。
- Start entry：从 stopped 状态启动时优先复用 entry 记录的 `tmux_window_id`；记录 id 缺失或失效时，按同 workspace tmux session 下的同名 window 查找并复用；都不存在时创建新的 managed window，更新 entry 的 `tmux_window_id`，再启动新的 ttyd process 并 attach/select 到目标 window；不保留 restart API 命名。
- Delete entry：停止 ttyd process，kill managed window，删除 entry；如果 workspace 已无 entries，保留 workspace record 作为目录节点，并 kill workspace tmux session。
- Delete workspace：删除二级目录节点及所有 entries，清理所有 managed windows 和 workspace tmux session。
- Close all sessions：作为显式高影响操作，清理所有 managed windows 和 workspace tmux sessions，但保留 records 与目录节点。

### 4. sessions.json schema

新的持久化顶层只接受：

```json
{
  "environments": {
    "windows_cygwin": {
      "d:/sourcecodes/agentic": {
        "id": "ws_...",
        "host": "windows_cygwin",
        "path": "D:/Projects",
        "name": "agentic",
        "tmux_session_name": "tb_cyg_...",
        "created_at": "...",
        "updated_at": "...",
        "sessions": {
          "agentic commit": {
            "id": "sess_...",
            "workspace_id": "ws_...",
            "name": "agentic commit",
            "tmux_window_id": "@1"
          }
        }
      }
    },
    "windows_wsl": {},
    "linux": {}
  }
}
```

设计约束：

- environment key 使用 `ShortcutHost` 字面值。
- workspace key 使用标准化完整路径。
- Windows/Cygwin workspace key 使用 forward slash 且大小写归一。
- session key 使用会话名称。
- 同一 environment + workspace 下的 session name 必须唯一；重名创建直接拒绝。
- 不支持旧 `{ "workspaces": ... }` schema；读到旧 schema 应报 incompatible schema。

### 5. API surface

新增目录删除 API：

- `DELETE /api/session-workspaces/{workspace_id}`
- 成功：`204 No Content`
- workspace 不存在：`404`
- repository 错误：`500`

既有 session API 随 stopped 语义改为 start 命名：

- `POST /api/sessions`
- `POST /api/sessions/{session_id}/stop`
- `POST /api/sessions/{session_id}/start`
- `DELETE /api/sessions/{session_id}`
- `POST /api/sessions/close-all`
- `GET /api/session-tree`

### 6. Frontend interaction

- 左侧树继续展示 environment、workspace、session 三级。
- workspace 节点 hover/focus 时右侧展示删除 icon。
- 点击 workspace 删除 icon 调用目录删除 API，刷新 session tree，并关闭该 workspace 下已打开终端 tab。
- 创建会话上下文从显式选中的 tree node 产生：
  - environment node：提供 host。
  - workspace node：提供 host + workspace path。
  - session node：提供其所属 host + workspace path。
- 不再由 active session watch 隐式覆盖 create context。

## Affected components

- `src/termbridge/services.py`：tmux lifecycle 与 workspace 删除。
- `src/termbridge/repositories.py`：sessions schema 读写。
- `src/termbridge/api.py`：workspace 删除 endpoint。
- `frontend/src/api/sessions.ts`：workspace 删除 wrapper。
- `frontend/src/components/SessionList.vue`：workspace 删除 icon、显式 create context。
- `frontend/src/components/AppShell.vue`：workspace 删除 handler 与 tab 清理。
- `frontend/src/i18n/locales/*.json`：目录删除文案。
- `tests/*`：service、repository、API、terminal command 覆盖。

## Technical questions

- 无待用户确认问题。用户已明确不兼容、不迁移旧数据。

## Risks

- 旧 sessions 文件会被拒绝读取，需要用户删除或重新生成。
- session name 成为 key 后，未来如果增加 rename，需要实现 key rename 语义。
- Stop 会清理 managed tmux window，不再保留 stopped entry 自己的 tmux window 内容；start 仍允许用户有意准备同 workspace + 同名 window 并复用。
- 目录删除是 destructive 操作；当前设计为 icon 直接触发，不额外增加确认弹窗。

## Alternatives

### Alternative 1: 保持旧 hash workspace schema

优点：实现变更小。缺点：不符合用户希望按左侧导航三级结构管理 sessions 文件的要求。

### Alternative 2: 兼容并迁移旧 schema

优点：历史数据安全。缺点：用户明确要求不向后兼容、不迁移历史数据；会增加无必要复杂度。

### Alternative 3: Stop 清理 window，start 重建

该方案已被后续 `docs/requirement/20260611-simplify-stopped-session-semantics.md` 接受并覆盖原“恢复复用 window”语义：优点是 stopped 状态与 tmux window 生命周期一致，缺点是 stop 后不保留 tmux window 内容。

## User review notes

- 用户指出恢复会话应复用 window。
- 用户要求 `.termbridge/sessions.json` 与左侧导航一样组织为三层结构。
- 用户补充删除会话不再删除目录，目录用于快速创建会话。
- 用户补充目录节点 hover 展示删除 icon，删除二级节点。
- 用户切换为严格模式 / strict，并要求补 plan 文档。
- 用户明确：不向后兼容，不迁移历史数据。
