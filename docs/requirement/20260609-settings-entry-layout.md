# 前端设置入口布局优化范围说明

Review status: Accepted

Flow mode: light
Stage: Scope note

## Goal

- 删除顶部 logo/标题区域和右上角导航/语言入口。
- 将设置入口放到会话管理面板左下角，作为低干扰底部操作区。
- 设置入口使用 reka-ui `DropdownMenu`，参考 `docs/llms.txt` 中 Dropdown Menu 组件说明。
- 设置菜单展示为：环境管理、终端管理、语言（中文、English）。
- 环境管理用于管理 Windows/Cygwin/WSL、Cygwin 配置和 ttyd 管理；终端管理跳转 `/terminals` 路由。
- 移除终端管理页面右上角 ttyd 和新建终端工具条，相关设置入口迁移到设置菜单/环境管理。
- 会话管理和终端面板在主视口内垂直充满；设置入口固定在会话面板底部。
- 会话管理的“新建会话”在右上角单行显示。
- 终端标题和当前会话小标题同一行显示，不换行。

## Non-goal

- 不重做整体视觉系统或引入新组件库。
- 不改变会话创建、选择、删除和终端管理业务逻辑。
- 不新增语言偏好持久化。

## Acceptance

- 顶部标题/导航/语言切换区域不再渲染。
- 会话管理面板底部左侧有“设置”入口，并与会话列表区域有分隔线。
- 设置入口点击后打开 reka-ui DropdownMenu。
- DropdownMenu 展示环境管理、终端管理、语言；语言下包含中文、English。
- 终端管理菜单项跳转 `/terminals` 路由。
- 环境管理入口可进入环境管理界面，支持 Windows/Cygwin/WSL 和 Cygwin 配置的管理入口。
- 主界面左右面板使用 reka-ui `Splitter` 实现拖拽调整宽度，不再依赖手写 pointer 事件。
- 当前页面仍可在会话视图和终端管理视图之间切换。
- `yarn typecheck`、`yarn lint` 通过。

## Risk

- 终端管理从顶栏迁移到底部设置菜单后，入口更隐蔽，需要保持菜单按钮明显可见。
- 如果终端管理页面复用侧边栏，主区域布局会与之前全宽终端管理不同，需要保持可读宽度。
