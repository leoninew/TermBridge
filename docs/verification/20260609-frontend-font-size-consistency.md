# web font size consistency verification

Review status: Accepted

Mode: 轻量模式 / light
Stage: 验证 / Verification

## What changed

- 按用户确认的“机械收敛，不抽太多新类”方向，直接统一 Tailwind 字号类。
- 标题类文字统一到 `text-lg font-semibold`：
  - `web/src/components/AppStatus.vue`
  - `web/src/components/EnvironmentManagement.vue`
- 非标题类显式小字号统一到 `text-sm`：
  - `web/src/components/WorkspaceBrowser.vue`
  - `web/src/components/SessionCard.vue`
  - `web/src/components/SessionList.vue`
  - `web/src/components/ShortcutManagement.vue`
  - `web/src/components/EnvironmentManagement.vue`
- 补齐隐式默认字号问题：
  - `web/src/App.vue` 的 `<main>` 增加 `text-sm`，作为普通文本兜底，避免未显式字号的内容回退到浏览器默认 16px。
  - `web/src/components/SessionList.vue` 的 loading/error/empty 文本补 `text-sm`，其中 “暂无会话，先创建一个。” 现在是 `text-sm`。
  - Portal 弹窗内容容器补 `text-sm`，避免挂到 `body` 后丢失 `main` 的字号继承。
- 未抽取新的全局语义类，避免引入额外样式体系。

## Acceptance

- [x] 标题类元素统一使用 `text-lg`。
- [x] 非标题类元素统一使用 `text-sm`。
- [x] “暂无会话，先创建一个。” 已从隐式默认字号修正为 `text-sm`。
- [x] `web/src` 中未发现普通 UI 文本继续使用 `text-xs`、`text-base`、`text-xl`、`text-2xl` 或任意值字号类。
- [x] 改动范围限制在前端样式类和 SDD 文档，没有修改业务逻辑、API、i18n 文案或后端代码。

## Commands

- `npm --prefix web run build`
  - 结果：通过。
  - 备注：构建过程中出现来自 `node_modules/@vueuse/core/dist/index.js` 的 Rolldown `INVALID_ANNOTATION` warning，构建最终成功；该 warning 与本次字号改动无关。
- `npm --prefix web run lint`
  - 结果：通过。
- 搜索检查：`web/src` 中未匹配 `text-(xs|base|xl|2xl|\[[^\]]+\])`。

## Remaining risk

- `text-xs` 统一提升到 `text-sm` 后，badge、菜单分组 label、工作区浏览器条目等紧凑元素会稍微变大；这是本轮为了统一字号接受的视觉变化。
- 已补 `main` 级别 `text-sm` 兜底，但个别第三方组件内部默认样式仍可能不完全受 Tailwind class 控制。
- 本轮未做浏览器截图或人工视觉回归，只完成代码层收敛和构建/lint 验证。
