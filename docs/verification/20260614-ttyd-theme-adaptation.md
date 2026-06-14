# ttyd 适配暗色和浅色主题验证

- Flow mode: light
- Stage: Verification
- Review status: Draft
- Date: 2026-06-14

## What changed

- 新增 `docs/requirement/20260614-ttyd-theme-adaptation.md`，按轻量模式记录 ttyd 主题适配需求。
- 新增 `src/termbridge/ttyd.py`，集中维护 ttyd 默认主题、dark/light 两套 xterm theme 和字体、字号、光标闪烁等通用 client options。
- 用户已确认早先暗色配置在实际 ttyd 页面中有效，因此将该暗色调色板保留为集中主题表里的 `dark` 默认主题。
- 在 `src/termbridge/services.py` 中改为通过 `ttyd_client_options()` 生成 ttyd 启动参数，默认不传主题时使用 `dark`。
- 在 `web/src/components/SessionTerminal.vue` 中只传当前主题名 `theme=dark|light`，不再维护任何 xterm 颜色表。
- 在 `src/termbridge/api.py` 中由 terminal proxy 将 `theme=dark|light` 规范化为 ttyd 需要的 `theme={...json...}`；未知主题值保持原样转发，兼容 ttyd 原有 client option query。
- 更新 `tests/test_services.py` 和 `tests/test_api.py`，覆盖默认 ttyd client options 以及 proxy 对 `theme=light` 的集中映射。

## Acceptance

| Acceptance | Result | Notes |
| --- | --- | --- |
| 后端启动 ttyd 时传入适配 TermBridge 的 client options | Pass | `_build_ttyd_command()` 会追加 `ttyd_client_options()` 生成的默认 options。 |
| 至少覆盖 dark 和 light 两套 theme | Pass | `src/termbridge/ttyd.py` 集中维护 dark/light 主题表，默认主题为 dark。 |
| iframe URL 能携带当前主题信息 | Pass | `terminalUrl(item.url)` 使用 `URLSearchParams` 写入 `theme=dark|light`。 |
| 切换主题后新打开或刷新后的 terminal 使用匹配主题 | Mostly Pass | 代码会根据当前 theme 生成 iframe src，proxy 统一映射为 ttyd theme JSON；仍建议手动确认已加载 ttyd iframe 在主题切换时的重载体验。 |
| session 启停、proxy、认证、端口语义不变 | Pass | 未改动相关服务逻辑，仅追加 ttyd client option 和 query 规范化。 |
| 增加测试覆盖 | Pass | `tests/test_services.py` 覆盖默认 client options；`tests/test_api.py` 覆盖 `theme=light` proxy 映射。 |

## Commands

已执行：

```bash
cd /d/SourceCodes/mywork/term-bridge && uv run ruff check src/termbridge/api.py src/termbridge/services.py src/termbridge/ttyd.py tests/test_api.py tests/test_services.py && uv run mypy src/termbridge/api.py src/termbridge/services.py src/termbridge/ttyd.py tests/test_api.py tests/test_services.py
uv run pytest tests/test_services.py tests/test_api.py
cd /d/SourceCodes/mywork/term-bridge/web && yarn lint && yarn typecheck
```

结果：

```text
ruff: passed
mypy: passed
pytest tests/test_services.py tests/test_api.py: 43 passed, 1 warning
frontend lint: passed
frontend typecheck: passed
```

## Remaining risk

- 未执行浏览器手动验证浅色主题 ttyd 页面；暗色主题已由用户反馈确认早先调色板有效，并已集中迁移到 `src/termbridge/ttyd.py`。
- 当前方案仍依赖 ttyd 1.7.7 对 URL query client option 覆盖的支持；TermBridge proxy 已将 `theme=dark|light` 统一映射为 ttyd 需要的 JSON theme 参数。
- 已加载的 iframe 在主题切换时可能重新加载 terminal 页面；若后续要求无刷新即时切换，需要额外设计 iframe 内通信或自定义 ttyd 前端。
