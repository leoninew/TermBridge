# tmux window 与会话存储生命周期修复计划

Review status: Accepted

## Requirement and spec basis

- `docs/requirement/20260611-tmux-window-storage-lifecycle.md`
- `docs/spec/20260611-tmux-window-storage-lifecycle.md`
- 当前流程已切换为严格模式 / strict。
- 后续 `docs/requirement/20260611-simplify-stopped-session-semantics.md` 已覆盖原恢复复用决策：stop 后 stopped entry 不保留自己的 managed tmux window；start 会优先复用记录 id 或同名 window，都不存在时再创建新 window。
- 用户提出：`.termbridge/sessions.json` 应与左侧导航一致，按环境、标准化目录完整路径、会话名称三级结构组织。
- 用户明确：不向后兼容，不迁移历史 sessions 数据。

## Implementation steps

1. 修正 tmux window 创建命令
   - 修改 `TerminalService._create_window_script()`。
   - 新 workspace tmux session 使用 detached session 直接运行目标 command，并用目标 window name 创建首个 window，避免默认 `bash` window。
   - 已存在 workspace session 时继续使用 `tmux new-window` 创建新 managed window。
   - 保持返回 tmux window id。

2. 修正 stop/start 生命周期
   - `SessionService.stop()` / `_stop_entry()` 停止 ttyd process，kill managed window，清空 `tmux_window_id` 和 URL。
   - `SessionService.start()` 优先复用记录 id 对应 window；记录 id 缺失或失效时按同名 window 复用；都不存在时创建新 managed window 并更新 `tmux_window_id`。
   - `delete()` kill managed window 并删除 entry，但保留 workspace/目录节点。
   - `close_all()` 终止 managed windows 和 workspace tmux sessions，但保留 records 与 workspace/目录节点。

3. 调整目录节点管理语义
   - Repository 支持空 workspace 持久化。
   - 增加目录节点删除能力：删除二级目录节点及其 entries，并清理对应 tmux windows/session。
   - 后端暴露目录删除 API，前端目录节点 hover 时展示删除 icon 并调用该 API。
   - 创建表单上下文由树节点点击显式设置：环境节点提供 host，目录节点提供 host + workspace，session 节点不再作为唯一上下文来源。

4. 调整 sessions 持久化 schema
   - 在模型中引入环境、目录、会话名称三级结构。
   - 环境 key 使用 host 值：`windows_cygwin`、`windows_wsl`、`linux`。
   - 目录 key 使用标准化完整路径；Windows/Cygwin 路径统一为 forward-slash 且大小写归一。
   - 会话 key 使用 session name。
   - 同一环境同一目录下创建重名会话时拒绝。
   - Repository 对外方法保持尽量稳定，内部适配新 schema。

5. 拒绝旧 schema
   - `FileSessionRepository._read_state()` 只接受新 `{ "environments": { ... } }` schema。
   - 读到旧 `{ "workspaces": { ... } }` schema 时返回 incompatible schema 错误。
   - 删除已添加的旧 schema 迁移测试，改为旧 schema 拒绝测试。

6. 更新规格文档中被本需求覆盖的语义
   - 更新 `docs/spec/20260610-workspace-tmux-session-model.md` 中 stop/restart 相关描述，避免文档与新语义冲突。

7. 更新测试
   - `tests/test_terminal_service.py` 覆盖创建首个 window 不留下默认 window 的 tmux script。
   - `tests/test_services.py` 覆盖 stop 清理 window、start stopped session 复用记录 window、复用同名 window、缺失时创建新 window。
   - 覆盖重名 session 拒绝。
   - 覆盖删除 entry 后 workspace 仍保留。
   - 覆盖目录节点删除会删除 workspace 及其 managed tmux resources。
   - 覆盖新 schema 写读结构和旧 schema 拒绝读取。
   - 调整 close all 测试以符合 stop 保留 window、close all 终止 window/session 的分工。

## Files to change

- `src/termbridge/models.py`
- `src/termbridge/repositories.py`
- `src/termbridge/services.py`
- `src/termbridge/api.py`
- `web/src/api/sessions.ts`
- `web/src/types/sessions.ts`
- `web/src/components/SessionList.vue`
- `web/src/components/AppShell.vue`
- `web/src/i18n/locales/zh-CN.json`
- `web/src/i18n/locales/en-US.json`
- `tests/test_services.py`
- `tests/test_terminal_service.py`
- `tests/test_api.py`
- 可能新增或调整 repository 测试
- `docs/spec/20260610-workspace-tmux-session-model.md`
- `docs/verification/20260611-tmux-window-storage-lifecycle.md`

## Verification plan

- `python -m pytest tests/test_terminal_service.py tests/test_services.py`
- `python -m pytest tests/test_api.py`
- `python -m pytest`
- `python -m ruff check src tests`
- 如环境可用，运行 `python -m mypy src`；若当前环境缺少 mypy，记录为未执行成功。

## Risks

- schema 改造比单纯 lifecycle 修复更大，需避免破坏现有 API response。
- 以 session name 作为 key 后，重命名会话未来需要专门处理；当前没有重命名能力。
- 不兼容旧 sessions schema 会导致历史记录无法自动读取；这是用户明确约束，最终交付需在风险中说明。
- 当前工作区已有其它未提交 UI/SpecFlow 改动，最终提交前需要拆分或确认边界。

## Rollback

- tmux lifecycle 如需回退，需要重新引入 stop 保留 window 与 start/reconnect 复用 window 的区分；当前需求明确不采用该区分。
- schema 写出改造若出现问题，可回退到旧 `workspaces` schema 并仅完成 lifecycle 修复；但这会不满足用户对三层存储结构和不兼容旧数据的要求。

## User review notes

- 用户要求从标准模式切换到严格模式 / strict。
- 用户要求补齐 strict 模式下的 plan 文档，并已补齐对应 spec 文档作为 plan basis。
- 用户明确要求不向后兼容、不迁移历史 sessions 数据；计划已移除旧 schema 迁移步骤，改为拒绝旧 schema。
