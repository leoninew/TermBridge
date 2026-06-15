# 快捷方式管理改进实施计划

- Flow mode: strict
- Stage: Plan
- Review status: Accepted
- Date: 2026-06-15

## Requirement and Spec basis

- Requirement: `docs/requirement/20260615-shortcut-management-improvements.md`，状态 `Accepted`。
- Spec: `docs/spec/20260615-shortcut-management-improvements.md`，状态 `Accepted`。

本计划实现快捷方式从 `terminals.json` 拆出到 `shortcuts.json`，改为环境分组的两级存储和两级 API response；保留 shortcut `id` 供会话引用；后端注入 session repository 统计 `used_session_count` 并校验删除；前端直接消费两级 response，移除基于 `openTerminalSessions` / `sessions` 的删除判断。本轮不实现排序。

## Implementation steps

### 1. 扩展后端模型

修改：

- `src/termbridge/models.py`

计划：

1. 新增快捷方式存储 value 模型：
   ```py
   class ShortcutDefinition(BaseModel):
       id: str
       command: str
       description: str | None = None
   ```
2. 新增 `ShortcutState`，结构为：
   ```py
   shortcuts: dict[ShortcutHost, dict[str, ShortcutDefinition]]
   ```
   并提供包含 `windows_cygwin`、`windows_wsl`、`linux` 的默认空分组。
3. 保留领域/API 用 `Shortcut`，字段包含 `id`、`name`、`command`、`host`、`description`。
4. 新增 `ShortcutResponse(Shortcut)`，包含：
   ```py
   used_session_count: int = 0
   ```
5. 新增 `ShortcutEnvironmentResponse`：
   ```py
   host: ShortcutHost
   label: str
   shortcuts: list[ShortcutResponse]
   ```
6. 将 `ShortcutListResponse` 从 `shortcuts: list[...]` 改为：
   ```py
   environments: list[ShortcutEnvironmentResponse]
   ```
7. 从 `TerminalState` 中移除 `shortcuts` 或停止使用该字段；`TerminalState` 只承载 terminal settings 和各环境 settings。

注意：`CreateShortcutRequest` / `UpdateShortcutRequest` 可以保留现有形态。

### 2. 新增 shortcuts repository 和 settings 路径

修改：

- `src/termbridge/settings.py`
- `src/termbridge/repositories.py`

计划：

1. 在 `Settings` 增加：
   ```py
   @property
   def shortcuts_file(self) -> Path:
       return self.state_dir / "shortcuts.json"
   ```
2. 新增 `FileShortcutRepository`：
   - 构造参数：`shortcuts_file: Path`
   - `get_state() -> ShortcutState`
   - `save_state(state: ShortcutState) -> ShortcutState`
   - 缺失文件返回 `ShortcutState()`。
   - JSON decode / pydantic validation 错误统一抛出 `ShortcutRepositoryError`。
   - 写入逻辑复用现有 tempfile + `os.replace` 原子写入风格。
3. `FileTerminalRepository` 保留现有职责，但后续不再读写 shortcuts。
4. 不在 `FileShortcutRepository` 中兼容旧 `terminals.json` 扁平结构；旧数据由迁移脚本处理。

### 3. 调整依赖注入

修改：

- `src/termbridge/di.py`

计划：

1. 新增：
   ```py
   def get_shortcut_repository(settings: SettingsDep) -> FileShortcutRepository:
       return FileShortcutRepository(settings.shortcuts_file)
   ```
2. 修改 `get_terminal_service()`，注入：
   - `FileTerminalRepository`
   - `FileShortcutRepository`
   - `FileSessionRepository`
   - `Settings`
3. 保持 `get_session_service()` 注入 `TerminalService` 的方向不变，避免循环：
   - repository 层无依赖。
   - `TerminalService` 依赖 `FileSessionRepository` 只读统计。
   - `SessionService` 依赖 `TerminalService` 解析和启动快捷方式。

### 4. 重写 TerminalService 快捷方式 CRUD

修改：

- `src/termbridge/services.py`

重点函数：

- `TerminalService.__init__`
- `list_shortcuts`
- `create_shortcut`
- `update_shortcut`
- `delete_shortcut`
- `resolve_shortcut_command`
- `resolve_shortcut`
- `_find_shortcut`
- `_ensure_default_shortcuts`
- `_ensure_unique_shortcut_name`

计划：

1. 构造函数接收 terminal repository、shortcut repository、session repository。
2. `list_shortcuts()`：
   - 读取 `ShortcutState`。
   - 如果 `shortcuts.json` 缺失或为空，调用新的 `_ensure_default_shortcuts()` 写入默认 shortcuts。
   - 用 session repository 统计 `shortcut_id -> count`。
   - 按固定 host 顺序返回 `ShortcutListResponse(environments=[...])`。
   - 每个 environment 包含 label 和 shortcuts。
3. `create_shortcut()`：
   - trim `name` 和 `command`。
   - 校验 name / command 非空。
   - 校验 `state.shortcuts[host]` 中不存在同名。
   - 生成唯一 `id`，例如 `shortcut_<uuid>`；默认 shortcuts 继续使用固定 id。
   - 写入 `state.shortcuts[host][name] = ShortcutDefinition(id=..., command=..., description=...)`。
   - 返回 `ShortcutResponse` 或 `Shortcut`（API response 可由 FastAPI 按模型序列化）。
4. `update_shortcut(shortcut_id, request)`：
   - 通过遍历两级 map 找到旧 `(host, name, definition)`。
   - 合并 request 字段。
   - 如果 `name` 或 `host` 变化且 `used_session_count > 0`，抛出 `ShortcutInUseError` 或 `InvalidTerminalConfigError`（Plan 建议使用 409 语义的 `ShortcutInUseError`）。
   - 校验目标 host 下新 name 不重复（排除当前 shortcut）。
   - `id` 保持不变。
   - 若 key 变化，删除旧 key，写入新 key。
   - 保存并返回更新后的 shortcut response。
5. `delete_shortcut(shortcut_id)`：
   - 先基于 session repository 统计引用。
   - 如果引用数量大于 0，抛出 `ShortcutInUseError`。
   - 找到对应 `(host, name)` 后删除。
   - 找不到则抛出 `ShortcutNotFoundError`。
6. `_find_shortcut(shortcut_id)`：
   - 遍历 `ShortcutState.shortcuts`，由 definition.id 找到 shortcut。
   - 返回派生 `Shortcut(id, name, command, host, description)`。
7. `_ensure_default_shortcuts()`：
   - 输出新两级结构。
   - 默认 shortcuts 保持现有 id：`cygwin-bash`、`cygwin-cmd`、`cygwin-claude` 等。
   - 写入 `shortcuts.json`，不写 `terminals.json`。
8. `_shortcut_usage_counts()` helper：
   - 使用 `FileSessionRepository.list_entries()`。
   - 统计 `entry.shortcut_id`。

### 5. 更新 API 层

修改：

- `src/termbridge/api.py`

计划：

1. `GET /api/shortcuts` response model 改为新的 `ShortcutListResponse` 两级结构。
2. `POST /api/shortcuts` response model 建议改为 `ShortcutResponse`，返回 `used_session_count: 0`。
3. `PUT /api/shortcuts/{shortcut_id}` response model 建议改为 `ShortcutResponse`。
4. `DELETE /api/shortcuts/{shortcut_id}` 保持路径不变。
5. 删除接口可移除 API 层对 `session_service.list_sessions()` 的重复检查，统一交给 `TerminalService.delete_shortcut()`；或者保留也可以，但为避免重复读取和逻辑分散，计划移除 API 层检查。
6. 保持现有 exception mapping，`ShortcutInUseError` 返回 409。

### 6. 新增一次性迁移脚本

新增：

- `scripts/migrate_shortcuts_to_shortcuts_json.py`

计划：

1. 支持默认路径：
   - 输入：`.termbridge/terminals.json`
   - 输出：`.termbridge/shortcuts.json`
2. 可选参数建议：
   - `--terminals-file <path>`
   - `--shortcuts-file <path>`
   - `--force`：允许覆盖已存在 `shortcuts.json`。
3. 行为：
   - 读取旧 terminals JSON。
   - 提取 `shortcuts` 数组。
   - 按 host/name 写成新结构。
   - 保留旧 id；缺失 id 时生成新 id。
   - 同 host 重名时报错退出，不覆盖。
   - 默认如果输出文件存在则拒绝覆盖。
   - 不修改旧 `terminals.json`。
4. 脚本输出简短结果：迁移了多少快捷方式，输出文件路径。

### 7. 更新前端类型和 API 消费

修改：

- `web/src/types/sessions.ts`
- `web/src/api/sessions.ts`

计划：

1. `Shortcut` 增加：
   ```ts
   used_session_count: number
   ```
2. 新增：
   ```ts
   export interface ShortcutEnvironment {
     host: ShortcutHost
     label: string
     shortcuts: Shortcut[]
   }
   ```
3. `ShortcutListResponse` 改为：
   ```ts
   environments: ShortcutEnvironment[]
   ```
4. `listShortcuts()` 函数签名不变，返回类型随 interface 更新。
5. create/update/delete shortcut API 仍使用 `shortcut.id`。

### 8. 更新快捷方式管理页

修改：

- `web/src/components/ShortcutManagement.vue`

计划：

1. 移除 props：
   ```ts
   sessions: Session[]
   ```
2. 移除 `usedShortcutIds` computed。
3. 移除 `shortcutGroups` computed。
4. 本地状态从 `shortcuts = ref<Shortcut[]>([])` 改为：
   ```ts
   const shortcutEnvironments = ref<ShortcutEnvironment[]>([])
   ```
5. `load()` 中：
   - `shortcutResponse.environments` 直接赋值给 `shortcutEnvironments`。
   - 环境 readiness 仍从 `listEnvironments()` 获取，用于 host select disabled reason。
6. 模板中 `v-for` 直接遍历 `shortcutEnvironments`。
7. 删除按钮：
   ```vue
   :disabled="shortcut.used_session_count > 0"
   ```
8. 删除 title：使用 `used_session_count` 表示被多少会话使用；若现有 i18n 不足，补充文案。
9. `hasDuplicateName()` 改为遍历 `shortcutEnvironments` 中同 host 的 shortcuts。
10. `edit` / `delete` 继续使用 `shortcut.id`。
11. 保持新增/编辑 modal 行为不变。

### 9. 更新新建会话表单

修改：

- `web/src/components/SessionCreateForm.vue`

计划：

1. `shortcuts` 状态可以保留为扁平列表，也可以改为两级 environments。
2. 为减少 UI 改动，计划在 `loadShortcuts()` 后将两级 response flatten 为当前表单局部使用的 `shortcuts`：
   ```ts
   shortcuts.value = response.environments.flatMap((environment) => environment.shortcuts)
   ```
3. 这是表单内部为了 combobox filter 的局部转换，不是管理页分组计算；不影响用户提出的管理页直接消费两级结构目标。
4. `filteredShortcuts` 继续按 `selectedHost` 过滤。
5. combobox value 和 create payload 继续使用 `shortcut.id` / `shortcut_id`。
6. 保留上一轮已修复的 combobox 选中后折叠行为，不恢复 `open-on-focus`。

### 10. 更新 AppShell 传参

修改：

- `web/src/components/AppShell.vue`

计划：

1. 动态组件传参目前统一传 `:sessions="openTerminalSessions"`。
2. 快捷方式管理页不再声明 `sessions` prop，因此 Vue 会把未声明 prop 作为 fallthrough attribute；为避免无意义传参，可接受短期保留，也可在 Plan 实现中改成更明确的 route-specific prop。
3. 本计划建议最小改动：删除 `ShortcutManagement.vue` 的 `sessions` prop 即可；若 type/lint 或 Vue warning 需要，再调整 `AppShell` 的动态组件传参结构。

### 11. 更新 i18n 文案

修改：

- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`

计划：

1. 若删除按钮 title 需要显示使用数量，新增：
   - zh-CN: `该快捷方式正在被 {count} 个会话使用，不能删除`
   - en-US: `This shortcut is used by {count} session(s) and cannot be deleted`
2. 保留现有 `shortcutManagement.delete.inUse` 也可以，但建议改为支持 count。

### 12. 更新测试

修改：

- `tests/test_terminal_service.py`
- `tests/test_repositories.py`
- `tests/test_api.py`
- 可新增 `tests/test_shortcut_migration.py`

后端测试计划：

1. repository：
   - `FileShortcutRepository` missing file returns empty/default `ShortcutState`。
   - save creates parent directory。
   - invalid JSON raises `ShortcutRepositoryError`。
   - incompatible schema raises `ShortcutRepositoryError`。
2. service：
   - default shortcuts 初始化到 `shortcuts.json`，不是 `terminals.json`。
   - `list_shortcuts()` 返回 `environments` 两级结构和固定 host 顺序。
   - `list_shortcuts()` 为被 session 引用的 shortcut 返回正确 `used_session_count`。
   - create shortcut 生成 id，写入对应 host/name。
   - duplicate name in same host rejected，不同 host 同名允许。
   - update command/description 保持 id 不变。
   - update name/host 迁移 key，id 不变。
   - update used shortcut 的 name/host 被拒绝。
   - delete unused shortcut succeeds。
   - delete used shortcut rejected。
   - resolve shortcut by id works against two-level storage。
3. API：
   - `GET /api/shortcuts` 返回 `environments`。
   - POST/PUT/DELETE response 和错误码符合预期。
   - FakeTerminalService 同步改为新 response。
4. migration：
   - 从旧 terminals JSON 生成 shortcuts JSON。
   - 同 host 重名时报错。
   - 输出文件存在且无 `--force` 时拒绝。

前端验证计划：

1. `yarn typecheck`：覆盖 TS 类型从扁平 response 到 `environments` 的改动。
2. `yarn lint`：覆盖 Vue 组件和类型改动。
3. 手动或运行 app 检查：快捷方式管理页分组展示、删除禁用、编辑保存、新建会话选择快捷方式。

## Files to change

### Product code

- `src/termbridge/settings.py`
- `src/termbridge/models.py`
- `src/termbridge/repositories.py`
- `src/termbridge/di.py`
- `src/termbridge/services.py`
- `src/termbridge/api.py`
- `web/src/types/sessions.ts`
- `web/src/api/sessions.ts`（如仅类型引用变化，可不改逻辑）
- `web/src/components/ShortcutManagement.vue`
- `web/src/components/SessionCreateForm.vue`
- `web/src/components/AppShell.vue`（视实现需要）
- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`

### Scripts

- `scripts/migrate_shortcuts_to_shortcuts_json.py`

### Tests

- `tests/test_terminal_service.py`
- `tests/test_repositories.py`
- `tests/test_api.py`
- `tests/test_shortcut_migration.py`（新增，或合入 repository/service 测试）

### SpecFlow docs

- `docs/verification/20260615-shortcut-management-improvements.md`（Verification 阶段）

## Verification plan

### Backend checks

从仓库根目录运行：

```bash
uv run pytest tests/test_repositories.py tests/test_terminal_service.py tests/test_api.py
```

如新增独立迁移测试：

```bash
uv run pytest tests/test_shortcut_migration.py
```

最后运行较完整后端测试：

```bash
uv run pytest
```

### Frontend checks

从 `web/` 目录运行：

```bash
yarn typecheck
yarn lint
```

如时间允许，运行：

```bash
yarn build
```

### Manual checks

1. 启动后端和前端。
2. 打开快捷方式管理页。
3. 确认页面按后端返回 environments 分组展示。
4. 确认使用中快捷方式显示不可删除状态。
5. 创建一个未使用快捷方式，确认可删除。
6. 编辑未使用快捷方式的 name/host，确认分组更新。
7. 编辑使用中快捷方式的 command/description，确认允许。
8. 编辑使用中快捷方式的 name/host，确认后端拒绝并提示。
9. 打开新建会话表单，确认快捷方式下拉仍可按运行环境过滤并提交 `shortcut_id`。

## Blockers

暂无阻塞项。

## Assumptions

1. 保留 `shortcut_id` 是本轮会话引用的唯一稳定方案。
2. `shortcuts.json` 缺失时自动生成默认 shortcuts 是可接受的；旧用户数据需要通过迁移脚本进入新文件。
3. 迁移脚本默认不修改旧 `terminals.json`，只生成 `shortcuts.json`。
4. 本轮不实现排序，但 API 两级 response 已为后续分组内排序/拖拽准备结构。

## Risks

1. `ShortcutListResponse` 从 `shortcuts` 改为 `environments` 是 API breaking change，前端所有调用必须同步更新。
2. `TerminalService` 注入 session repository 后构造函数影响测试较多，需要集中更新测试 helper。
3. 使用 `host + name` 做存储 key 且保留 id 做引用，更新 name/host 时容易遗漏 key 迁移或重复校验。
4. 迁移脚本涉及用户本地配置文件，必须避免默认覆盖已有 `shortcuts.json`。
5. `terminals.json` 停止承载 shortcuts 后，现有测试中对 `TerminalState.shortcuts` 的断言都需要更新。

## Rollback

1. 若实现过程中发现拆出 `shortcuts.json` 风险过大，可停止实现并回到 Spec 重新评审，不做半成品迁移。
2. 若代码已改但验证失败，可通过 git diff 定位本需求相关文件，撤回 shortcut repository/service/API/frontend 类型改动。
3. 不执行迁移脚本则不会修改用户现有 state；迁移脚本默认拒绝覆盖 `shortcuts.json`，降低回滚成本。

## User review notes

- 2026-06-15: 用户要求进入 Plan 阶段；Spec 已标记为 Accepted。
