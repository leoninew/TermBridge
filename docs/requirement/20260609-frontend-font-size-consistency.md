# Frontend font size consistency

Review status: Accepted

Mode: 轻量模式 / light
Stage: 范围说明 / Scope note

## Goal

- 改进前端字号一致性，将标题类文字收敛到统一标题字号。
- 将非标题类文字收敛到统一正文字号，避免正文、按钮、表单、列表项、状态文本出现多套字号。
- 优先处理当前主要 Vue 组件中的 Tailwind 字号类，不引入复杂设计系统。

## Non-goal

- 不重做整体视觉设计、颜色、间距、圆角或布局。
- 不引入新的 UI 组件库或全局主题体系。
- 不修改业务逻辑、API、i18n 文案或后端代码。

## Acceptance

- 标题类元素统一使用同一标题字号，例如页面标题、面板标题、弹窗标题、分组标题。
- 非标题类元素统一使用同一正文字号，例如描述、按钮、表单 label、input、列表项、状态文本、辅助说明。
- 主要前端源码中不再保留用于普通 UI 文本的 `text-xl`、`text-base`、`text-xs` 混用。
- 改动范围限制在前端样式类和 SDD 文档。

## Risk

- 将 `text-xs` 提升为正文统一字号后，个别 badge、菜单 label 或紧凑列表可能更占空间；本轮接受该变化以换取字号一致性。
- Tailwind 默认字号仍可能通过未显式 `text-sm` 的元素继承或默认值出现；本轮优先统一显式文字样式，避免过度改动。
