# 快捷方式管理改进规格

- Flow mode: strict
- Stage: Spec
- Review status: Accepted
- Date: 2026-06-15

## Requirement basis

基于 `docs/requirement/20260615-shortcut-management-improvements.md`，本规格覆盖以下已接受需求：

1. 快捷方式从 `terminals.json` 拆出到新的 `shortcuts.json`。
2. 快捷方式存储改为两级结构：环境 -> 快捷方式名 -> 快捷方式数据。
3. 快捷方式保留并生成稳定 `id`，会话继续通过 `id` 引用快捷方式。
4. 查询接口返回按运行环境分组的两级快捷方式列表，每个快捷方式包含 `used_session_count`。
5. 前端直接消费两级结构，避免再做分组 compute，也为后续分组内拖拽保留自然数据结构。
6. 前端删除判断只依赖 `used_session_count`。
7. 后端删除接口基于实际会话引用再次校验。
8. 支持一次性数据迁移：读取旧 `terminals.json` 并重新生成 `shortcuts.json`。
9. 迁移完成后的业务读写路径不继续使用 `terminals.json` 中的快捷方式数据。
10. 本轮不实现快捷方式排序。

## Overview

设计将快捷方式从 `terminals.json` 中的“带 id 的扁平数组”拆出到独立的 `shortcuts.json`，并改为“按 host 分组、以 name 为 key、value 保留 id 和业务字段”的结构。

新 `shortcuts.json` 示例：

```json
{
  "shortcuts": {
    "windows_cygwin": {
      "bash": {
        "id": "cygwin-bash",
        "command": "bash",
        "description": "Start Cygwin bash"
      }
    },
    "windows_wsl": {
      "bash": {
        "id": "wsl-bash",
        "command": "bash",
        "description": "Start bash in WSL"
      }
    },
    "linux": {}
  }
}
```

`terminals.json` 后续只负责 terminal settings 和环境 settings，不再保存快捷方式。

API 对外也返回两级结构：环境分组在后端完成，前端直接按返回结构渲染各环境分组。每个快捷方式条目包含：

- `id`
- `name`
- `command`
- `host`
- `description`
- `used_session_count`

会话引用继续使用 `shortcut_id`，这样已有 session lifecycle 中“创建会话 -> 启动会话 -> 根据 id 解析快捷方式”的语义保持清晰。存储结构虽然以 `host + name` 分组，但服务层需要维护 `id -> shortcut` 的查找能力。

## Design decisions

### 1. 存储文件拆分

新增 `Settings.shortcuts_file`，默认路径为：

```text
.termbridge/shortcuts.json
```

新增 `FileShortcutRepository`：

- `FileShortcutRepository`：读写 `shortcuts.json`。
- `FileTerminalRepository`：继续读写 `terminals.json` 中的 terminal settings / environment settings。

推荐新增独立 repository，避免 `FileTerminalRepository` 名称与职责继续混杂。

### 2. 存储模型

`ShortcutState`：

```python
ShortcutMap = dict[ShortcutHost, dict[str, ShortcutDefinition]]

class ShortcutDefinition(BaseModel):
    id: str
    command: str
    description: str | None = None

class ShortcutState(BaseModel):
    shortcuts: ShortcutMap = Field(default_factory=default_shortcut_map)
```

领域模型由 key + value 派生：

```python
class Shortcut(BaseModel):
    id: str
    name: str
    command: str
    host: ShortcutHost
    description: str | None = None

class ShortcutResponse(Shortcut):
    used_session_count: int = 0
```

查询响应使用环境分组：

```python
class ShortcutEnvironmentResponse(BaseModel):
    host: ShortcutHost
    label: str
    shortcuts: list[ShortcutResponse]

class ShortcutListResponse(BaseModel):
    environments: list[ShortcutEnvironmentResponse]
```

理由：

- `host + name` 决定存储位置和同环境名称唯一。
- `id` 稳定保留给会话引用。
- API 直接返回两级结构，前端不需要 `computed shortcutGroups` 反向分组，后续拖拽也可直接在分组数组上操作。

### 3. API 响应模型

`GET /api/shortcuts` 返回两级结构：

```json
{
  "environments": [
    {
      "host": "windows_cygwin",
      "label": "Cygwin",
      "shortcuts": [
        {
          "id": "cygwin-bash",
          "name": "bash",
          "command": "bash",
          "host": "windows_cygwin",
          "description": "Start Cygwin bash",
          "used_session_count": 2
        }
      ]
    },
    {
      "host": "windows_wsl",
      "label": "WSL",
      "shortcuts": []
    },
    {
      "host": "linux",
      "label": "Linux",
      "shortcuts": []
    }
  ]
}
```

设计要求：

1. 返回固定 host 顺序：`windows_cygwin`、`windows_wsl`、`linux`。
2. 即使某个环境无快捷方式，也返回空 `shortcuts` 数组，便于前端稳定渲染和后续拖拽区域挂载。
3. 每个快捷方式条目保留 `host` 字段，便于复用现有前端类型和提交上下文。

理由：用户明确要求 API 返回两级列表，避免前端额外 compute 和后续拖拽时逆向分组。

### 4. 创建和更新语义

创建快捷方式：

- 请求仍包含 `name`、`command`、`host`、`description`。
- 后端生成唯一 `id`。
- 写入 `shortcuts[host][name] = { id, command, description }`。
- 同一 host 下 name 已存在则拒绝。

更新快捷方式：

- API 仍按 `id` 定位：

```http
PUT /api/shortcuts/{shortcut_id}
DELETE /api/shortcuts/{shortcut_id}
```

- 更新请求可包含 `name`、`command`、`host`、`description`。
- 后端通过 `id` 找到当前 `(host, name)`。
- 若 `name` 或 `host` 变化：
  - 检查目标 host 下新 name 不重复。
  - 保持 `id` 不变。
  - 从旧 key 删除，写入新 key。
- 如果该快捷方式 `used_session_count > 0`，允许修改 `command` / `description`，但禁止修改 `name` / `host`。

理由：保留 id 后，API 不必把可变 name 放入 path，避免 URL encode 问题，也更适合会话引用。

### 5. 删除语义

删除接口按 `id` 定位：

```http
DELETE /api/shortcuts/{shortcut_id}
```

后端删除前通过注入的 session repository 统计实际会话引用：

- 若任意 session entry 的 `shortcut_id == shortcut_id`，拒绝删除并返回 conflict。
- 若未使用，删除 `shortcuts[host][name]` 对应条目。

### 6. 使用计数

用户已选择“注入”，因此 `TerminalService` 构造时注入 session repository。

推荐构造关系：

```python
class TerminalService:
    def __init__(
        self,
        terminal_repository: FileTerminalRepository,
        shortcut_repository: FileShortcutRepository,
        session_repository: FileSessionRepository,
        *,
        settings: Settings | None = None,
    ) -> None: ...
```

`used_session_count` 计算：

1. 从 `FileSessionRepository.list_entries()` 获取所有 session entry。
2. 按 `entry.shortcut_id` 计数。
3. 构建 `ShortcutResponse` 时按 `shortcut.id` 填入计数。
4. 再按 host 组装为 `ShortcutListResponse.environments`。

### 7. 一次性迁移

新增迁移脚本，例如：

```text
scripts/migrate_shortcuts_to_shortcuts_json.py
```

迁移输入：

- 旧 `.termbridge/terminals.json`。

迁移输出：

- 新 `.termbridge/shortcuts.json`。

迁移规则：

1. 读取旧 `terminals.json.shortcuts` 扁平列表。
2. 对每个旧 shortcut：
   - 使用旧 `id`；如果缺失，则生成新 id。
   - 使用旧 `host` 作为一级 key。
   - 使用旧 `name` 作为二级 key。
   - value 写入 `{ id, command, description }`。
3. 同一 host 下重复 name：迁移脚本应报错并停止，而不是静默覆盖。
4. 如果 `shortcuts.json` 已存在，默认拒绝覆盖；Plan 阶段决定是否提供 `--force`。
5. 迁移不需要改写 sessions，因为会话继续引用 `shortcut_id`。
6. 迁移后业务路径不再读取 `terminals.json.shortcuts`。

`terminals.json` 是否删除旧 `shortcuts` 字段不作为业务要求；脚本可以选择不修改旧文件，只生成新文件。后续业务代码忽略旧字段。

### 8. 默认快捷方式

当前 `TerminalService._ensure_default_shortcuts` 会在 state 无 shortcuts 时写默认快捷方式。新模型下应迁移为：

- 当 `shortcuts.json` 不存在或 shortcuts 为空时，生成新结构的默认快捷方式。
- 默认快捷方式也必须有稳定 id。
- 不应回写到 `terminals.json`。

### 9. 前端变更

新增两级响应类型：

```ts
export interface Shortcut {
  id: string
  name: string
  command: string
  host: ShortcutHost
  description?: string | null
  used_session_count: number
}

export interface ShortcutEnvironment {
  host: ShortcutHost
  label: string
  shortcuts: Shortcut[]
}

export interface ShortcutListResponse {
  environments: ShortcutEnvironment[]
}
```

`ShortcutManagement.vue`：

- 移除 `sessions` prop。
- 移除 `usedShortcutIds` 计算属性。
- 移除 `shortcutGroups` 计算属性。
- 直接保存和渲染 `shortcutEnvironments` / `environments` 响应。
- 删除按钮：`shortcut.used_session_count > 0` 时禁用。
- 删除 title 使用 `used_session_count` 表达使用中。
- 编辑和删除仍使用 `shortcut.id`。

`SessionCreateForm.vue`：

- `listShortcuts()` 返回两级结构后，表单需要从 `response.environments` 找到当前 `selectedHost` 的快捷方式列表。
- 该查找只用于“当前 host 下快捷方式”选择，不再承担管理页分组职责。
- combobox value 继续使用 `shortcut.id`。
- 新建会话 payload 继续提交 `shortcut_id`。

`AppShell.vue`：

- 不再向 `ShortcutManagement` 传入仅用于占用判断的 sessions。

理由：管理页直接消费后端分组；新建会话表单按已选 host 从分组响应中读取对应列表；会话引用仍保持 id。

## Affected components

### Backend

- `src/termbridge/settings.py`
  - 新增 `shortcuts_file` property。
- `src/termbridge/models.py`
  - 新增 `ShortcutDefinition`、`ShortcutState`、`ShortcutResponse`、`ShortcutEnvironmentResponse`。
  - `TerminalState` 移除 `shortcuts` 字段或停止包含快捷方式。
  - `ShortcutListResponse` 改为 `environments` 两级响应。
- `src/termbridge/repositories.py`
  - 新增 `FileShortcutRepository` 读写 `shortcuts.json`。
  - `FileTerminalRepository` 只处理 `terminals.json` 中的 terminal/environment settings。
- `src/termbridge/services.py`
  - `TerminalService` 注入 terminal repository、shortcut repository 与 session repository。
  - 快捷方式 CRUD 改为操作 `shortcuts.json`。
  - list 注入 `used_session_count` 并返回两级环境分组。
  - resolve by id 需要遍历两级结构找到对应快捷方式。
- `src/termbridge/api.py`
  - list response 改为两级结构并包含 `used_session_count`。
  - delete/update 继续按 `shortcut_id` path 参数。
- `src/termbridge/di.py`
  - 注入 `FileShortcutRepository` 和 `FileSessionRepository` 给 `TerminalService`。
- `scripts/migrate_shortcuts_to_shortcuts_json.py`
  - 新增一次性迁移脚本。

### Frontend

- `web/src/types/sessions.ts`
  - `Shortcut` 增加 `used_session_count`。
  - `ShortcutListResponse` 改为 `environments` 两级结构。
  - 新增 `ShortcutEnvironment` 类型。
- `web/src/api/sessions.ts`
  - `listShortcuts()` 类型随响应更新。
- `web/src/components/ShortcutManagement.vue`
  - 删除 `sessions` prop、`usedShortcutIds`、`shortcutGroups`。
  - 直接渲染 API 返回的 environments。
  - 删除判断改用 `shortcut.used_session_count`。
  - 编辑/删除仍使用 `shortcut.id`。
- `web/src/components/AppShell.vue`
  - 不再依赖给快捷方式管理页传 sessions 做删除判断。
- `web/src/components/SessionCreateForm.vue`
  - 从两级 shortcuts response 中取当前 host 的 shortcuts。
  - 保持使用 `shortcut.id` 创建会话。

### Tests / verification targets

- Python service/API tests：快捷方式两级 list/create/update/delete、used count、使用中删除拒绝、使用中禁止改 name/host。
- Python migration test：旧 terminals 输入生成新 shortcuts 输出。
- Frontend typecheck/lint：确保 `ShortcutListResponse.environments` 改造后无旧扁平响应误用。
- Manual check：快捷方式管理页删除/编辑、新建会话选择快捷方式。

## Interfaces

### Shortcut list response

```json
{
  "environments": [
    {
      "host": "windows_cygwin",
      "label": "Cygwin",
      "shortcuts": [
        {
          "id": "cygwin-bash",
          "name": "bash",
          "command": "bash",
          "host": "windows_cygwin",
          "description": "Start Cygwin bash",
          "used_session_count": 2
        }
      ]
    },
    {
      "host": "windows_wsl",
      "label": "WSL",
      "shortcuts": []
    },
    {
      "host": "linux",
      "label": "Linux",
      "shortcuts": []
    }
  ]
}
```

### Create shortcut request

```json
{
  "name": "bash",
  "command": "bash",
  "host": "windows_cygwin",
  "description": "Start Cygwin bash"
}
```

Response can return the created `ShortcutResponse` with generated `id` and `used_session_count: 0`.

### Update shortcut request

```http
PUT /api/shortcuts/cygwin-bash
```

```json
{
  "name": "Claude",
  "command": "claude",
  "host": "windows_cygwin",
  "description": "Start Claude Code"
}
```

If `name` or `host` changes while `used_session_count > 0`, backend returns conflict.

### Delete shortcut request

```http
DELETE /api/shortcuts/cygwin-bash
```

If `used_session_count > 0`, backend returns conflict.

### Create session request

保持现状：

```json
{
  "name": "默认",
  "workspace": "D:/SourceCodes/mywork/TermBridge",
  "shortcut_id": "cygwin-bash"
}
```

## Technical questions

1. `FileTerminalRepository` 是否应重命名或拆出 settings repository？
   - 本轮不强制；为了控制范围，建议只新增 `FileShortcutRepository`，保留现有 terminal repository 名称。
2. 迁移脚本是否从旧 `terminals.json` 删除 `shortcuts` 字段？
   - 规格倾向不修改旧文件，只生成 `shortcuts.json`；业务代码忽略旧字段。
3. `shortcuts.json` 已存在时迁移是否允许覆盖？
   - 规格倾向默认拒绝覆盖，Plan 可决定是否加 `--force`。

## Risks

1. 快捷方式从 `terminals.json` 拆出后，repository / service 构造关系会变化，需要避免 DI 循环或重复读取状态。
2. 存储以 `host + name` 为 key，同时以 `id` 给会话引用；编辑 name/host 时必须保证 key 迁移但 id 不变。
3. 迁移脚本如果遇到同 host 重名快捷方式，不能静默覆盖，否则会丢数据。
4. 如果业务路径不兼容旧格式，开发环境中未迁移的 `.termbridge/shortcuts.json` 缺失时会走默认快捷方式生成逻辑；需要明确这是否符合预期。
5. 使用中禁止改 name/host 可能让用户无法直接重命名被引用快捷方式；这是为保护会话引用稳定性做出的边界选择。
6. API 返回结构从扁平 `shortcuts` 改为 `environments` 后，所有前端调用方必须同步更新，否则会出现运行时空列表或类型错误。

## Alternatives

1. API 继续返回扁平 shortcuts，由前端 computed 分组。
   - Rejected：用户指出这会造成额外 compute，且后续拖拽还要逆向处理；API 应直接返回两级列表。
2. 新结构下移除 `id`，用 `host + name` 做会话引用。
   - Rejected：用户修正为保留和生成 id，以便会话引用。
3. `TerminalService` 不注入 session repository，在 API 层组合计数。
   - Rejected：用户明确选择注入。
4. 继续把快捷方式放在 `terminals.json`。
   - Rejected：用户明确要求读取旧 `terminals.json` 并重新生成 `shortcuts.json`，后续不再使用 `terminals.json` 存快捷方式。
5. 编辑被使用快捷方式时同步更新所有会话引用。
   - Rejected for now：保留 id 后无需为了 name/host 编辑更新引用；但 name/host 是存储 key，使用中改动仍可能造成心智混乱，先禁止。
6. 同步实现排序。
   - Rejected：用户明确要求排序先不实现。

## User review notes

- 2026-06-15: 用户要求进入 Spec 阶段；Requirement 已标记为 Accepted。
- 2026-06-15: 用户 review 后修正规格：快捷方式保留和生成 id；选择注入 session repository；迁移读取旧 `terminals.json` 并生成 `shortcuts.json`，后续不再使用 `terminals.json` 存储快捷方式。
- 2026-06-15: 用户指出 API 应返回两级列表，避免前端额外 compute 和后续拖拽逆向处理；规格改为 `ShortcutListResponse.environments`。
