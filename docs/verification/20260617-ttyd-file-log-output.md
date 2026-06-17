# ttyd file 模式日志输出修复验证
最后修改时间: 2026-06-17 10:53:27

- Flow mode: light
- Stage: Verification
- Review status: Draft
- Date: 2026-06-17

## Requirement alignment

对照 `docs/requirement/20260617-ttyd-file-log-output.md`：

1. file 模式日志目录按运行形态选择：已实现 `Settings.ttyd_logs_dir`。
   - 源码 checkout / `pip install -e .` editable 模式：`<project_root>/logs/ttyd`。
   - wheel / 普通安装后运行：`settings.state_dir / "logs" / "ttyd"`，默认对应用户目录 `.termbridge/logs/ttyd`。
2. file 模式启动 ttyd 时写入非空 header：已在 `TtydProcessAdapter.start()` 中打开日志文件后立即写入并 flush header。
3. header 包含诊断信息：timestamp、session_id、cwd、command、pid pending 标记，并在 `Popen` 成功后补写实际 pid。
4. ttyd stdout/stderr 继续写入同一日志文件：file 模式仍将 `stdout` / `stderr` 指向同一个打开的日志文件。
5. console / none 语义保持不变：console 仍继承父进程输出，none 仍使用 `subprocess.DEVNULL`。
6. 不引入 pipe reader、`stdbuf` 或 ttyd `--debug`：最终实现没有新增后台日志采集线程，也没有修改 ttyd debug 参数。
7. 文档已更新：`.env.sample`、历史 ttyd log requirement / verification 和本需求文档均说明路径和 buffering 行为。

结论：实现与需求对齐。

## Spec / Plan alignment

轻量模式 / light 未创建独立 spec 或 plan。实现按 requirement / 需求直接核对。

## Actual diff summary

主体实现已在最近提交 `d6a7426 fix(ttyd): write startup header and fix log path for file mode` 中完成，包含：

- `.env.sample`
  - 更新 file 模式日志路径说明，区分源码/editable 与 wheel/普通安装。
- `.gitignore`
  - 忽略项目目录 `logs`，避免开发模式 ttyd 日志进入版本控制。
- `docs/requirement/20260611-ttyd-log-handling.md`
  - 补充 file 模式路径选择和启动 header 行为。
- `docs/requirement/20260617-ttyd-file-log-output.md`
  - 新增本次轻量需求文档。
- `docs/verification/20260611-ttyd-log-handling.md`
  - 更新历史验证说明，记录 file 模式 header 和 stdout/stderr buffering 风险。
- `src/termbridge/settings.py`
  - 新增 `editable_project_root()`。
  - 新增 `Settings.ttyd_logs_dir`。
- `src/termbridge/services.py`
  - file 模式日志路径改为 `settings.ttyd_logs_dir / <session-id>.log`。
- `src/termbridge/process.py`
  - file 模式启动时写入 header 并 flush。
  - `Popen` 成功后写入 ttyd pid 并 flush。
- `tests/test_process.py`
  - 新增 header 写入测试。
- `tests/test_settings.py`
  - 增加 `ttyd_logs_dir` 路径选择测试。
- `tests/test_services.py`
  - 更新 file 模式日志路径断言。
  - 明确 console/default 和 file 模式均不注入 `--debug`。

验证阶段后当前工作区还有 3 个未提交微调：

- `docs/requirement/20260617-ttyd-file-log-output.md`
  - 修正 Non-goal 编号。
- `src/termbridge/process.py`
  - 按 ruff 建议移除不必要的 `encode("utf-8")` 显式参数。
- `tests/test_settings.py`
  - 为既有 monkeypatch fixture 参数补充 `MonkeyPatch` 类型标注，使 changed-file mypy 通过。

## Expected vs actual changed files

| 文件 | 预期 | 实际 | 说明 |
| --- | --- | --- | --- |
| `.env.sample` | 是 | 是 | 更新 file 模式路径说明 |
| `.gitignore` | 是 | 是 | 忽略开发模式 `logs` 目录 |
| `src/termbridge/settings.py` | 是 | 是 | 增加运行形态相关 log dir 解析 |
| `src/termbridge/services.py` | 是 | 是 | file 模式使用 `settings.ttyd_logs_dir` |
| `src/termbridge/process.py` | 是 | 是 | 写入启动 header 和 pid |
| `tests/test_process.py` | 是 | 是 | 覆盖 header 写入 |
| `tests/test_settings.py` | 是 | 是 | 覆盖路径选择；另有类型标注微调 |
| `tests/test_services.py` | 是 | 是 | 覆盖 file 路径和不加 `--debug` |
| `docs/requirement/20260617-ttyd-file-log-output.md` | 是 | 是 | 本次需求文档 |
| `docs/requirement/20260611-ttyd-log-handling.md` | 是 | 是 | 更新历史需求说明 |
| `docs/verification/20260611-ttyd-log-handling.md` | 是 | 是 | 更新历史验证说明 |
| `docs/verification/20260617-ttyd-file-log-output.md` | 是 | 是 | 本验证文档 |

未发现与需求无关的产品代码改动。

## Acceptance checklist

1. [x] file 模式按运行形态解析日志目录。
2. [x] 未新增 `TERMBRIDGE_TTYD_LOG_DIR`，但默认行为满足源码/editable 与安装态区分。
3. [x] file 模式启动 ttyd 时创建并写入非空 header。
4. [x] header 包含 session id、cwd、启动命令，并在启动后补写 pid。
5. [x] ttyd stdout/stderr 仍写入同一日志文件；允许 ttyd 自身输出因缓冲延迟落盘。
6. [x] console 和 none 模式语义保持不变。
7. [x] 文档已更新路径、header 和 buffering 说明。
8. [x] 单元测试覆盖 file 模式路径选择和 header 写入。
9. [x] 相关后端测试通过。

## Commands

### 测试

```text
uv run pytest tests/test_process.py tests/test_settings.py tests/test_services.py
```

结果：通过。

```text
54 passed
```

### Ruff

```text
uv run ruff check src/termbridge/process.py src/termbridge/services.py src/termbridge/settings.py tests/test_process.py tests/test_settings.py tests/test_services.py
```

结果：通过。

```text
All checks passed!
```

### Mypy

```text
uv run mypy src tests/test_process.py tests/test_settings.py tests/test_services.py
```

结果：通过。

```text
Success: no issues found in 18 source files
```

### 手工 / 运行时观察

- 用户确认开发模式下已创建 `D:\SourceCodes\mywork\TermBridge\logs\ttyd\sess_...log`。
- 用户观察到 ttyd 自身输出会在一段时间后刷新到 file 日志，支持“普通文件输出存在缓冲，file 模式不保证实时”的最终策略。

## Missed or expanded scope

- 未新增 UI 日志查看器，符合 non-goal。
- 未实现日志轮转 / 清理 / 下载，符合 non-goal。
- 未引入 pipe reader / 日志采集器，符合最终决策。
- 未加入 ttyd `--debug` 或 `stdbuf`，符合最终决策。
- 未新增 `TERMBRIDGE_TTYD_LOG_DIR`，符合“可不新增，默认行为关键”的决策。

## Risks

1. ttyd/libwebsockets 对普通文件 stdout/stderr 可能做块缓冲，因此 file 模式不保证实时落盘；需要实时上屏时应使用 console 模式。
2. header 中包含完整 ttyd command，可能包含本地 credential；用户已确认这是本地凭据，可接受。
3. 开发 / editable 模式下日志目录从 `.termbridge/logs` 迁移到 `logs/ttyd`，旧路径使用者需要调整认知。
4. 当前验证未构建 wheel 包做安装态端到端验证；安装态路径通过 `Settings.ttyd_logs_dir` 分支逻辑和单元测试间接覆盖。

## Incomplete items

- 当前工作区仍有验证阶段产生的 3 个未提交微调文件：`docs/requirement/20260617-ttyd-file-log-output.md`、`src/termbridge/process.py`、`tests/test_settings.py`。
- 本验证文档为新文件，尚未提交。

## Conclusion

本次 ttyd file 模式日志修复满足轻量需求：开发 / editable 模式日志写入项目 `logs/ttyd`，安装态使用 `.termbridge/logs/ttyd`；file 模式会立即写入启动 header，避免空文件误导；console / none 语义保持不变；file 模式明确定位为持久化诊断日志，不保证 ttyd 自身输出实时落盘。

Verification 结论：可交付。建议将当前验证阶段微调和本验证文档纳入后续提交或按需合并到已提交变更。
