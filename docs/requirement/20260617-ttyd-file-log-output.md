# ttyd file 模式日志输出修复需求
最后修改时间: 2026-06-17 10:35:00

- Flow mode: light
- Stage: Requirement
- Review status: Accepted
- Date: 2026-06-17

## Background

当前 `.env` 中设置 `TERMBRIDGE_TTYD_LOG_MODE=file` 后，TermBridge 会在启动受管理 ttyd session 时创建日志文件，但路径和内容不符合当前排查预期：

1. 现有实现把 file 模式日志写入 `settings.state_dir / "logs" / "ttyd" / <session-id>.log`。在本项目默认配置下，对应 `.termbridge/logs/ttyd/<session-id>.log`。
2. 用户预期 file 模式写入项目根目录下的 `logs/ttyd/<session-id>.log`，而不是 `.termbridge/logs/ttyd`。
3. 当前 `.termbridge/logs/ttyd` 下的日志文件会被创建，但实际为 0 字节。console 模式能看到 ttyd 输出，因此 file 模式空文件不符合“把 ttyd stdout/stderr 写入文件”的排查预期。
4. 当前 file 模式只把 ttyd 子进程 stdout/stderr 重定向到文件，没有主动写入 TermBridge 侧的启动诊断 header；如果 ttyd 自身没有输出或输出被缓冲，文件会保持空白，难以判断 file 模式是否生效。

## Goal

1. `TERMBRIDGE_TTYD_LOG_MODE=file` 时，受管理 ttyd session 的日志文件应按运行形态选择默认位置：开发环境及 `pip install -e .` editable 模式使用项目目录 `logs/ttyd/<session-id>.log`；wheel 包或普通安装后运行使用用户目录 `.termbridge/logs/ttyd/<session-id>.log`。
2. 是否新增 `TERMBRIDGE_TTYD_LOG_DIR` 不是本次关键点；如实现上需要可新增，但默认行为必须满足上述开发/安装形态区分。
3. file 模式创建日志文件时，TermBridge 应主动写入一段启动诊断 header，避免日志文件为空且无法判断是否生效。
4. ttyd 子进程 stdout/stderr 仍应继续追加到同一个 session 日志文件；允许 ttyd 自身输出因运行时缓冲而延迟落盘。
5. console 模式语义保持不变：ttyd stdout/stderr 继续继承父进程控制台，用于需要实时上屏的交互式排查。
6. none 模式语义保持不变：ttyd stdout/stderr 继续丢弃。
7. 更新相关测试和文档，使日志路径与 file 模式行为清晰可查。

## Non-goal

1. 不实现 UI 日志查看器。
2. 不实现日志轮转、日志清理或日志下载。
3. 不把 ttyd 输出转发到 Python logging。
4. 不引入后台 reader 线程或日志采集器；file 模式定位为持久化诊断日志，不保证像 console 一样实时落盘。
5. 不改变 ttyd 启动命令、端口分配、tmux session/window 生命周期。
6. 不改变 console / none / file 模式的 ttyd verbose/debug 参数；file 模式不依赖 ttyd `--debug`。
7. 不改变 TermBridge 主应用日志的格式或输出位置。

## User scenarios

1. 开发者在源码 checkout 或 `pip install -e .` editable 模式下设置 `TERMBRIDGE_TTYD_LOG_MODE=file` 后启动一个 session，可以在项目目录 `logs/ttyd/<session-id>.log` 找到对应日志文件。
2. 用户通过 wheel 包或普通安装方式运行 TermBridge 时，file 模式日志默认写入用户目录 `.termbridge/logs/ttyd/<session-id>.log`。
3. 即使 ttyd 自身暂时没有 stdout/stderr 输出，日志文件中也至少包含 TermBridge 写入的启动诊断 header，例如 session id、pid、cwd、命令、log mode 等。
4. 如果 ttyd 后续向 stdout/stderr 输出内容，该内容应追加到同一个日志文件。
5. 开发者切换到 `console` 模式时，ttyd 输出仍直接进入 TermBridge 后端控制台。
6. 开发者切换到 `none` 模式时，不产生 ttyd stdout/stderr 输出文件，也不污染控制台。

## Acceptance

1. `_ttyd_log_options()` 或等价逻辑在 file 模式下按运行形态解析日志目录：源码 checkout / editable 模式返回项目目录 `logs/ttyd/<session-id>.log`；wheel / 普通安装后运行返回用户目录 `.termbridge/logs/ttyd/<session-id>.log`。
2. 如果新增 `TERMBRIDGE_TTYD_LOG_DIR`，该配置可以覆盖默认目录；如果不新增配置，也必须满足验收 1 的默认行为。
3. file 模式启动 ttyd 时，日志文件会被创建并写入非空 header。
4. header 至少包含 session id、cwd、启动命令或等价诊断信息；如果 pid 只能在 `Popen` 后获得，则 pid 可在进程启动后补写。
5. stdout/stderr 重定向到日志文件的行为保留，且不破坏当前子进程启动；ttyd 自身输出允许因缓冲延迟写入文件。
6. `console` 和 `none` 模式测试仍覆盖原有行为。
7. 更新 `docs/requirement/20260611-ttyd-log-handling.md`、`docs/verification/20260611-ttyd-log-handling.md` 或新增说明，使 file 模式路径和 header 行为与实现一致。
8. 增加或更新单元测试覆盖 file 模式日志路径选择和 header 写入行为。
9. 相关后端测试通过。

## Open questions

1. 是否新增独立配置项 `TERMBRIDGE_TTYD_LOG_DIR` 暂不强制；实现可按最小改动选择。但默认路径必须区分源码 / editable 模式和 wheel / 普通安装后运行模式。

## Decisions

1. 用户确认：console 模式 ttyd 输出进入控制台符合现有语义。
2. 用户指出：file 模式日志文件为空不符合预期，需要修复。
3. 用户采纳 SpecFlow 轻量模式推进本修复。
4. 用户确认：是否新增 `TERMBRIDGE_TTYD_LOG_DIR` 不重要；关键是开发环境及 `pip install -e .` editable 模式使用项目目录 `logs`，wheel 包及安装后使用用户目录 `.termbridge/logs`。
5. 用户确认：header / 日志中包含完整 ttyd command 及本地 credential 无问题，这是本地凭据。
6. 用户确认：console 模式当前没有传 `--debug`；file 模式单独传 `--debug` 不是语义等价的最终方案，应移除。
7. 用户观察到 ttyd 输出会在一段时间后刷新到 file 日志，确认根因是 ttyd/libwebsockets 对普通文件输出存在缓冲。
8. 用户采纳最终策略：file 模式作为持久化诊断日志，不保证实时；需要实时输出时使用 console 模式。暂不引入 pipe reader、`stdbuf` 或 ttyd `--debug`。

## Risk

1. ttyd/libwebsockets 对普通文件 stdout/stderr 可能做块缓冲；header 可以保证文件非空，但 ttyd 自身输出可能延迟刷入文件。需要实时上屏时使用 console 模式。
2. header 写入完整命令会包含 `--credential` 参数；用户已确认这是本地凭据，可以接受。
3. 开发 / editable 模式下将日志从 `.termbridge/logs` 改到 `logs/ttyd` 会改变既有文档中的路径；依赖旧路径排查的用户需要迁移认知。

## User review notes

暂无。
