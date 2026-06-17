# Toast 时长由 store 兜底验证
最后修改时间: 2026-06-17 11:18:03

Review status: Draft

## Requirement alignment

按 `docs/requirement/20260617-toast-duration-store.md` 核对：

- 已实现 `toast.show()` 的可选 `duration` 参数。
- 已在 `toast` store 内提供默认展示时长，调用未传 `duration` 时使用默认时长。
- 已将自动关闭控制下沉到 store，避免完全依赖 Reka UI 的内部计时。
- 已确认现有 `toast.show()` 调用点没有传入 `duration` 参数。
- 已保留手动关闭入口，关闭后仍经过短延迟移除，以保留动画窗口。
- 多 toast 使用基于 id 的独立计时器，互不复用全局单一计时器。

## Spec alignment

不适用。当前任务使用 light / 轻量模式，没有单独创建 spec / 规格文档。

## Plan alignment

不适用。当前任务使用 light / 轻量模式，直接依据 requirement / 需求实现。

## Actual diff summary

实际改动文件：

- `web/src/stores/toast.ts`
  - 新增 store 默认时长 `DEFAULT_TOAST_DURATION_MS = 5000`。
  - 新增移除延迟常量 `TOAST_REMOVE_DELAY_MS = 200`。
  - `ToastOptions` 新增 `duration?: number`。
  - 新增每个 toast 独立的关闭计时器和移除计时器 Map。
  - `show()` 创建 toast 后按 `options.duration ?? DEFAULT_TOAST_DURATION_MS` 调度关闭。
  - `updateOpen()` 在关闭时清理关闭计时器并调度延迟移除。
- `web/src/components/AppToast.vue`
  - 将 Reka UI `ToastProvider` 的 `duration` 从 `5000` 改为 `Number.POSITIVE_INFINITY` 常量，避免组件层计时器与 store 计时器竞争。
- `docs/requirement/20260617-toast-duration-store.md`
  - Requirement 状态已从 `Draft` 更新为 `Accepted`。

## Expected vs actual changed files

预期改动：

- toast store：增加默认时长、可选时长、计时器兜底关闭。
- toast component：避免 Reka UI 继续主导自动关闭。
- requirement 文档：按 SpecFlow 接受需求。
- verification 文档：记录本次验证。

实际改动与预期一致。未发现扩大到无关业务模块、后端接口或样式系统的改动。

## Acceptance checklist

- [x] `web/src/stores/toast.ts` 中的 `toast.show()` 类型支持可选时长字段。
- [x] store 内部定义默认 toast 展示时长；调用未传入时长时使用该默认值。
- [x] store 负责根据时长触发关闭/移除，降低 Reka UI 内部计时失效导致长期保留的风险。
- [x] 所有现有 `toast.show()` 调用点不传递时长参数。
- [x] 保留手动关闭能力，点击关闭按钮仍会调用 `toast.updateOpen(item.id, false)`。
- [x] 多个 toast 使用独立 id 和独立计时器，关闭计时互不干扰。
- [x] Reka UI `duration` 已改为无限时长，组件层不再与 store 默认时长竞争。

## Command results

### `npm --prefix web run lint`

结果：通过。

输出摘要：

```text
> lint
> eslint .
```

### `npm --prefix web run build`

结果：通过。

输出摘要：

```text
> build
> vue-tsc --noEmit && vite build
✓ 2391 modules transformed.
✓ built in 428ms
```

构建过程中出现既有依赖/打包警告：

- `node_modules/@vueuse/core/dist/index.js` 中的 `/* #__PURE__ */` 注释位置被 Rolldown 忽略。
- 部分 chunk 超过 500 kB。

这些警告来自依赖或构建体积提示，不是本次 toast store 改动直接引入的类型错误或构建失败。

## Missed or expanded scope

- 未做浏览器手动交互验证；当前验证覆盖静态 lint、类型检查和生产构建。
- 未修改任何 `toast.show()` 调用点，因为检查结果显示当前调用点均未传入 `duration` 参数。
- 未变更 toast 样式、文案、触发业务逻辑或后端代码。

## Risks

- store 级计时器不会继承 Reka UI 原本的 hover/focus/window blur 暂停语义；这是本需求为确保 toast 能按默认时长关闭而接受的行为取舍。
- 如果未来需要某些 toast 悬停暂停，需要在 store 层显式设计暂停/恢复机制，而不是依赖 Reka UI 的 `duration`。

## Incomplete items

- 无代码层面的未完成项。
- 可选后续项：如需更强信心，可运行应用并在浏览器中观察“会话已启动”toast 是否在约 3 秒后自动消失。

## Conclusion

本次实现与 light / 轻量模式 requirement 对齐。前端 lint 和 build 均通过；构建仅有依赖 pure annotation 与 chunk size 警告。当前代码可进入用户验收。