# 会话侧边栏两级分组与目录名消歧计划

- Flow mode: standard
- Stage: Plan
- Review status: Accepted
- Date: 2026-06-14

## Requirement Basis

- `docs/requirement/20260614-session-sidebar-two-level-groups.md`
- Requirement status: Accepted

## Goal

将会话侧边栏调整为“固定环境分组 + 目录/会话树”的两级视觉结构。目录节点默认显示目录名，并在同一环境内目录名重复时按需向上补充父级路径消歧，同时保留完整路径搜索、tooltip、会话选择、新建会话和目录操作能力。

## Implementation Steps

1. 调整 `SessionList.vue` 的树数据建模
   - 保留现有后端 `SessionEnvironment` / `SessionWorkspace` 数据输入，不修改 API。
   - 将用于 `TreeRoot` 的节点列表从“环境节点作为根节点”改为“每个环境分组内单独生成 workspace/session 节点”。
   - `SessionTreeNode.kind` 不再需要把 `environment` 作为树节点 kind；环境信息由分组容器承载，workspace/session 节点继续携带 `host`。

2. 新增目录展示 label 计算
   - 对每个环境内的 `workspaces` 计算 display label。
   - 默认使用路径 basename。
   - 当同一环境内 basename 重复时，对重复项逐级向上补充父级路径片段。
   - 保证同一环境内不同完整路径最终显示为不同 label。
   - 保留 `workspace.path` 作为完整路径，用于 tooltip、搜索、create context、remove workspace。

3. 调整过滤和空状态逻辑
   - 搜索过滤继续使用完整路径 `workspace.path`，不改为只搜 display label。
   - 过滤结果仍按环境分组输出；没有匹配 workspace 的环境不展示。
   - 保持现有 loading、error、no ready environment、empty session 状态语义。

4. 调整模板结构
   - 在会话列表滚动区域中按环境渲染固定分组 header。
   - 每个环境分组 header 显示环境 icon 和环境 label，不提供折叠/展开交互。
   - 每个环境分组下渲染独立 `TreeRoot` 或等效树区域，只包含 workspace/session 节点。
   - workspace 节点作为环境分组下的第一层，session 节点作为 workspace 子节点。

5. 保持选择、展开与 active session 行为
   - active session 变化时，仍能找到对应 session node 并设置选中态。
   - 默认展开所有 workspace 节点，使 session 仍可直接可见。
   - 因环境不再是树节点，展开 key 只覆盖 workspace 节点。
   - `handleTreeSelect` 继续只在 session 节点上触发 `select`。

6. 保持新建和删除行为
   - 顶部“新建会话”继续根据当前选中节点取 `host` / `workspacePath`。
   - workspace 行 hover 操作继续支持“在目录中新建会话”和“删除目录”。
   - session 行继续支持启动中 spinner、running 停止、stopped 删除等现有状态操作。
   - 固定环境 header 不作为 create context 来源；如果只选中为空，则顶部新建保持无上下文或现有默认行为。

7. 样式与可访问性收尾
   - 环境 header 使用弱分组样式，避免像可点击树节点。
   - workspace label 保持 `min-w-0 flex-1 truncate`，避免横向滚动和遮挡右侧操作按钮。
   - workspace title 使用完整路径。
   - 浅色/暗色主题沿用当前会话面板色彩系统。

## Files to Change

- `web/src/components/SessionList.vue`
  - 树节点类型和 computed 数据结构。
  - workspace display label 计算函数。
  - active session 查找、默认展开 key、选中态辅助函数。
  - 模板中环境固定分组和各分组下树渲染。
  - workspace tooltip/search/create/remove 行为保持完整路径。

## Verification Plan

1. 静态检查
   - `npm --prefix web run lint`
   - `npm --prefix web run typecheck`

2. 手动 UI 验证
   - 打开 `/session`。
   - 确认环境以固定分组显示，不作为可折叠树节点。
   - 确认目录默认只显示目录名。
   - 构造或观察同一环境内同名目录，确认重复目录显示父级路径片段用于区分。
   - 确认不同环境下同名目录不会互相触发消歧。
   - 确认 hover 目录节点时，新建/删除目录按钮不遮挡 label，不出现横向滚动。
   - 确认 hover 目录节点 tooltip 显示完整路径。
   - 确认搜索完整路径片段仍可找到目录。
   - 确认点击 session 仍切换终端 tab / active session。
   - 确认顶部新建会话仍使用当前选中 session/workspace 的目录上下文。
   - 确认浅色和暗色主题下分组、目录、会话状态颜色仍协调。

## Risks

1. 多个独立 `TreeRoot` 可能影响键盘导航连续性；如发现体验割裂，可改为单个 `TreeRoot` 承载目录/会话节点，同时在外层渲染环境分组容器。
2. 环境 header 移出树后，active session 查找和默认展开逻辑需要同步调整，避免选中态丢失。
3. Windows、WSL、Linux 路径格式不同，basename 和父级片段计算需要兼容 `\` 与 `/`。
4. 同名目录消歧在极端相似路径下可能仍较长，需要依靠截断和 tooltip 控制视觉宽度。

## Rollback

如果实现后交互或视觉风险过高，可以回退到当前三层树结构，仅保留目录 label 的 basename/tooltip 计算作为较小范围优化。回退时不需要后端或数据迁移。

## User Review Notes

- 2026-06-14: 用户要求进入 Plan / 计划阶段，Requirement 已更新为 Accepted。
