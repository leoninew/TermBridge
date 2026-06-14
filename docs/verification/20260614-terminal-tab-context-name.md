# 终端 tab 上下文命名验证

- Flow mode: light
- Stage: Verification
- Review status: Accepted
- Date: 2026-06-14

## What changed

1. 将左侧会话列表原有的 workspace 目录节点显示名计算逻辑抽到 `web/src/sessionTreeLabels.ts`，供侧边栏和终端 tab 共用。
2. `SessionList.vue` 改为复用 `workspaceDisplayLabels`，保持目录节点原有去重显示规则不变。
3. `AppShell.vue` 基于当前 `sessionTree` 计算 `workspaceLabels`，并传给 `SessionTerminal.vue`。
4. `SessionTerminal.vue` 的 tab 文本从单独 `session.name` 改为 `workspaceLabel · session.name`；如果找不到 workspace label，则回退到原 `session.name`。
5. tab 的 `title` 仍保留完整 `item.workspace` 路径，tab 切换、关闭、拖动排序和创建入口未改变。

## Acceptance

- [x] 终端 tab 文本使用目录节点显示名 + 会话名称。
- [x] 目录节点显示名复用左侧会话列表的去重计算逻辑。
- [x] 同名 session 可通过 workspace label 在 tab 文本中区分。
- [x] tab `title` 仍保留完整 workspace 路径提示。
- [x] 未引入后端接口、持久化字段或 session 数据结构变更。
- [x] tab 关闭、选择、拖动排序和新建入口相关代码路径保持原有事件语义。

## Commands

1. `npm --prefix web run typecheck`
   - Result: passed.
2. `npm --prefix web run lint`
   - Result: passed.
3. `npm --prefix web run format:check`
   - Result: initially failed on `SessionList.vue` and `SessionTerminal.vue`; after running Prettier on the touched Vue files, passed.
4. `npm --prefix web run build`
   - Result: passed.
   - Notes: build emitted existing dependency/build warnings from `node_modules/@vueuse/core` pure annotations and a chunk-size warning; no build failure.

## Remaining risk

1. 未进行浏览器手工截图验证；当前验证覆盖 TypeScript、ESLint、Prettier 和 production build。
2. 当前工作区存在本需求外的 `pyproject.toml` version diff，未纳入本次需求实现范围。
