# Cygwin tmux 工作目录路径传递

本文总结 TermBridge 在 Windows/Cygwin runtime 中向 tmux 传递 workspace 工作目录时的实践和排障结论。

## 背景

TermBridge 的 Windows/Cygwin 会话链路是：

```text
Windows 后端
  -> Windows 原生 ttyd
    -> Cygwin bash.exe -lc <script>
      -> tmux new-session / new-window / attach-session
```

用户在 UI 中选择的是 Windows 路径，例如：

```text
D:\SourceCodes\mywork\term-bridge
```

但 tmux 运行在 Cygwin 环境内，`tmux new-session -c` / `tmux new-window -c` 需要的是 Cygwin 当前 mount 配置下可被 tmux 正确 `chdir()` 的路径。

## 问题现象

曾经的实现只把 Windows 反斜杠替换为正斜杠：

```text
D:\SourceCodes\mywork\term-bridge
-> D:/SourceCodes/mywork/term-bridge
```

然后生成 tmux 命令：

```sh
tmux new-window -P -F '#{window_id}' \
  -t tb_cyg_18fe2767127bef3e \
  -n 1 \
  -c D:/SourceCodes/mywork/term-bridge \
  bash
```

在某些机器上，shell 中执行：

```sh
cd D:/SourceCodes/mywork/term-bridge
```

可能成功；但这不代表 tmux 的 `-c D:/...` 也一定成功。

实际故障日志中，tmux window 创建成功，但 pane 的当前目录变成了 home：

```text
tmux create-window script=... -c D:/SourceCodes/mywork/term-bridge bash
tmux create-window result returncode=0 stdout=@12 stderr=
tmux window current path stdout=/c/Users/leon
```

这说明 tmux 接受了命令并创建了 window，但 `-c D:/...` 没有作为有效工作目录生效，最终回落到 shell home。

## 根因

`D:/...` 是 Windows 风格路径的 forward-slash 变体，不是 Cygwin/tmux 最稳妥的工作目录输入。

差异点包括：

- `cd D:/...` 是 bash/shell 层行为，可能有额外兼容处理。
- `tmux -c <path>` 是 tmux 自己处理路径并调用 `chdir()`。
- tmux server 是长期进程，可能继承旧环境。
- 不同机器的 Cygwin mount 配置可能不同，例如：
  - `/d/...`
  - `/cygdrive/d/...`
  - 其他自定义 mount prefix
- 不同机器的 bash/tmux 来源、版本、PATH 顺序可能不同。

因此，同一条：

```sh
tmux new-window -c D:/SourceCodes/mywork/term-bridge bash
```

可能在一台机器上可用，在另一台机器上退回 home。

## 正确策略

不要手写或猜测 Cygwin 路径规则。应使用当前配置的 Cygwin `bash.exe` 执行 `cygpath -u`，让 Cygwin 自己返回当前 mount 配置下的 Unix path。

输入：

```text
D:\SourceCodes\mywork\term-bridge
```

转换：

```sh
cygpath -u 'D:\SourceCodes\mywork\term-bridge'
```

可能输出：

```text
/d/SourceCodes/mywork/term-bridge
```

或：

```text
/cygdrive/d/SourceCodes/mywork/term-bridge
```

最终传给 tmux：

```sh
tmux new-window -P -F '#{window_id}' \
  -t tb_cyg_18fe2767127bef3e \
  -n 1 \
  -c /d/SourceCodes/mywork/term-bridge \
  bash
```

## 实现约定

### 1. 使用 bash.exe，不使用 mintty.exe

TermBridge 的 Cygwin runtime 应使用：

```text
D:\ProgramFiles\Cygwin\bin\bash.exe -lc <script>
```

不要使用 `mintty.exe`。`mintty.exe` 是 GUI terminal emulator，会打开独立窗口，不适合作为 ttyd/tmux 的后端 runtime。

### 2. 不依赖用户全局 PATH

用户只要安装了 Cygwin，并且 TermBridge 能检测或保存 `bash.exe` 绝对路径，就应该可以工作。

从：

```text
D:\ProgramFiles\Cygwin\bin\bash.exe
```

推导 Cygwin bin：

```text
D:\ProgramFiles\Cygwin\bin
```

运行 Cygwin 子进程时，显式把该目录放到 PATH 最前，避免 Git Bash/MSYS 等工具链污染：

```text
PATH=D:\ProgramFiles\Cygwin\bin;<original PATH>
```

### 3. 检测 bash 必须确认是 Cygwin

不要只看 `bash --version`，因为 Git Bash/MSYS 也会通过。

应通过 Cygwin bash 执行：

```sh
cygpath -w $(command -v bash) && bash --version && uname -o
```

其中 `uname -o` 应返回：

```text
Cygwin
```

### 4. 传给 tmux -c 前必须转换 workspace path

推荐流程：

```text
Windows workspace path
  -> 指定 Cygwin bash.exe
  -> cygpath -u <windows path>
  -> tmux new-session/new-window -c <converted path>
```

不要只做：

```python
str(path).replace("\\", "/")
```

这只能得到 `D:/...`，不能保证 tmux 可用。

## 推荐诊断日志

排查 Cygwin tmux 工作目录问题时，建议记录：

- Cygwin `bash.exe` path。
- Cygwin env PATH 前几项。
- Windows workspace path。
- `cygpath -u` 转换结果。
- 完整 tmux create-window script。
- tmux create-window stdout/stderr。
- 创建后实际 pane 当前目录：

```sh
tmux display-message -p -t <window_id> '#{pane_current_path}'
```

关键判断：

```text
如果 pane_current_path 是目标目录：
  tmux -c 生效，后续问题应看 attach / select-window / ttyd。

如果 pane_current_path 是 home：
  tmux -c 没生效，应检查传给 -c 的路径是否为 cygpath -u 后的结果。
```

## 两台机器行为不同的原因

另一台机器没有问题，通常不是业务逻辑天然正确，而是环境刚好兼容 `D:/...`：

- Cygwin mount 配置不同。
- tmux 版本不同。
- bash/tmux 实际来源不同。
- tmux server 启动时继承的环境不同。
- PATH 顺序不同。

因此，`D:/...` 能工作只能视为兼容性巧合。稳定做法仍是使用当前 Cygwin 的 `cygpath -u` 转换结果。

## 最小复现命令

在 Cygwin bash 中可对比：

```sh
workspace='D:\SourceCodes\mywork\term-bridge'
converted="$(cygpath -u "$workspace")"

printf 'converted=%s\n' "$converted"

tmux new-session -d -P -F '#{window_id}' -s tb_path_test -n test -c "$converted" bash
window_id="$(tmux display-message -p -t tb_path_test '#{window_id}')"
tmux display-message -p -t "$window_id" '#{pane_current_path}'
tmux kill-session -t tb_path_test
```

预期 `pane_current_path` 等于 `converted`，或至少是同一目录的规范化表示。
