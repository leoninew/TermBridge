# 快捷方式管理改进验证

- Flow mode: strict
- Stage: Verification
- Review status: Draft
- Date: 2026-06-15

## Requirement alignment

基于 `docs/requirement/20260615-shortcut-management-improvements.md` 的已接受需求，本次实现对齐情况如下：

1. 快捷方式存储文件已从 `terminals.json` 拆分到 `.termbridge/shortcuts.json`，后端新增 `Settings.shortcuts_file` 和 `FileShortcutRepository`。
2. `shortcuts.json` 使用两级结构：`host -> shortcut name -> shortcut definition`。
3. 快捷方式保留稳定 `id`，新建快捷方式时由后端生成 `shortcut_<uuid>`，会话继续通过 `shortcut_id` 引用。
4. `GET /api/shortcuts` 返回 `environments` 两级列表，每个 shortcut 包含 `used_session_count`。
5. `used_session_count` 由 `TerminalService` 通过注入的 `FileSessionRepository.list_entries()` 统计。
6. 快捷方式管理页直接消费后端 `environments`，删除状态只依赖 `shortcut.used_session_count`。
7. 后端删除和使用中快捷方式重命名 / 跨 host 修改由服务层校验，使用中删除或 key 迁移会抛出冲突。
8. 新增一次性迁移脚本从旧 `terminals.json.shortcuts` 生成新 `shortcuts.json`。
9. 运行时业务逻辑不再兼容或读取旧 `terminals.json.shortcuts`。
10. 本轮未实现快捷方式排序 / 拖拽，符合 non-goal。
11. 后续排查中发现并修复了两个与本需求交互直接相关的前端问题：删除确认按钮未发起请求、新建会话快捷方式 combobox 选中后列表重新打开。这两个修复支撑“删除可用”和“新建会话可选择快捷方式”的验收标准。

## Spec alignment

对照 `docs/spec/20260615-shortcut-management-improvements.md`：

- 存储模型已按规格新增 `ShortcutDefinition` / `ShortcutState`，`TerminalState` 不再承载 shortcuts。
- API response 已按规格改为 `ShortcutListResponse.environments`，环境固定包含 `windows_cygwin`、`windows_wsl`、`linux`。
- `ShortcutResponse` 包含 `id`、`name`、`command`、`host`、`description`、`used_session_count`。
- 创建、更新、删除仍以 `shortcut_id` 作为 API path / session 引用标识。
- 使用中的 shortcut 允许更新 `command` / `description`，禁止更新 `name` / `host`。
- 删除接口的实际引用校验集中在 `TerminalService.delete_shortcut()`。
- 前端类型、管理页和新建会话表单已同步两级 response。
- 迁移脚本默认拒绝覆盖已有输出，同 host 重名时报错，保留旧 id，缺失 id 时生成新 id。
- 删除确认按钮不再使用会自动关闭 dialog 的 `AlertDialogAction`，而是由业务函数完成“调用接口 -> 成功后关闭 -> 重新加载”的流程。
- 新建会话快捷方式 combobox 外层不再使用 `<label>` 包裹，避免 label 默认聚焦行为在选中后重新打开列表。

## Plan alignment

对照 `docs/plan/20260615-shortcut-management-improvements.md`：

- 已完成后端模型、repository、DI、service、API 更新。
- 已新增迁移脚本。
- 已更新前端类型、快捷方式管理页、新建会话表单和 i18n 文案。
- 已更新后端 service / repository / API 测试，并新增迁移脚本测试。
- `web/src/api/sessions.ts` 逻辑无需修改，函数签名通过类型接口变化自然同步。
- `web/src/components/AppShell.vue` 未修改；计划允许最小改动仅删除 `ShortcutManagement.vue` 的 `sessions` prop，当前 typecheck、lint、build 均通过。
- 本次未启动应用做人工 UI 检查；已通过 frontend typecheck、lint 和 build 做静态与构建验证。
- 计划外的 ttyd 端口监听 / 启动等待改动已撤回，当前 `SessionService` 仍使用 `ProcessAdapter.is_running(ProcessHandle(pid=entry.pid))` 判断 ttyd 进程状态。

## Actual diff summary

当前工作区 diff 涉及 18 个文件，约 911 行新增、161 行删除。

### Backend

- `src/termbridge/settings.py`
  - 新增 `shortcuts_file` 路径。
- `src/termbridge/models.py`
  - 新增 shortcut 存储模型和两级 response 模型。
  - `TerminalState` 停止包含快捷方式列表。
- `src/termbridge/repositories.py`
  - 新增 `FileShortcutRepository`，负责读写 `shortcuts.json`。
- `src/termbridge/di.py`
  - 注入 shortcut repository 和 session repository 给 `TerminalService`。
- `src/termbridge/services.py`
  - 快捷方式 CRUD 改为基于 `ShortcutState`。
  - 查询返回 environment groups 和 `used_session_count`。
  - 删除、使用中 name/host 更新由服务层校验。
  - 保留 id 查找和会话启动解析能力。
  - ttyd lifecycle 逻辑保持 pid / `ProcessAdapter.is_running()` 语义，未保留端口监听判断改动。
- `src/termbridge/api.py`
  - shortcut create/update response 改为 `ShortcutResponse`。
  - 删除接口移除 API 层 session 列表检查，统一交给 service。

### Frontend

- `web/src/types/sessions.ts`
  - `Shortcut` 增加 `used_session_count`。
  - 新增 `ShortcutEnvironment`。
  - `ShortcutListResponse` 改为 `environments`。
- `web/src/components/ShortcutManagement.vue`
  - 移除 `sessions` prop、`usedShortcutIds`、本地分组 computed。
  - 直接渲染 `shortcutEnvironments`。
  - 删除状态与提示使用 `used_session_count`。
  - 删除确认按钮改为普通 `button`，避免 `AlertDialogAction` 自动关闭导致待删除 shortcut 被清空。
- `web/src/components/SessionCreateForm.vue`
  - 从两级 response 局部展开 shortcuts 供 combobox 按 host 过滤。
  - 移除 `open-on-focus`。
  - 快捷方式 combobox 外层从 `<label>` 改为 `<div>` + `<span>` 标签，避免选中后列表重新打开。
- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`
  - 删除禁用提示加入使用数量。

### Scripts

- `scripts/migrate_shortcuts_to_shortcuts_json.py`
  - 新增一次性迁移脚本。

### Tests

- `tests/test_terminal_service.py`
- `tests/test_repositories.py`
- `tests/test_api.py`
- `tests/test_shortcut_migration.py`
  - 覆盖新 repository、service、API contract 和迁移行为。
- `tests/test_services.py`
  - 在撤回 ttyd 端口判断后，保持原有 pid / process adapter 行为测试通过。

### Other changed files

- `justfile`
  - 当前 diff 中包含 justfile recipe 调整（`dev-backend` / `dev-frontend` / `check` / `clean` 等）。该文件不属于本快捷方式管理需求、Spec 或 Plan 的计划范围，应作为独立变更审视或拆分。

## Planned vs actual changed files

| Planned file | Actual status |
| --- | --- |
| `src/termbridge/settings.py` | 已修改 |
| `src/termbridge/models.py` | 已修改 |
| `src/termbridge/repositories.py` | 已修改 |
| `src/termbridge/di.py` | 已修改 |
| `src/termbridge/services.py` | 已修改 |
| `src/termbridge/api.py` | 已修改 |
| `web/src/types/sessions.ts` | 已修改 |
| `web/src/api/sessions.ts` | 未修改；逻辑无需变化 |
| `web/src/components/ShortcutManagement.vue` | 已修改 |
| `web/src/components/SessionCreateForm.vue` | 已修改 |
| `web/src/components/AppShell.vue` | 未修改；最小改动下无需变化 |
| `web/src/i18n/locales/zh-CN.json` | 已修改 |
| `web/src/i18n/locales/en-US.json` | 已修改 |
| `scripts/migrate_shortcuts_to_shortcuts_json.py` | 已新增 |
| `tests/test_terminal_service.py` | 已修改 |
| `tests/test_repositories.py` | 已修改 |
| `tests/test_api.py` | 已修改 |
| `tests/test_shortcut_migration.py` | 已新增 |
| `docs/verification/20260615-shortcut-management-improvements.md` | 已更新 |
| `tests/test_services.py` | 非计划文件；用于确认撤回 ttyd 端口判断后的原 session service 行为 |
| `justfile` | 非计划文件；不属于本需求范围 |

## Acceptance criteria checklist

| # | 验收标准 | 结果 |
| --- | --- | --- |
| 1 | 快捷方式存储文件为 `shortcuts.json` | 通过 |
| 2 | `shortcuts.json` 为环境 -> 名称 -> 数据 | 通过 |
| 3 | 快捷方式数据包含稳定 `id` | 通过 |
| 4 | 新建快捷方式生成唯一 `id` | 通过 |
| 5 | 会话继续通过 shortcut `id` 引用 | 通过 |
| 6 | 查询接口返回两级列表和 `used_session_count` | 通过 |
| 7 | `used_session_count` 后端统计 | 通过 |
| 8 | 管理页直接使用两级结构渲染 | 通过 |
| 9 | 管理页删除判断只依赖 `used_session_count` | 通过 |
| 10 | 管理页不再接收 sessions 用于占用判断 | 通过 |
| 11 | 后端删除前校验实际会话引用 | 通过 |
| 12 | 未使用快捷方式删除成功并从存储移除 | 通过；同时修复了删除确认按钮未发请求的问题 |
| 13 | 编辑保存后后端存储更新、前端刷新展示 | 通过 |
| 14 | 同环境名称唯一 | 通过 |
| 15 | 不同环境允许同名 | 通过 |
| 16 | 新建会话表单仍按环境过滤选择快捷方式 | 通过；同时修复了选中后列表不收起的问题 |
| 17 | 新建会话提交继续使用 `shortcut_id` 并可解析 | 通过 |
| 18 | 一次性迁移读取旧 `terminals.json` 并生成 `shortcuts.json` | 通过 |
| 19 | 业务读写路径不继续使用 `terminals.json.shortcuts` | 通过 |
| 20 | 删除和编辑在浅色和暗色主题下保持可用且状态清晰 | 自动验证通过构建；未执行人工主题检查 |
| 21 | 本轮不包含排序入口、接口或持久化逻辑 | 通过 |

## Test results

本次重新验证的命令结果：

```text
uv run pytest tests/test_terminal_service.py tests/test_repositories.py tests/test_api.py tests/test_shortcut_migration.py tests/test_services.py
99 passed, 1 warning
```

```text
uv run ruff check
All checks passed!
```

```text
yarn --cwd web typecheck
Done
```

```text
yarn --cwd web lint
Done
```

```text
uv run pytest
138 passed, 1 warning
```

```text
yarn --cwd web build
built successfully
```

`pytest` warning：

- `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`

`yarn --cwd web build` 存在非失败警告：

- `node_modules/@vueuse/core/dist/index.js` 的 Rolldown `[INVALID_ANNOTATION]` 警告。
- chunk size 超过 500 kB 的打包提示。

这些警告不影响本次验证通过。

## Missed or expanded scope

### Missed manual checks

未启动应用做人工 UI 检查。当前通过 typecheck、lint、build 和后端测试覆盖主要 contract 与行为。

建议如需最终人工验收，可单独执行：

1. 打开快捷方式管理页。
2. 检查使用中的快捷方式删除按钮禁用和 count title。
3. 检查未使用快捷方式新增、编辑、删除。
4. 检查删除确认按钮点击后发起删除请求，成功后关闭并刷新列表。
5. 检查新建会话快捷方式下拉按环境过滤，选中后列表收起，并提交 `shortcut_id`。
6. 分别在浅色 / 暗色主题下查看禁用状态。

### Expanded or unrelated scope

1. `web/src/components/ShortcutManagement.vue` 的删除确认按钮修复、`web/src/components/SessionCreateForm.vue` 的 combobox label 修复，虽不在原 Plan 的逐项文件改动细节中，但直接对应删除可用性和新建会话选择快捷方式体验，建议保留。
2. ttyd 端口监听 / 启动等待相关改动已撤回，不再属于当前 diff。
3. `justfile` 变更不属于本快捷方式管理需求，建议独立审视或拆分，不应与本需求一起作为同一交付边界提交，除非用户确认它属于本次发布/开发工具改进。

## Risks

1. API response 从扁平 `shortcuts` 改为 `environments` 是 breaking change；当前前端调用方已更新并通过 typecheck，但外部未同步调用方需要按新 contract 调整。
2. 运行时不兼容旧 `terminals.json.shortcuts`；旧用户数据必须先执行迁移脚本生成 `shortcuts.json`。
3. 未执行人工 UI 主题检查，视觉状态仍建议在最终验收时快速确认。
4. 构建存在现有依赖 annotation 和 chunk size 警告，虽然不影响本次功能通过，但可作为后续构建优化项。
5. 当前 diff 包含非本需求的 `justfile` 变更，提交前建议拆分或明确纳入独立提交。

## Incomplete items

产品代码、测试和迁移脚本已完成。

未完成 / 待用户决策项：

1. 可选人工验收：浅色 / 暗色主题下的视觉检查和真实页面交互检查。
2. `justfile` 变更是否保留在本次工作区，或拆成独立提交 / 单独处理。

## Conclusion

本次快捷方式管理改进已完成 strict 流程的 Verification 阶段复核。实现与已接受的 Requirement、Spec、Plan 基本对齐；自动化测试、lint、typecheck 和 build 均通过。此前临时加入的 ttyd 端口监听 / 启动等待改动已撤回，当前验证范围聚焦快捷方式管理、删除确认和新建会话快捷方式选择。主要剩余风险是未执行人工 UI 主题检查，以及当前 diff 中存在与本需求无关的 `justfile` 变更，需要提交前单独处理。
