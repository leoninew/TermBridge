# Cygwin workspace 直接 cygpath 转换需求
最后修改时间: 2026-06-17 13:30:46

## Review status

Accepted

## Background

创建 Windows/Cygwin session 时，后端需要把 Windows workspace 路径转换为 Cygwin 可识别的 Unix path，再传给 tmux `-c` 使用。

当前实现通过 Cygwin bash 执行 `bash -lc "cygpath -u ..."` 完成转换。一次实际创建 session 的日志显示该步骤超时并返回 400：

```text
Cygwin workspace path conversion timed out
```

本地复验显示同一命令当前可快速返回，但现有设计仍把纯路径转换包装进 login shell，存在不必要的 profile 初始化、quoting 和诊断复杂度。

## Goal

- 将 Windows/Cygwin workspace 路径转换改为直接调用同一 Cygwin 安装目录下的 `cygpath.exe`。
- 转换完成后继续使用转换出的 Cygwin path 传给 tmux `-c`。
- 减少 `bash -lc` 嵌套，避免路径转换受 login shell/profile 影响。
- 保持现有 Windows/Cygwin shortcut、tmux window 创建和 session 创建行为不变。
- 失败时给出明确错误，区分 `cygpath.exe` 缺失、执行失败和超时。

## Non-goal

- 不重构整个 Cygwin runtime command 构造流程。
- 不改变 shortcut command 的执行方式；用户配置的命令仍由 tmux window 启动。
- 不改变 Windows/WSL 或 Linux 的 workspace 处理逻辑。
- 不调整 `.termbridge` 数据结构或用户配置格式。
- 不修改 Cygwin 环境检测的整体 ready 判定逻辑，除非为直接定位 `cygpath.exe` 做必要的小范围辅助函数。

## User scenarios

1. 用户使用 Windows/Cygwin shortcut 在 `D:\SourceCodes\mywork\pomelo-orbit` 创建 session。
   - 后端直接运行 `D:\ProgramFiles\Cygwin64\bin\cygpath.exe -u D:\SourceCodes\mywork\pomelo-orbit`。
   - 得到 `/d/SourceCodes/mywork/pomelo-orbit`。
   - tmux window 使用该路径作为 `-c` 工作目录。

2. 用户的 Cygwin shell profile 中存在慢初始化或交互逻辑。
   - workspace path conversion 不启动 login shell，因此不受 profile 影响。

3. `cygpath.exe` 缺失或不可执行。
   - 创建 session 失败，并返回明确错误，而不是表现为 bash/tmux 混合错误。

## Acceptance

- Windows/Cygwin workspace 转换不再通过 `bash -lc "cygpath -u ..."` 完成。
- 代码从已配置/已确认的 Cygwin `bash_path` 推导 `cygpath.exe` 路径，例如：
  - `D:\ProgramFiles\Cygwin64\bin\bash.exe`
  - `D:\ProgramFiles\Cygwin64\bin\cygpath.exe`
- 调用 `cygpath.exe` 时使用 argv 参数形式，不把 workspace 拼进 shell command 字符串。
- 转换成功后，tmux 创建 window 的 `-c` 参数继续使用转换后的 Cygwin path。
- `cygpath.exe` 缺失、非零退出、超时分别有可诊断错误信息。
- 现有 Cygwin tmux command env 行为不回退；tmux 管理命令仍使用 Cygwin `bin` 优先的 env。
- 测试覆盖：
  - Cygwin tmux 创建前直接调用 `cygpath.exe -u <workspace>`。
  - tmux create command 使用 `cygpath.exe` 输出的路径。
  - direct `cygpath.exe` 超时时返回 `Cygwin workspace path conversion timed out` 或同等明确错误。
  - `cygpath.exe` 缺失时返回明确错误。

## Open questions

暂无必须阻塞实现的问题。

## Decisions

- 采用直接调用 `cygpath.exe` 的方案，而不是把 `bash -lc` 改成 `bash --noprofile --norc -c`。
- `cygpath.exe` 路径优先从 configured Cygwin `bash_path` 的同目录推导，不依赖宿主 PATH 搜索。
- 保留现有 timeout 机制，但 timeout 范围只覆盖 `cygpath.exe` 执行本身。

## Risk

- 如果某些非标准 Cygwin 安装中 `bash.exe` 与 `cygpath.exe` 不在同一目录，需要明确报错或后续扩展查找策略。
- Windows path 到 Cygwin path 的 mount 风格由目标 `cygpath.exe` 决定；这正是期望行为，但测试不能写死所有机器的真实 mount 风格，只应断言 mock 输出被传递给 tmux。
- 本次仅移除 path conversion 的 shell 嵌套；tmux 管理命令本身仍会通过 Cygwin bash 执行，若未来还有 profile 污染风险，需要另立需求处理。

## User review notes

- 用户指出：路径转换应直接由 `cygpath` 处理完再使用；多层命令嵌套难看且容易出问题。
