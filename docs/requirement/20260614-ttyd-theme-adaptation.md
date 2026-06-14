# ttyd 适配暗色和浅色主题

- Flow mode: light
- Stage: Requirement
- Review status: Accepted
- Date: 2026-06-14

## Goal

让 TermBridge 内嵌的 ttyd 终端界面颜色与当前应用主题一致：

1. 应用处于暗色主题时，ttyd 终端背景、前景色、光标、选择色和 ANSI 调色板应接近 TermBridge 的 slate 暗色视觉，不再出现明显割裂的灰色背景。
2. 应用处于浅色主题时，ttyd 终端应使用可读的浅色背景、深色文字、清晰光标和选择色。
3. 主题适配应通过 ttyd 已支持的 `--client-option` / `-t` 入口传递 xterm.js `ITerminalOptions`，优先使用 `theme={...}`，避免维护自定义 `index.html`。
4. 终端 session 仍沿用当前 `/terminal/{session_id}/` iframe/proxy 入口，不改变 tmux、session 启停、认证和端口分配语义。

## Non-goal

1. 不新增用户自定义 ttyd 主题编辑器。
2. 不引入自定义 ttyd `index.html`，除非后续确认 `--client-option` 无法满足需求。
3. 不改变 ttyd 认证、绑定地址、端口分配、tmux attach command 或 terminal proxy 路由。
4. 不把每个 session 的主题持久化成独立业务数据。

## Acceptance

1. 后端启动 ttyd 时会传入适配 TermBridge 的 ttyd client options。
2. ttyd client options 至少覆盖 dark 和 light 两套 `theme` 配置。
3. 前端 iframe 的 `/terminal/{session_id}/` URL 能携带当前主题信息，或后端能以等效方式让 ttyd client 选择对应主题。
4. 切换应用主题后，新打开或刷新后的 ttyd terminal 使用匹配主题。
5. 现有 session 创建、启动、停止、tab 打开和 terminal proxy 行为不倒退。
6. 增加针对 ttyd 命令参数或 terminal URL 主题参数的测试覆盖。

## Risk

1. ttyd `--client-option theme=...` 是启动时传给 ttyd client 的默认配置；如果要让已加载 iframe 在不刷新情况下即时跟随主题，需要额外设计通信或重载策略，本次轻量需求先接受“刷新/新打开后生效”。
2. URL 参数覆盖能力需要结合 ttyd 实际行为验证；如果当前 ttyd 版本不支持通过 URL 切换 client option，则应退回为启动时传入固定默认主题，或后续再评估自定义 `index.html`。
3. JSON theme 字符串需要保持为单个命令参数，避免 shell 转义或空格导致 ttyd 解析失败。
4. 当前工作区已经存在独立拖动排序相关未提交改动；本需求应尽量限制在 ttyd 主题相关文件，避免进一步扩大提交边界。

## Notes

- 本机 `D:\ProgramFiles\Cygwin\usr\local\bin\ttyd.exe --help` 显示版本为 `1.7.7-40e79c7`，支持 `-t, --client-option` 和 `-I, --index`。
- ttyd 官方文档说明 `--client-option <key=value>` 可设置 xterm.js `ITerminalOptions`，包括 `theme={...}`；`--index` 可自定义 `index.html`，但本需求暂不采用。
- 2026-06-14: 用户要求使用轻量模式重新规划和实现 ttyd 对暗色、浅色主题的适配。
- 2026-06-14: 用户确认刚刚实现的 `TTYD_DARK_CLIENT_OPTIONS` 是有效的，因此暗色方案保留该配置作为基线，再补齐浅色主题适配。
