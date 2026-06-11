# Terminal-first 无界界面范围说明

Review status: Accepted

当前：轻量模式 / light，范围说明 / Scope note

## Goal

将当前会话工作台从“大白卡片 + 大圆角 + 大阴影”的产品卡片感，调整为更贴近终端工具的 Terminal-first 无界风格。

目标视觉方向：

- 终端区域成为主视觉中心。
- 弱化外层卡片、边框、阴影和大圆角。
- 左侧会话管理更像工具侧栏，而不是独立卡片。
- 右侧 terminal tab 和 terminal viewport 更接近工作区边缘，减少容器装饰。
- 用细分隔线、背景层次和 spacing 维持结构，而不是依赖大卡片边框。
- 引入浅色/暗色主题切换，入口放在左下角设置菜单中。

## Non-goal

- 不改信息架构。
- 不新增新的页面或导航模型。
- 不重做 IDE-like 多面板系统。
- 不把整个应用固定成全黑主题；暗色主题应作为可切换选项。
- 不调整后端、API、session lifecycle 或 terminal attach 逻辑。
- 本轮需要覆盖所有路由页面的外层无界/主题适配，包括 Home、Environment、Shortcut、Help 和 Session 工作台；但不重做信息架构。

## Acceptance

- 会话主界面不再呈现明显的大卡片边框和厚重阴影。
- 左侧会话管理与右侧终端区域通过轻量分隔线和背景层次组织。
- 右侧终端区域更贴近“终端工作区”心智，terminal viewport 更沉浸。
- 保留当前会话树、tab、创建会话、删除/停止等已有交互。
- 左下角设置菜单提供浅色/暗色主题切换入口。
- 主题选择在刷新后保持。
- 不引入新的水平滚动问题。
- 前端 typecheck 通过。

## Risk

- 去掉卡片装饰后，结构层次可能变弱，需要通过 spacing、divider、背景色保持可读性。
- 如果终端区域过度贴边，可能影响 tab 和空状态的可用性。
- 所有路由页面都要做外层风格适配，范围扩大后需要避免改动过深导致细节不一致。
- 暗色主题需要避免影响嵌入的 ttyd iframe 内部主题；本轮只控制 TermBridge 外壳主题。

## Decisions

- 采用 Terminal-first 方向。
- 不采用完整 Editor-like 重构。
- 不采用仅轻微去卡片化的 Soft minimal 方向。
- 本轮扩展加入主题切换，入口放在左下角设置菜单。
