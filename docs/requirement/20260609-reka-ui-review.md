# Reka UI 样式和组件改进审视

Review status: Accepted

当前：轻量模式 / light，范围说明 / Scope note

## Goal

基于引入的 `docs/llms.txt`（来源：Reka UI llms.txt）审视当前前端样式和组件实现，找出适合用 Reka UI primitive 改进的交互、可访问性和一致性问题。

## Non-goal

- 本阶段不直接重写 UI。
- 不引入新的组件库；继续使用现有 `reka-ui`、Vue、Tailwind 和 lucide-vue。
- 不做大规模视觉 redesign，只聚焦现有页面中明显适合 Reka UI primitive 的交互点。

## Acceptance

- 识别当前已使用和未使用但适合的 Reka UI primitive。
- 输出按优先级排序的改进建议。
- 标明每项建议影响的组件和收益。
- 覆盖顶部菜单/导航入口的组件化改进建议。
- 覆盖会话管理与终端区域的左右结构，以及左导航折叠/收起能力。
- 明确哪些建议适合立即进入实现，哪些应暂缓。

## Risk

- Reka UI 是 unstyled primitive，接入后仍需维护 Tailwind 样式；不能期望自动获得完整视觉系统。
- Dialog/Alert Dialog/Toolbar/Tree 等 primitive 会改变 DOM 和事件结构，需要避免一次性大改导致回归。
- 当前页面规模较小，过度组件化可能比原生实现更重。

## Review notes

- 用户引入 `docs/llms.txt`，要求基于 Reka UI 文档审视样式和组件改进。
