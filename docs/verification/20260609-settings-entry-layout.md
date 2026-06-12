# 前端设置入口布局优化验证

Review status: Accepted

Flow mode: light
Stage: Verification

## What changed

- 移除 `App.vue` 中顶部 `AppStatus` 渲染，顶部 logo/标题、右上导航和语言切换不再显示。
- 将“新建会话”从右上圆形图标改为会话管理面板内的主操作按钮。
- 在会话管理面板底部增加带分隔线的“设置”入口。
- 设置入口使用 reka-ui `DropdownMenu`，菜单展示为：环境管理、终端管理、语言；语言使用子菜单展示中文和 English。
- 终端管理菜单项跳转 `/terminals` 路由，主内容区显示 `TerminalManagement`。
- 新增环境管理视图，菜单项跳转 `/environment`；该视图展示 Windows、Cygwin、WSL、Cygwin 配置入口，并承载 ttyd 管理表单。
- 移除终端管理页面右上角 ttyd 设置入口和新建终端工具条，ttyd 设置迁移到环境管理。
- 会话管理面板和终端面板调整为主视口内垂直充满；设置入口保持在会话面板底部。
- 会话管理“新建会话”放回右上角并保持单行显示。
- 终端标题和当前会话小标题改为同一行展示，小标题超长时截断。
- 终端管理页面改为主内容区内垂直充满，并让终端卡片网格在剩余高度内滚动。
- 设置菜单保持环境管理、终端管理和语言入口；点击左侧会话列表可从环境管理或终端管理返回会话视图。

## Acceptance

- [x] 顶部标题/导航/语言切换区域不再渲染。
- [x] 会话管理面板底部左侧有“设置”入口，并与会话列表区域有分隔线。
- [x] 设置入口点击后打开 reka-ui DropdownMenu。
- [x] DropdownMenu 展示环境管理、终端管理、语言；语言下包含中文、English。
- [x] 终端管理菜单项跳转 `/terminals` 路由。
- [x] 环境管理入口跳转 `/environment`，展示 Windows/Cygwin/WSL、Cygwin 配置和 ttyd 管理。
- [x] 终端管理页面右上角 ttyd 设置入口和新建终端工具条已移除。
- [x] 当前页面仍可在会话视图、环境管理视图和终端管理视图之间切换。
- [x] 从环境管理或终端管理可通过点击左侧会话列表返回会话视图。
- [x] 终端管理页面在主内容区内垂直充满。
- [x] 主界面左右面板使用 reka-ui Splitter 实现拖拽调整宽度。

## Commands

- `yarn --cwd web typecheck`：通过。
- `yarn --cwd web lint`：通过。

## Remaining risk

- 视觉验证未通过浏览器截图执行；当前仅做代码和类型/lint 检查。
- Windows/Cygwin/WSL 和 Cygwin 配置目前是前端管理入口骨架；保存能力需要后端环境配置 API 支持。
