# Terminal-first 无界界面验证

Review status: Accepted

当前：轻量模式 / light，验证阶段 / Verification

## What changed

- 会话工作台外层从大卡片风格调整为更轻的 Terminal-first 工作台风格。
- Session sidebar 去掉大圆角、大白卡片、厚重阴影，改为侧栏背景和细分隔线。
- Terminal panel 去掉外层卡片边框和阴影，terminal viewport 更贴近主工作区。
- Home、Help、Environment、Shortcut 等路由页面的外层大卡片风格做了无界化处理。
- 新增浅色/暗色主题 store，并通过 `localStorage` 持久化。
- 左下角设置菜单新增主题切换入口。
- 设置菜单中的环境管理 icon 改为 `LaptopMinimal`。
- 主题选择通过 document root class/data attribute 生效，便于后续继续补齐暗色细节。

## Acceptance

- [x] 会话主界面不再呈现明显的大卡片边框和厚重阴影。
- [x] 左侧会话管理与右侧终端区域通过轻量分隔线和背景层次组织。
- [x] 右侧终端区域更贴近终端工作区心智。
- [x] 当前会话树、tab、创建会话、删除/停止等交互保留。
- [x] 左下角设置菜单提供浅色/暗色主题切换入口。
- [x] 主题选择刷新后保持。
- [x] 所有路由页面都做了外层无界/主题适配。
- [x] 前端 typecheck/lint 通过。

## Commands

- `yarn --cwd frontend typecheck`：通过。
- `yarn --cwd frontend lint`：通过。

## Remaining risk

- 暗色主题当前重点覆盖外壳和主要路由外层；部分表单控件、弹窗、子菜单的暗色细节后续仍可继续精修。
- 未做浏览器截图回归验证；本次通过静态检查和代码审视确认范围。
