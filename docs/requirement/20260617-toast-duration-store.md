# Toast 时长由 store 兜底
最后修改时间: 2026-06-17 11:12:50

Review status: Accepted

## Background

当前 toast 展示依赖 `ToastProvider` 的默认 `duration` 触发关闭。用户观察到“会话已启动”等成功提示长时间未关闭，需要将自动关闭时长控制下沉到 `toast` store，避免完全依赖 UI 组件内部计时行为。

## Goal

- `toast.show()` 支持可选时长参数，用于单次 toast 覆盖默认展示时长。
- `toast` store 提供统一默认时长；调用方未提供时长时，使用 store 默认时长生效。
- 默认行为保持现有预期：普通 toast 自动延时关闭。
- 清理所有 `toast.show()` 调用点，不在业务调用处显式传递时长参数，避免业务层分散控制默认时长。

## Non-goal

- 不调整 toast 的视觉样式、位置、颜色、动画和文案。
- 不重构所有通知组件或替换 Reka UI toast 组件。
- 不改变现有成功/错误 toast 的业务触发时机。
- 不引入按业务场景区分的多套默认时长策略。

## User scenarios

- 用户启动会话后看到“会话已启动”提示，该提示应在默认时长后自动关闭。
- 未来如果某个调用确实需要特殊展示时长，可以通过 `toast.show()` 的可选时长能力单独覆盖。
- 普通业务调用只需要 `toast.show({ title, variant })`，默认时长由 store 统一管理。

## Acceptance

- `web/src/stores/toast.ts` 中的 `toast.show()` 类型支持可选时长字段。
- store 内部定义默认 toast 展示时长；调用未传入时长时使用该默认值。
- store 负责根据时长触发关闭/移除，确保 toast 不会因为 Reka UI 的计时暂停或事件未触发而长期保留。
- 所有现有 `toast.show()` 调用点不传递时长参数。
- 保留手动关闭能力，点击关闭按钮仍能关闭并移除 toast。
- 多个 toast 并发出现时，各自的关闭计时互不干扰。
- 如组件层仍保留 Reka UI `duration` 配置，其行为不得与 store 默认时长产生冲突；优先以 store 控制为准。

## Open questions

暂无需要用户确认的未决事项。

## Decisions

- 使用 light / 轻量模式推进。
- 默认时长由 `toast` store 集中定义和执行。
- `toast.show()` 保留可选时长扩展能力，但本次所有现有调用点不显式传递时长。
- store 默认时长默认沿用当前 UI 层配置意图：约 3000ms。

## Risk

- 如果 store 级计时器绕过 Reka UI 的 hover/focus/window blur 暂停语义，toast 在用户悬停或窗口失焦期间也可能按 store 时长关闭；本需求优先解决长期不关闭问题。
- 需要注意关闭动画和移除延迟配合，避免刚设置关闭状态就立即从列表删除导致动画消失或组件状态不一致。
- 需要清理定时器，避免 toast 手动关闭后残留计时器重复操作。