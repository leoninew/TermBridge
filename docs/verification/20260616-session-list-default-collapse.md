# 会话列表默认折叠与环境级展开控制验证

- Flow mode: light
- Stage: Verification
- Review status: Accepted
- Date: 2026-06-16

## What changed

1. `web/src/components/SessionList.vue`
   - 会话列表初始展开逻辑从“全部目录默认展开”调整为“有活动状态会话的目录默认展开；无活动状态会话的目录默认折叠”。
   - 活动状态判断基于会话 `status`，当前包含 `running`、`starting`、`disconnected`，避免刷新后没有 `activeSessionId` 时运行中会话目录不展开。
   - 将展开状态同步收敛到单个 `watch`，减少多个 watch 互相同步造成的状态复杂度。
   - 环境一级节点右侧增加批量展开/折叠按钮：展开使用 `ChevronsUpDown`，折叠使用 `ChevronsDownUp`。
   - 环境级按钮通过当前环境下 workspace 的展开状态推导，不额外维护独立环境展开状态。
   - 搜索时自动展开匹配目录，避免搜索结果被折叠隐藏。

2. `web/src/i18n/locales/zh-CN.json`
   - 新增环境级展开/折叠按钮中文文案。

3. `web/src/i18n/locales/en-US.json`
   - 新增环境级展开/折叠按钮英文文案。

4. `docs/requirement/20260616-session-list-default-collapse.md`
   - 记录 light requirement、用户反馈和最终默认展开规则。

## Acceptance

- [x] 页面初次加载时，没有活动状态会话的目录默认折叠。
- [x] 页面初次加载时，包含 `running` / `starting` / `disconnected` 会话的目录默认展开。
- [x] 刷新后即使尚未恢复 `activeSessionId`，`status: "running"` 会话所在目录仍会默认展开。
- [x] 每个环境一级节点右侧展示环境级展开/折叠 icon。
- [x] 展开操作使用 `ChevronsUpDown`，折叠操作使用 `ChevronsDownUp`。
- [x] 点击环境一级节点右侧 icon 后，仅展开或折叠该环境下所有目录节点，不影响其他环境。
- [x] 展开状态实现减少为单个主要 `watch`，避免多个 watch 互相同步的坏味道。
- [x] 会话选择、状态颜色、目录/会话操作入口保持在原组件结构内。
- [x] 空状态、加载态、无可用环境状态未改动。

## Commands

```text
npm --prefix web run typecheck
```

Result: passed.

```text
npm --prefix web run lint
```

Result: passed.

```text
npm --prefix web run format:check
```

Result: initial run reported `src/components/SessionList.vue` formatting differences. After running Prettier on `web/src/components/SessionList.vue`, the command passed.

```text
npm --prefix web exec prettier -- web/src/components/SessionList.vue --write
```

Result: formatted `web/src/components/SessionList.vue`.

## Remaining risk

1. 本轮验证以静态检查、类型检查和 diff 对照为主，未启动浏览器进行手动 UI 观察。
2. 当前工作区中 `web/src/components/SessionList.vue` 存在已暂存与未暂存的混合状态；提交前需要重新暂存该文件，确保 Prettier 后的最终内容被纳入提交。
3. 环境级批量展开/折叠基于现有 workspace 展开 key 推导；如果未来会话树增加更深层级，需要重新确认 `collectExpandableKeys` 的行为是否仍符合“二级节点”语义。
