# Terminal-first 无界界面范围说明

Review status: Accepted

当前：轻量模式 / light，需求 / Requirement

## Background

最近一次 Terminal-first 改造已经完成了第一轮去卡片化和浅色/暗色主题切换，但通过 Pomelo PW 截图审视后，当前结果仍更接近“局部去卡片化 + 暗色补丁”，还没有形成彻底统一的 Terminal-first 设计语言。

截图依据：

- `.pomelo-pw/02-session-light.png`
- `.pomelo-pw/03-session-settings-light.png`
- `.pomelo-pw/04-environment-light.png`
- `.pomelo-pw/05-shortcuts-light.png`
- `.pomelo-pw/08-session-dark.png`
- `.pomelo-pw/09-session-settings-dark.png`
- `.pomelo-pw/10-environment-dark.png`
- `.pomelo-pw/11-shortcuts-dark.png`

## Goal

将当前会话工作台从“大白卡片 + 大圆角 + 大阴影”的产品卡片感，进一步调整为更彻底、更一致的 Terminal-first 无界风格。

目标视觉方向：

- 终端区域成为主视觉中心，`/session` 更像 full-bleed terminal workbench，而不是浅色页面中的黑色卡片。
- 弱化所有路由中的大卡片、厚边框、大圆角、阴影和白色浮层。
- 左侧会话管理更像 terminal/workbench explorer，而不是普通 SaaS 管理侧栏。
- 右侧 terminal tab 和 terminal viewport 更接近工作区边缘，减少容器装饰。
- 用细分隔线、背景层次、monospace/code surface 和 spacing 维持结构，而不是依赖大卡片边框。
- 浅色/暗色主题必须来自同一套设计 token，不再逐个组件临时补 `dark:` class。
- 暗色主题不能出现突兀白色菜单、白色 command block 或低对比度标题。

## Non-goal

- 不改信息架构。
- 不新增新的页面或导航模型。
- 不重做 IDE-like 多面板系统。
- 不调整后端、API、session lifecycle 或 terminal attach 逻辑。
- 不修改 ttyd iframe 内部主题；本轮只控制 TermBridge 外壳主题。
- 不以“全黑主题”替代设计系统；浅色和暗色都要一致、可用。
- 不在本轮引入复杂 design system 框架；优先用现有 Tailwind/Vue 结构收敛语义样式。

## Current gaps from screenshot audit

### Session workspace

当前 `/session` 方向基本正确，但仍不够沉浸：

- light mode 下右侧 terminal 像浅灰页面里的黑色大矩形，周围 padding 和页面感仍明显。
- terminal 顶部 tab 区域太弱，只有孤立的 `+`，不像完整 workbench tab strip。
- sidebar 仍偏普通管理侧栏，terminal/tool explorer 气质不足。
- dark mode 更接近目标，但 sidebar 文本、icon、层级的对比度偏低。
- follow-up 截图显示，会话列表面板与终端之间仍存在明显风格差异：色面、控件密度、圆角和主按钮视觉重量都不够协调。
- 需要同时兼顾浅色/暗色两主题，不能只把 dark mode 改得更像终端而忽略 light mode 的桥接效果。

### Settings menu

Settings menu 是最明显的暗色主题漏点：

- dark mode 中主 settings menu 仍是白色浮层。
- language submenu 也未统一暗色样式。
- 底部 settings trigger 在 dark mode 中是白色 pill，破坏暗色沉浸感。

### Environment management

Environment 页面仍偏“产品表单卡片”：

- `ttyd` 和环境配置区域仍使用大 rounded border panel。
- 输入框是标准表单样式，边框和轮廓较强。
- dark mode 下卡片轮廓更明显，输入框边框过亮，部分标题/label 对比度不足。

### Shortcut management

Shortcut 页面是当前最不彻底的页面：

- light mode 仍是 card grid：rounded card + border + shadow。
- command 内容放在白色 pill/input-like 块里，产品卡片感强。
- dark mode 下 command 白底块非常突兀，卡片边框过亮，标题对比度不足。
- 网格卡片更像 dashboard，不像 command palette / CLI registry。

## Follow-up direction

### Session sidebar neutral bridge

会话列表面板采用“中性色桥接”方向，而不是纯浅色 Explorer 或完全终端同色化：

- light mode 使用浅蓝灰 / 雾灰 surface，避免纯白 SaaS 侧栏硬贴深色 terminal。
- dark mode 使用深蓝黑 / 墨灰 surface，比 terminal viewport 略亮或略有层次，但仍属于同一 terminal workbench 色系。
- 浅色和暗色使用同一套语义色阶与结构规则，只做亮度偏移；不能变成两套互不相关的设计。
- sidebar 与 terminal 的统一重点同时包含：色面割裂、控件产品化、密度不一致。
- 搜索框、新建会话按钮、底部工具按钮应更像 workbench toolbar 控件，而不是强 SaaS 表单和主 CTA。
- 树节点行高、缩进、图标尺寸、hover/selected/disabled 状态要更 compact、explorer-like，同时保持 light/dark 下的清晰层级。
- “新建会话”不能抢过 terminal 的主视觉中心；如果继续保留蓝色，应降低尺寸、圆角或视觉重量。
- terminal 顶部 tab 继续使用 Reka UI Tabs 组件组织，tab bar 需要跟随浅色/暗色主题颜色，而不是固定只适配深色。
- `/shortcuts` 的环境分组标题后不再显示数量 badge，降低标题行噪音。
- session sidebar 折叠后的左下角展开按钮使用圆形按钮，不再是方形按钮。

## Follow-up acceptance

- [ ] `/session` 主工作区更接近 full-bleed terminal workbench，terminal viewport 不再像浅色页面内的大黑卡片。
- [ ] terminal tab strip 有明确工作台栏结构，`+` 不再孤立漂浮。
- [ ] sidebar 在 light/dark 下都保持清晰层级，但视觉更 compact、explorer-like。
- [ ] session sidebar 使用中性色桥接：light mode 为浅蓝灰 / 雾灰，dark mode 为深蓝黑 / 墨灰，两主题共享同一语义结构和密度规则。
- [ ] sidebar 与 terminal 的色面、控件圆角、按钮视觉重量和树节点密度不再显得来自两套 UI。
- [ ] 搜索框、新建会话按钮、底部工具按钮更像 workbench toolbar，减少强产品化表单 / CTA 感。
- [ ] terminal 顶部 tab 使用 Reka UI Tabs 的 Root/List/Trigger/Content 组织，并在 light/dark 下跟随主题颜色。
- [ ] `/shortcuts` 环境分组标题后不显示数量 badge。
- [ ] session sidebar 折叠后的左下角展开按钮为圆形按钮。
- [ ] Settings 主菜单、theme submenu、language submenu、底部 settings trigger 在 dark mode 下全部统一暗色样式。
- [ ] Environment 页面去除主要大卡片感，section 优先使用 divider/background hierarchy，而不是 rounded bordered panel。
- [ ] Shortcut 页面去除卡片阴影和强 dashboard 感，command 内容改为 terminal-like monospace/code surface。
- [ ] dark mode 下不出现突兀白色 command block、白色 menu 或不可读标题。
- [ ] 所有主要路由的浅色/暗色视觉语言来自统一 token 或统一 class pattern。
- [ ] 不引入新的水平滚动问题。
- [ ] 前端 typecheck/lint 通过。
- [ ] Pomelo PW 截图脚本可复跑，并更新截图用于回归比对。

## Priority

### P0 — 修复破坏暗色沉浸的漏点

- Settings 主浮层、language submenu、theme submenu 使用统一 dark menu style。
- 底部 settings trigger 在 dark mode 下改为 dark ghost/pill，不使用白色背景。
- Shortcut command block 在 dark mode 下改为暗色 code surface。
- 补齐 Shortcut、Environment、menu item 的 dark text / muted text / hover state。

### P1 — 收敛剩余卡片语言

重点区域：

- `frontend/src/components/ShortcutManagement.vue`
- `frontend/src/components/EnvironmentManagement.vue`
- `frontend/src/components/SessionCreateForm.vue`
- `frontend/src/components/WorkspaceBrowser.vue`

方向：

- 去除 `shadow-*` 作为主要层级手段。
- 减少 `rounded-xl`，必要时收敛为更克制的 `rounded-md` 或移除。
- 大 bordered panel 改为 divider-based sections。
- command/config 类内容使用 terminal-like monospace/code surface。

### P2 — 重塑 Session workspace

- terminal 区域更 full-bleed。
- tab strip 更像 workbench 顶部栏。
- sidebar 更 compact / explorer-like。
- sidebar 采用中性色桥接：light mode 从纯白/浅灰收敛到浅蓝灰/雾灰，dark mode 从纯黑/深色补丁收敛到深蓝黑/墨灰。
- 同步收敛 sidebar 的色面、搜索框、新建按钮、底部工具按钮、树节点行高、缩进、圆角和 hover/selected/disabled 状态。
- light mode 下减少“浅色页面 + 黑色 terminal 盒子”的割裂。

### P3 — 固化视觉回归

- 保留并复跑 `.pomelo-pw/terminal-first-style-audit.yaml`。
- 后续补充 create session panel、shortcut create/edit dialog 的截图状态。

## Risk

- 去掉卡片装饰后，结构层次可能变弱，需要通过 spacing、divider、背景色和字体层级保持可读性。
- 如果 terminal 区域过度贴边，可能影响 tab、空状态和小屏可用性。
- 暗色主题如果只靠局部 `dark:` 补丁，会继续出现漏点；需要先收敛语义样式或统一 class pattern。
- 中性色桥接如果只降低对比度，可能导致 sidebar 层级变糊；必须通过选中态、hover、细分隔线和字体层级维持可扫描性。
- light mode 不能简单复用 dark terminal 色块，否则会变成伪暗色主题；需要保留浅色主题身份，同时降低纯白侧栏和深色终端的割裂。
- Shortcut 从卡片网格改为 command registry/list 可能影响现有用户对快捷方式的浏览方式，需要保持扫描效率。
- Environment 表单去卡片化后，仍要保证 input、button、status badge 的可辨识度和可点击性。

## Decisions

- 继续采用 Terminal-first 方向。
- 不采用完整 Editor-like 重构。
- 不采用仅轻微去卡片化的 Soft minimal 方向。
- 下一轮优先修复暗色主题漏点和 Shortcut/Environment 的卡片残留。
- 对 session sidebar 采用中性色桥接方向，不采用纯浅色 Explorer 对比，也不采用 sidebar 与 terminal 完全同色。
- 会话列表和终端协调时，色面割裂、控件产品化、密度不一致三类问题都纳入范围。
- 浅色/暗色两主题使用同一语义色阶偏移：浅色为浅蓝灰 / 雾灰，暗色为深蓝黑 / 墨灰，结构、密度、圆角规则保持一致。
- terminal 顶部 tab 继续基于 Reka UI Tabs，不改成手写 tab；本轮补齐 TabsContent 与 light/dark 主题色跟随。
- Pomelo PW 截图作为后续视觉回归依据，截图输出保留在 `.pomelo-pw/`。
