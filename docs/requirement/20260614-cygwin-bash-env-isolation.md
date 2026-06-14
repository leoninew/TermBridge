# Cygwin bash 环境隔离轻量需求

Review status: Accepted

当前：轻量模式 / light，需求 / Requirement

## Goal

修复 Windows/Cygwin runtime 不应依赖宿主进程 PATH 的问题：用户只要安装了 Cygwin 并配置或被检测到 `bash.exe` 绝对路径，TermBridge 就应使用该 Cygwin 环境启动检测、tmux 管理命令和 ttyd attach 命令。

具体目标：

- Cygwin host 使用 `bash.exe`，不使用 `mintty.exe`。
- 从 Cygwin `bash.exe` 绝对路径推导 Cygwin `bin` 目录。
- 运行 Cygwin 检测、tmux 命令、ttyd 子进程时显式传入受控 env，使 Cygwin `bin` 优先于 Git Bash/MSYS 等其他 Unix-like 工具链。
- 自动发现补充常见 Cygwin 安装路径，至少覆盖 `D:/ProgramFiles/Cygwin/bin/bash.exe`。
- 目录传递不依赖 `Popen(cwd=...)` 或 `ttyd --cwd` 被 Cygwin login shell 继承；保留 bash/tmux 命令内显式目录传递。

## Non-goal

- 不改用 `mintty.exe` 或打开独立 GUI 终端。
- 不实现 Cygwin 安装器、自动安装或完整 registry 探测。
- 不重构 workspace / tmux session / tmux window 数据模型。
- 不改变 Windows/WSL 或 Linux runtime 的启动策略。

## Acceptance

- Cygwin 检测使用指定 `bash_path` 执行时，即使宿主 PATH 中 Git Bash 在前，也应优先解析到 Cygwin 自身的 `bash`、`cygpath`、`tmux`。
- Cygwin tmux 管理命令通过同一受控 env 执行。
- ttyd 启动 Cygwin attach command 时，子进程环境也应优先使用 Cygwin `bin`。
- 自动发现候选包含 `D:/ProgramFiles/Cygwin/bin/bash.exe`。
- 相关单元测试覆盖 env 构造和 subprocess 调用传入 env 的行为。

## Risk

- 当前机器 Cygwin mount 风格可能是 `/d/...` 而不是 `/cygdrive/d/...`；本次只保证不依赖全局 PATH，目录转换策略如需进一步增强可后续单独处理。
- `ttyd` 是 Windows 原生进程，给其进程 env 加 Cygwin `bin` 优先可能影响它执行 child command 的 PATH，但这是 Cygwin host 下的预期隔离行为。

## User review notes

用户要求“轻量模式 推进实现”，视为接受本轻量需求并进入实现阶段。
