# Cygwin bash 环境隔离验证

Review status: Accepted

当前：轻量模式 / light，验证 / Verification

## What changed

- 新增轻量需求文档：`docs/requirement/20260614-cygwin-bash-env-isolation.md`。
- `ProcessAdapter` / `TtydProcessAdapter` 支持向 `subprocess.Popen` 传入 `env`，用于控制 ttyd 进程环境。
- Cygwin bash/tmux 检测和 tmux 管理命令统一使用由 `bash_path` 推导出的 Cygwin `bin` 优先 PATH。
- Cygwin bash 检测增加 `uname -o` 校验，避免 Git Bash/MSYS 被误判为 Cygwin bash。
- Cygwin 自动发现候选补充 `D:/ProgramFiles/Cygwin/bin/bash.exe` 等常见路径，并把常见 Cygwin 安装路径优先于 PATH fallback。
- ttyd 启动 Cygwin attach command 时传入 runtime env，避免继承宿主 Git Bash/MSYS PATH 顺序。
- Cygwin workspace 传给 tmux `-c` 前改为通过同一个 `bash_path` 执行 `cygpath -u`，使用当前 Cygwin mount 风格的 Unix path。
- 增加 Cygwin tmux 创建/attach 诊断日志，记录 workspace 转换、create-window script、pane_current_path、PATH head 和 ttyd runtime command。
- 补充测试覆盖 Cygwin tmux subprocess env、ttyd process env 传递，以及 tmux `-c` 使用 `cygpath -u` 转换结果。

## Acceptance

- [x] Cygwin runtime 使用 `bash.exe`，未引入 `mintty.exe`。
- [x] 从 `bash_path` 推导 Cygwin `bin` 并放到子进程 PATH 最前。
- [x] Cygwin bash 检测、tmux 检测、tmux 管理命令使用受控 env。
- [x] ttyd 子进程启动支持并接收 runtime env。
- [x] 自动发现候选包含 `D:/ProgramFiles/Cygwin/bin/bash.exe`。
- [x] Cygwin workspace path 通过 `cygpath -u` 转为当前 Cygwin mount 风格后传给 tmux `-c`。
- [x] 测试覆盖 Cygwin env 优先级、ttyd env 传递和 tmux `-c` 路径转换结果。

## Commands

- `python -m pytest tests/test_terminal_service.py tests/test_services.py`
  - 第一次失败：新增测试断言使用 `/` 路径，而 Windows `Path(...).parent` 返回 `\` 风格。
  - 修正断言为 `Path(...)` 比较后通过：`66 passed in 1.06s`。
- `python -m pytest`
  - 结果：`117 passed, 1 warning in 1.96s`。
  - warning：FastAPI/TestClient 依赖的 StarletteDeprecationWarning，非本次改动引入。
- `python -m ruff check src tests`
  - 失败：当前 Python 环境没有安装 `ruff` 模块。
- `uv run ruff check src tests`
  - 结果：`All checks passed!`。
- `uv run mypy src tests`
  - 结果：`Success: no issues found in 24 source files`。
- `git diff --check`
  - 第一次失败：`src/termbridge/process.py` 原有 CRLF 与新增行组合导致 diff whitespace 检查报 trailing whitespace；已统一相关变更文件行尾并重跑通过。

## Remaining risk

- 本次没有改变 workspace 路径到 Cygwin Unix 路径的转换策略；当前仍主要使用 `D:/...` forward-slash 形式传给 tmux `-c`。如果后续确认某些 Cygwin mount 配置不接受该形式，应单独实现 `cygpath -u` workspace 转换。
- `uv run ruff` 创建了本地虚拟环境 `.venv`，该目录未出现在当前 git status 中；如本地未忽略，需要用户自行清理或确认。
