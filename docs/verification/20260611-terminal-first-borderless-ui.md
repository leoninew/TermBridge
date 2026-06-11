# Terminal-first 无界界面验证

Review status: Accepted

当前：轻量模式 / light，验证阶段 / Verification

## What changed

- 根据 Pomelo PW 截图审视结果，扩展 `docs/requirement/20260611-terminal-first-borderless-ui.md`，记录整体 Terminal-first 深化方向、P0-P3 优先级和验收标准。
- Session terminal 工作区进一步 full-bleed：右侧主工作区统一为 terminal dark surface，tab strip 改为更明确的顶部工作台栏。
- 左下角 settings menu 修复暗色主题漏点：主菜单、theme submenu、language submenu、menu item hover 和底部 settings trigger 在 dark mode 下不再出现突兀白色浮层。
- Shortcut 页面从 card grid / dashboard 感向 command registry 收敛：去除卡片阴影和大圆角，改用分隔线、左边界和 terminal-like monospace command surface。
- Environment 页面去除主要 rounded bordered panel，改用 divider-based sections；输入框、按钮、badge 和标题补齐 dark mode 对比度。
- Session create panel、Workspace browser、shortcut dialogs、AppShell dialogs、toast、Home/Help 辅助入口补齐暗色样式，并减少 rounded-xl / shadow-heavy 表现。
- Session sidebar 去掉“会话管理”标题；新建会话按钮移动到目录路径搜索框右侧；搜索逻辑仅匹配 workspace 目录路径，不再匹配环境名、会话名或快捷方式。
- Sidebar 折叠按钮移动到底部设置按钮左侧；设置按钮去掉文本说明，仅保留 icon；折叠后的展开按钮浮在左下角。
- 检查等宽字体使用范围：除 shortcut command 展示与 command 输入框外，移除 Environment 路径字段等非命令行元素的 `font-mono`。
- 扩展 `.pomelo-pw/terminal-first-style-audit.yaml`，加入 create session panel 与 shortcut create dialog 的 light/dark 截图状态；截图保留在 `.pomelo-pw/` 用于回归比对。
- Follow-up：根据新反馈将 session sidebar 收敛为 light/dark 双主题下的中性色桥接面板，减少纯白侧栏与深色 terminal 的割裂。
- Follow-up：压低 session sidebar 搜索框、新建会话按钮、底部工具按钮和折叠展开按钮的圆角、尺寸与视觉重量，使其更像 workbench toolbar。
- Follow-up：收紧 tree row 的间距、缩进、行高、action icon 尺寸和 hover/selected 状态，让会话树更 compact、explorer-like。
- Follow-up：terminal 顶部继续使用 Reka UI Tabs，并补齐 TabsContent 组织终端内容；tab bar 在 light/dark 下跟随主题色。
- Follow-up：`/shortcuts` 环境分组标题后移除数量 badge，降低标题行噪音。
- Follow-up：session sidebar 折叠后的左下角展开按钮改为圆形按钮。
- Final polish：新建会话表单、WorkspaceBrowser 和 HomeOnboarding 环境卡片改为完整边框，避免只显示左边线像少画三边的卡片。
- Final polish：`/shortcuts` 快捷方式卡片改为完整边框，编辑/删除按钮默认展示，不再仅 hover/focus 时出现。
- Final polish：`/shortcuts` command 展示与 command 输入框统一为 `text-xs`，长命令通过 `title` 提供完整内容提示。

## Acceptance

- [x] `/session` 主工作区更接近 full-bleed terminal workbench，terminal viewport 不再像浅色页面内的大黑卡片。
- [x] terminal tab strip 有明确工作台栏结构，`+` 不再孤立漂浮。
- [x] sidebar 在 light/dark 下都保持清晰层级，并保留 explorer-like 结构。
- [x] session sidebar 使用中性色桥接：light mode 从纯白收敛到浅蓝灰 / 雾灰，dark mode 使用比 terminal 略亮的深蓝黑 / 墨灰。
- [x] sidebar 与 terminal 的色面、控件圆角、按钮视觉重量和树节点密度进一步收敛。
- [x] 搜索框、新建会话按钮、底部工具按钮更像 workbench toolbar，减少强产品化表单 / CTA 感。
- [x] terminal 顶部 tab 使用 Reka UI Tabs 的 Root/List/Trigger/Content 组织，并在 light/dark 下跟随主题颜色。
- [x] `/shortcuts` 环境分组标题后不显示数量 badge。
- [x] session sidebar 折叠后的左下角展开按钮为圆形按钮。
- [x] 新建会话表单、WorkspaceBrowser、HomeOnboarding 环境卡片和 `/shortcuts` 快捷方式卡片使用完整边框，不再像少画三边的卡片。
- [x] `/shortcuts` 卡片编辑/删除按钮默认可见。
- [x] `/shortcuts` command 展示和 command 输入框使用更小字号；长命令悬停可查看完整内容。
- [x] Settings 主菜单、theme submenu、language submenu、底部 settings trigger 在 dark mode 下全部统一暗色样式。
- [x] Environment 页面去除主要大卡片感，section 优先使用 divider/background hierarchy，而不是 rounded bordered panel。
- [x] Shortcut 页面去除卡片阴影和强 dashboard 感，command 内容改为 terminal-like monospace/code surface。
- [x] dark mode 下不出现突兀白色 command block、白色 menu 或不可读标题。
- [x] create session panel、shortcut create dialog、toast、Home/Help 辅助入口纳入整体暗色/无界风格收敛。
- [x] Session sidebar 搜索只搜索目录路径，搜索框右侧放置新建会话按钮，并移除“会话管理”标题。
- [x] Sidebar 折叠和设置按钮在左下角紧邻排列；设置按钮仅保留图标；折叠后展开按钮浮在左下角。
- [x] 非命令行元素不使用等宽字体；保留 shortcut command 展示与 command 输入框的 `font-mono`。
- [x] 所有主要路由的浅色/暗色视觉语言进一步收敛到统一 class pattern。
- [x] 不引入新的水平滚动问题（通过 Pomelo PW 1440x960 截图观察）。
- [x] 前端 typecheck/lint 通过。
- [x] Pomelo PW 截图脚本可复跑，并更新截图用于回归比对。

## Commands

- `yarn --cwd frontend typecheck`：通过。
- `yarn --cwd frontend lint`：通过。
- `pomelo-pw validate .pomelo-pw/terminal-first-style-audit.yaml`：通过。
- Follow-up `yarn --cwd frontend typecheck`：通过。
- Follow-up `yarn --cwd frontend lint`：通过。
- Follow-up `pomelo-pw validate .pomelo-pw/terminal-first-style-audit.yaml`：通过。
- Follow-up `pomelo-pw run .pomelo-pw/terminal-first-style-audit.yaml -v`：通过，54 steps，生成 15 张截图用于 sidebar 中性色桥接检查。
- Follow-up 2 `yarn --cwd frontend typecheck`：通过。
- Follow-up 2 `yarn --cwd frontend lint`：通过。
- Follow-up 2 `pomelo-pw validate .pomelo-pw/terminal-first-style-audit.yaml`：通过。
- Follow-up 2 `pomelo-pw run .pomelo-pw/terminal-first-style-audit.yaml -v`：通过，54 steps，生成 15 张截图用于 tabs/shortcuts/collapse button 检查。
- Final `yarn --cwd frontend typecheck`：通过。
- Final `yarn --cwd frontend lint`：通过。
- Final `pomelo-pw validate .pomelo-pw/terminal-first-style-audit.yaml`：通过。

## Screenshot review

关键截图已更新到 `.pomelo-pw/`：

- `.pomelo-pw/02-session-light.png` 与 `.pomelo-pw/10-session-dark.png`：session sidebar 已移除标题，搜索框与新建按钮同排，底部折叠/设置 icon 紧邻排列；follow-up 后 light mode sidebar 从纯白收敛到浅蓝灰 / 雾灰，dark mode sidebar 使用比 terminal 略亮的深蓝黑 / 墨灰，tree row 和 toolbar 控件更 compact。
- `.pomelo-pw/03-create-session-light.png` 与 `.pomelo-pw/11-create-session-dark.png`：create session panel 已纳入无界/暗色样式验证。
- `.pomelo-pw/04-session-settings-light.png` 与 `.pomelo-pw/12-session-settings-dark.png`：settings menu light/dark 都使用统一 menu style，dark mode 不再是白色菜单。
- `.pomelo-pw/05-environment-light.png` 与 `.pomelo-pw/13-environment-dark.png`：environment section 改为 divider-based 结构，减少大卡片边框感。
- `.pomelo-pw/06-shortcuts-light.png` 与 `.pomelo-pw/14-shortcuts-dark.png`：shortcut command 已使用 terminal-like monospace surface，不再是突兀白色块。
- `.pomelo-pw/07-shortcut-dialog-light.png` 与 `.pomelo-pw/15-shortcut-dialog-dark.png`：shortcut create dialog 已纳入 light/dark 回归截图。
- `.pomelo-pw/08-help-light.png` 与 `.pomelo-pw/09-help-dark.png`：Help placeholder 保持无界页面样式。

## Remaining risk

- `/session` light mode 现在采用浅蓝灰 / 雾灰 sidebar 桥接深色 terminal，这是保留浅色主题身份同时减少割裂的折中；如果希望 terminal 外壳也变浅，可后续单独细化。
- Shortcut 页面仍保留 grid 排列，避免过度改变信息架构；如果要更彻底的 command registry/list，可作为下一轮交互改造。
- Pomelo PW 覆盖了主路由、settings menu、create session panel、shortcut create dialog；删除确认弹窗和 workspace browser 展开态未单独截图，但相关基础样式已随组件补齐。
