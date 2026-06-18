# 快捷方式卡片拖拽排序验证
最后修改时间: 2026-06-18 11:03:53

- Flow mode: light
- Stage: Verification
- Review status: Completed
- Date: 2026-06-18

## Requirement alignment

基于 `docs/requirement/20260618-shortcuts-card-drag-sorting.md` 的已接受需求，本次实现对齐情况如下：

1. `/shortcuts` 页面快捷方式卡片已接入 `VueDraggable`，支持拖拽排序。
2. 拖拽分组使用 `shortcuts:${group.host}`，并配置 `pull: false, put: false`，限制为 Cygwin / WSL / Linux 各自组内排序，不能跨运行环境移动。
3. 排序结果通过 `PUT /api/shortcuts/environments/{host}/order` 提交到后端，并写回 `shortcuts.json` 当前 host 下的有序结构。
4. 后端排序校验要求请求中的 `shortcut_ids` 与该 host 当前所有 shortcut id 集合完全一致，且长度一致；缺失、重复或混入其他 host 的 id 都会失败。
5. 前端拖拽区域保留卡片上的新建会话、编辑、删除按钮，并通过 `filter="button"` 与 `prevent-on-filter=false` 避免按钮点击被拖拽拦截。
6. 拖拽过程新增 ghost 样式和 `GripVertical` 手柄图标，提供清晰排序反馈。
7. 排序失败时前端显示 `shortcutManagement.errors.reorder` toast，并重新加载后端真实顺序。
8. 拖拽 DOM 事件不会再通过 routed component fallthrough listener 误触发 AppShell 的 `@start`，避免请求 `/api/sessions/undefined/start`。
9. 使用中的快捷方式仍禁止删除；编辑时前端禁用 command 字段，后端仅禁止修改 command，允许修改名称和说明。
10. 同 host 内编辑快捷方式不会改变既有排序位置，避免刷新后被编辑项移动到列表末尾。
11. `PUT /api/shortcuts/{id}` 修改成功后，前端使用响应中的 `Shortcut` 直接替换本地 `shortcutEnvironments` 对应项，正常编辑路径不再额外发起 `GET /api/shortcuts` 和 `GET /api/environments`。

## Spec alignment

轻量模式 / light 未创建单独 Spec 文档，本节按 requirement / 需求核对。

实现选择与需求一致：复用项目已有 `vue-draggable-plus` 模式；排序语义限定为同运行环境内顺序调整；后端持久化顺序而不改变 shortcut 的 host / name / command / description / used_session_count 业务语义。

## Plan alignment

轻量模式 / light 未创建单独 Plan 文档，本节按 requirement / 需求和实现前检查核对。

实现范围覆盖：

1. 后端模型、service、API 增加快捷方式排序能力。
2. 前端 API 类型、请求函数和 `/shortcuts` 页面拖拽交互同步更新。
3. 后端 repository/service/API 测试覆盖排序顺序保留、持久化和接口返回。
4. 前端通过 lint 和 typecheck 覆盖拖拽组件、类型与 i18n 变更。

## Actual diff summary

### 预期相关变更

- `docs/requirement/20260618-shortcuts-card-drag-sorting.md`
  - 记录轻量模式需求、用户确认的持久化排序和 Cygwin / WSL / Linux 组内拖拽约束。
- `src/termbridge/models.py`
  - 新增 `ReorderShortcutsRequest`。
- `src/termbridge/services.py`
  - 新增 `TerminalService.reorder_shortcuts()`，校验同 host 完整 id 列表并写回 `ShortcutState.shortcuts[host]` 顺序。
  - 修复同 host 编辑快捷方式时的写回逻辑，原位置替换 definition 而不是删除后追加，避免刷新后被编辑项移动到列表末尾。
  - 调整使用中快捷方式编辑约束：删除和 command 修改返回 409，名称和说明允许更新。
- `src/termbridge/api.py`
  - 新增 `PUT /api/shortcuts/environments/{host}/order`。
- `web/src/types/sessions.ts`
  - 新增 `ReorderShortcutsPayload`。
- `web/src/api/sessions.ts`
  - 新增 `reorderShortcuts()` API client。
- `web/src/components/ShortcutManagement.vue`
  - 引入 `VueDraggable` 和 `GripVertical`，实现同 host 卡片拖拽排序、失败回滚加载和拖拽反馈样式。
  - 禁用组件根节点 listener 继承，避免拖拽事件冒泡触发 AppShell 会话启动；使用中快捷方式编辑时锁定 command 输入。
  - 编辑快捷方式成功后用 `PUT` 返回值本地替换对应卡片，避免额外重新加载快捷方式列表和环境列表。
- `web/src/i18n/locales/zh-CN.json`
  - 新增快捷方式排序失败和 command 锁定中文提示。
- `web/src/i18n/locales/en-US.json`
  - 新增快捷方式排序失败和 command 锁定英文提示。
- `tests/test_repositories.py`
  - 增加快捷方式存储顺序保留测试。
- `tests/test_terminal_service.py`
  - 增加快捷方式同 host 排序持久化、不完整排序拒绝、同 host 编辑后顺序保持，以及使用中快捷方式删除/command 修改保护测试。
- `tests/test_api.py`
  - 增加排序 API 路由覆盖。

### 当前 diff 中的无关变更

- `docs/guides/llms.txt -> docs/guides/reka-llms.txt`
  - 当前工作区显示为 rename，和本次 `/shortcuts` 快捷方式拖拽排序需求无直接关系。本次验证未评估该文档重命名的业务影响。

## Expected vs actual changed files

### Expected

- `docs/requirement/20260618-shortcuts-card-drag-sorting.md`
- `docs/verification/20260618-shortcuts-card-drag-sorting.md`
- `src/termbridge/models.py`
- `src/termbridge/services.py`
- `src/termbridge/api.py`
- `tests/test_repositories.py`
- `tests/test_terminal_service.py`
- `tests/test_api.py`
- `web/src/types/sessions.ts`
- `web/src/api/sessions.ts`
- `web/src/components/ShortcutManagement.vue`
- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`

### Actual

`git diff HEAD --name-status` 显示：

- `R100 docs/guides/llms.txt -> docs/guides/reka-llms.txt`
- `A docs/requirement/20260618-shortcuts-card-drag-sorting.md`
- `M src/termbridge/api.py`
- `M src/termbridge/models.py`
- `M src/termbridge/services.py`
- `M tests/test_api.py`
- `M tests/test_repositories.py`
- `M tests/test_terminal_service.py`
- `M web/src/api/sessions.ts`
- `M web/src/components/ShortcutManagement.vue`
- `M web/src/i18n/locales/en-US.json`
- `M web/src/i18n/locales/zh-CN.json`
- `M web/src/types/sessions.ts`

新增本 verification 文档后，实际变更还包括：

- `A docs/verification/20260618-shortcuts-card-drag-sorting.md`

## Acceptance checklist

1. `/shortcuts` 页面中的快捷方式卡片支持拖拽排序：通过代码核对，已实现。
2. 拖拽只能在同一组内生效，不能跨组移动：通过 `VueDraggable` group 配置和后端 host 校验覆盖。
3. 卡片上的主要操作按钮在拖拽能力启用后仍可正常使用：通过代码核对，按钮保留并被 `filter="button"` 排除出拖拽触发。
4. 拖拽过程有清晰的视觉反馈：通过代码核对，已新增 ghost class 和手柄图标。
5. 排序结果不会影响快捷方式的分组归属：后端排序只重排 `state.shortcuts[host]`，不修改 shortcut definition 或其他 host。
6. 排序结果持久化到快捷方式存储中，刷新或重新进入 `/shortcuts` 后保持：`test_shortcut_service_reorders_shortcuts_within_host` 覆盖重新构造 service 后顺序保持。
7. 编辑同 host 内快捷方式不会破坏拖拽排序结果：`test_shortcut_service_preserves_order_when_updating_shortcut_in_same_host` 覆盖编辑后重新加载仍保留原顺序。
8. 拖拽快捷方式不会误触发会话启动：通过 `defineOptions({ inheritAttrs: false })` 阻断 AppShell `@start` fallthrough listener 绑定到 `/shortcuts` 根 DOM。
9. 使用中的快捷方式不能删除、不能修改 command：后端测试覆盖 409 语义，前端编辑弹窗禁用 command 输入。

## Command results

### Backend tests

命令：

```powershell
uv run pytest tests/test_terminal_service.py tests/test_api.py tests/test_repositories.py
```

结果：

```text
66 passed, 1 warning in 1.41s
```

警告：

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

该警告来自现有测试依赖栈，不是本次排序实现新增失败。

### Ruff

命令：

```powershell
uv run ruff check src/termbridge/models.py src/termbridge/services.py src/termbridge/api.py tests/test_repositories.py tests/test_terminal_service.py tests/test_api.py
```

结果：

```text
All checks passed!
```

### Frontend lint

命令：

```powershell
npm --prefix web run lint
```

结果：通过，无错误输出。

### Frontend typecheck

命令：

```powershell
npm --prefix web run typecheck
```

结果：通过，无错误输出。

### Whitespace check

命令：

```powershell
git diff --check HEAD
```

结果：通过，无输出。

## Missed or expanded scope

1. 未启动真实浏览器进行手动拖拽验证；本次验证依赖后端测试、静态检查和代码核对。
2. 当前 diff 中包含 `docs/guides/llms.txt -> docs/guides/reka-llms.txt` 文档重命名，属于本需求范围外改动，应在提交前确认是否一起提交或拆分。
3. 本次实现新增排序 API，属于持久化排序所需的最小范围扩展，已由用户确认“当然能持久化”。

## Risks

1. 拖拽与按钮点击冲突已通过 `filter="button"` 缓解，但仍建议在真实浏览器中验证点击“新建会话 / 编辑 / 删除”和拖拽手势的细节体验。
2. 后端以 Python dict 插入顺序和 JSON object 顺序承载快捷方式排序；当前 repository 读写和测试已覆盖顺序保留，但未来若引入排序 key 规范化或 JSON 处理变更，需要避免破坏该语义。
3. 当前工作区存在无关文档重命名，若直接提交会扩大提交边界。

## Incomplete items

1. 未执行浏览器级手动验证或截图验证。
2. 未处理或拆分 `docs/guides/llms.txt -> docs/guides/reka-llms.txt` 这一范围外变更。

## Conclusion

本次实现满足已确认的 `/shortcuts` 快捷方式卡片同组拖拽排序与持久化需求。后端测试、Ruff、前端 lint、前端 typecheck 和 whitespace check 均通过。交付前建议补充一次真实浏览器手动拖拽验证，并确认是否将范围外的 `docs/guides` 文档重命名纳入同一提交。
