# session-tree 快速刷新与批量状态检查
最后修改时间: 2026-06-16 22:29:54

- Flow mode: strict
- Stage: Requirement
- Review status: Accepted
- Date: 2026-06-16

## Background

当前会话页面刷新时，`GET /api/session-tree` 会在返回前逐个检查保存的会话对应的真实 tmux window 和 ttyd 状态。由于 Windows + Cygwin / WSL 下启动 shell 并执行 tmux 命令可能较慢，多会话场景下会出现页面初始加载时间明显变长的问题。

现有 UI 在等待会话树返回期间，左上角显示“正在加载会话”和 spinner，右侧终端区域显示“选择或新建一个会话查看终端”。这会带来两个问题：

1. 用户看到右侧空状态，容易误以为当前没有可用会话。
2. 在真实状态检查完成前，用户可能触发新建会话，与待恢复的已保存会话状态产生冲突或重复操作。

本需求希望把“快速读取记录”和“真实状态检查”拆开：先快速返回持久化记录用于恢复页面结构，再用批量 tmux 检查和必要的 ttyd 检查更新真实状态。

## Goals

1. 引入 `GET /api/session-tree?refresh=false`，用于立即返回持久化的 session tree 记录，不在返回前执行真实 tmux / ttyd 状态检查。
2. 页面初始加载时先调用 `GET /api/session-tree?refresh=false` 恢复已保存的会话树。
3. 在 `refresh=false` 的快速请求完成前，前端展示覆盖完整页面的加载遮挡层，避免用户点击“新建会话”等会修改会话状态的操作。
4. `refresh=false` 返回后，再触发真实状态刷新。
5. 真实状态刷新应批量检查 tmux 状态，而不是对每个 session 单独执行一次 tmux 命令。
6. tmux 批量检查使用 `tmux list-windows -a` 一次性获取所有运行中的 tmux window；该输出会包含目录和会话相关窗口，足以判断保存的 window 是否仍存在。
7. 只对 tmux window 仍存在的会话继续检查 ttyd 状态；tmux window 已不存在的会话无需检查 ttyd，可直接判定为停止类状态。
8. 最终 UI 应在状态刷新完成后更新 session tree，使 `running` / `disconnected` / `stopped` 状态反映真实结果。

## Non-goals

1. 不改变创建会话、启动会话、停止会话、删除会话的业务语义。
2. 不改变 tmux session/window 的命名规则。
3. 不改变 ttyd proxy、terminal iframe、WebSocket proxy 或认证机制。
4. 不引入后台 daemon 或长期轮询机制持续维护状态；本需求只处理页面刷新/显式加载时的快速恢复和状态刷新。
5. 不要求本次实现持久化状态检查 TTL 缓存，除非后续 Spec / Plan 阶段确认其为必要的最小实现。
6. 不要求新增 `checking` 或 `unknown` 会话状态；如后续设计发现必须新增，需要在 Spec 阶段明确说明兼容影响。

## User scenarios

1. 用户刷新 session 页面，系统应先用保存的记录快速恢复左侧会话树，而不是等待所有 tmux / ttyd 检查完成后才展示。
2. 用户刷新 session 页面时，在快速记录返回前看到覆盖完整页面的遮挡式加载状态，无法误点新建会话。
3. 快速记录返回后，用户可以看到已有会话结构；随后系统更新每个会话的真实状态。
4. 某个保存会话的 tmux window 已不存在时，状态刷新不再检查该会话的 ttyd 端口，直接将其视为停止类状态。
5. 某个保存会话的 tmux window 仍存在但 ttyd 不可用时，状态刷新应将其识别为 `disconnected`。
6. 某个保存会话的 tmux window 仍存在且 ttyd 可用时，状态刷新应将其识别为 `running`。

## Acceptance criteria

1. API 支持 `GET /api/session-tree?refresh=false`。
2. `refresh=false` 响应应直接基于持久化记录构建 session tree，不在返回前调用真实 tmux window 检查或 ttyd port 检查。
3. `GET /api/session-tree` 无 query 时保持现有兼容行为：返回经过真实状态刷新后的结果。
4. 真实状态刷新使用 `GET /api/session-tree`，不新增单独状态刷新 endpoint。
5. 前端页面初始加载时应先请求 `refresh=false` 快速恢复记录。
6. 在 `refresh=false` 请求完成前，前端应显示覆盖完整页面的加载遮挡层，阻止用户触发新建会话等状态写操作。
7. `refresh=false` 请求完成后，前端应触发 `GET /api/session-tree` 真实状态刷新，并用刷新结果更新 session tree。
8. 真实状态刷新应使用 `tmux list-windows -a` 批量 tmux window 查询，避免按 session 数量线性执行 `tmux display-message` / `tmux has-session` 等单条检查命令。
9. 批量 tmux 查询结果至少能判断保存的 `tmux_window_id` 是否仍存在。
10. 对 tmux window 不存在的 session，不执行 ttyd port 检查。
11. 对 tmux window 存在的 session，继续检查 ttyd 状态，并按现有语义区分 `running` 与 `disconnected`。
12. 状态刷新完成后，前端应展示真实状态，不应长期停留在快速记录中的旧状态。
13. 如果真实状态刷新失败但快速记录已加载，页面应保留快速记录视图，并以 toast 或非阻塞错误提示告知用户状态刷新失败。
14. 增加或更新后端测试覆盖：`refresh=false` 不执行真实检查、批量 tmux 结果映射、tmux window 不存在时跳过 ttyd 检查。
15. 增加或更新前端测试或通过项目现有检查覆盖：初始遮挡、快速加载后触发状态刷新、状态刷新失败不清空已加载记录。
16. Spec 阶段应列出现有无 query 调用 `/api/session-tree` 的位置，并明确哪些保持无 query、哪些改为显式 `refresh=false`。

## Open questions

暂无阻塞进入 Spec 的问题。以下事项已由用户确认：

1. `GET /api/session-tree` 默认仍执行真实刷新，前端快速恢复时显式使用 `refresh=false`。
2. 真实状态刷新继续使用无 query 的 `GET /api/session-tree`。
3. 批量 tmux 检查使用 `tmux list-windows -a`；该命令本身就是批量检查，会返回目录和会话相关窗口。
4. 加载遮挡层覆盖完整页面。

## Decisions

- 本次采用 strict / 严格模式，需要经过 Requirement、Spec、Plan、Implementation、Verification 阶段。
- 快速恢复接口使用用户指定的 `GET /api/session-tree?refresh=false`。
- `GET /api/session-tree` 无 query 时保持兼容，仍返回经过真实状态刷新的结果。
- 真实状态刷新不新增 endpoint，继续使用 `GET /api/session-tree`。
- 真实状态刷新顺序为：先通过 `tmux list-windows -a` 批量获取 tmux windows，再对 window 仍存在的会话检查 ttyd。
- tmux window 不存在的会话不再检查 ttyd。
- `refresh=false` 返回前，前端需要覆盖完整页面的加载遮挡层，避免用户新建会话或触发其他会话写操作。

## Risks and assumptions

1. 假设持久化 session tree 记录可以安全用于初始 UI 恢复，即使其中状态字段可能是旧值。
2. 快速返回旧状态后再异步刷新真实状态，可能出现短时间内 UI 状态跳变；需要通过文案或 loading 表达降低困惑。
3. 批量 tmux 查询在不同 host（Cygwin、WSL、Linux）下的可用性和性能可能不同，需要在 Spec / Plan 阶段确认命令封装边界。
4. 如果 `tmux list-windows -a` 本身超时或失败，应避免导致快速记录视图被清空。
5. 覆盖完整页面的遮挡层会短暂阻止所有操作；需要确保它只持续到快速记录返回或失败，而不是持续到真实状态刷新完成。

## User review notes

- 2026-06-16：用户确认进入 Spec，并明确四项决策：默认 `GET /api/session-tree` 仍真实刷新；真实状态刷新使用无 query 的 `GET /api/session-tree`；批量 tmux 检查使用 `tmux list-windows -a`；加载遮挡层覆盖完整页面。