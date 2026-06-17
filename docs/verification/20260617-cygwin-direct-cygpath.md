# Cygwin workspace 直接 cygpath 转换验证
最后修改时间: 2026-06-17 13:36:29

## Review status

Accepted

## Requirement alignment

依据 `docs/requirement/20260617-cygwin-direct-cygpath.md` 核对。

- 已将 Windows/Cygwin workspace path conversion 从 `bash -lc "cygpath -u ..."` 改为直接调用 `cygpath.exe -u <workspace>`。
- 已从 configured Cygwin `bash_path` 同目录推导 `cygpath.exe`。
- `cygpath.exe` 调用使用 argv 形式，没有把 workspace 拼进 shell command 字符串。
- 转换成功后，tmux create-window script 继续使用转换后的 Cygwin path 作为 `-c` 参数。
- `cygpath.exe` 缺失和转换超时已有明确错误；非零退出仍使用 stderr 或通用 `Cygwin workspace path conversion failed`，与原有执行失败行为一致。
- Cygwin tmux command env 行为未回退，仍通过 `_cygwin_process_env()` 将 Cygwin `bin` 放在 PATH 最前。

## Spec alignment

不适用。轻量模式 / light 未创建单独 spec 文档，按 requirement / 需求核对。

## Plan alignment

不适用。轻量模式 / light 未创建单独 plan 文档，按 requirement / 需求核对。

## Actual diff summary

实际改动文件：

- `src/termbridge/services.py`
  - `_cygwin_workspace_path()` 先从 `bash_path` 推导 `cygpath.exe`。
  - 如果 `cygpath.exe` 不存在，直接抛出 `InvalidTerminalConfigError`。
  - 将 subprocess argv 从 `[bash_path, "-lc", "cygpath -u ..."]` 改为 `[cygpath_path, "-u", workspace_text]`。
  - 新增 `_cygpath_executable_path()` 小辅助函数。

- `tests/test_terminal_service.py`
  - 更新 Cygwin tmux command 测试，断言第一个 subprocess 调用为 direct `cygpath.exe -u <workspace>`。
  - 保留断言：tmux command env 的 PATH 首项是 Cygwin `bin`。
  - 保留断言：tmux create command 使用转换后的 Cygwin workspace path。
  - 新增 `cygpath.exe` 超时错误测试。
  - 新增 `cygpath.exe` 缺失错误测试。

- `docs/requirement/20260617-cygwin-direct-cygpath.md`
  - 记录并接受本次轻量需求。

- `docs/verification/20260617-cygwin-direct-cygpath.md`
  - 记录本次验证结果。

## Expected vs actual changed files

| 文件 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- |
| `src/termbridge/services.py` | 修改 Cygwin workspace path conversion | 已修改 | 符合 |
| `tests/test_terminal_service.py` | 更新/新增相关单测 | 已修改 | 符合 |
| `docs/requirement/20260617-cygwin-direct-cygpath.md` | 轻量需求文档 | 已新增 | 符合 |
| `docs/verification/20260617-cygwin-direct-cygpath.md` | 验证文档 | 已新增 | 符合 |
| Windows/WSL、Linux runtime 代码 | 不应修改 | 未修改 | 符合 |
| `.termbridge` 数据结构 | 不应修改 | 未修改 | 符合 |

## Acceptance checklist

- [x] Windows/Cygwin workspace 转换不再通过 `bash -lc "cygpath -u ..."` 完成。
- [x] 从 configured Cygwin `bash_path` 推导 `cygpath.exe` 路径。
- [x] 调用 `cygpath.exe` 使用 argv 参数形式。
- [x] 转换成功后 tmux `-c` 使用转换后的 Cygwin path。
- [x] `cygpath.exe` 缺失时返回明确错误。
- [x] `cygpath.exe` 超时时返回明确错误。
- [x] `cygpath.exe` 非零退出有可诊断错误信息。
- [x] Cygwin tmux command env 行为未回退。
- [x] 测试覆盖 direct `cygpath.exe` 调用、tmux 使用转换结果、超时和缺失场景。

## Command results

### 相关单测

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_terminal_service.py
```

结果：

```text
42 passed in 1.69s
```

### 全量 Python 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

结果：

```text
159 passed, 1 warning in 2.65s
```

警告来自 FastAPI/TestClient 依赖栈的 Starlette deprecation warning，不是本次改动引入的业务失败。

### Ruff lint

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
```

结果：

```text
All checks passed!
```

### Mypy type check

```powershell
.\.venv\Scripts\python.exe -m mypy src
```

结果：

```text
Success: no issues found in 15 source files
```

### 真实 Cygwin cygpath 验证

```powershell
& 'D:\ProgramFiles\Cygwin64\bin\cygpath.exe' -u 'D:\SourceCodes\mywork\pomelo-orbit'
```

结果：

```text
/d/SourceCodes/mywork/pomelo-orbit
```

## Scope deviations

无范围扩张。未修改 Windows/WSL、Linux、shortcut command 执行方式、`.termbridge` 数据结构或 Cygwin readiness 判定逻辑。

## Risks

- 当前实现按标准 Cygwin 安装假设 `bash.exe` 与 `cygpath.exe` 位于同一 `bin` 目录。非标准 wrapper bash 会得到明确缺失错误，需要后续另立需求扩展查找策略。
- tmux 管理命令仍通过 Cygwin bash 执行；本次只移除 workspace path conversion 的 shell 嵌套。

## Incomplete items

无。

## Conclusion

验证通过。本次改动满足已接受的轻量需求：workspace path conversion 已改为 direct `cygpath.exe` argv 调用，减少 shell 嵌套和 profile 污染风险；相关单测、全量测试、lint、type check 和真实 `cygpath.exe` 转换均通过。
