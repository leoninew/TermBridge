import shlex

from termbridge.exceptions import InvalidTerminalCommandError, UnknownRuntimeError


class RuntimeRegistry:
    def __init__(self, commands: dict[str, list[str]] | None = None) -> None:
        self._commands = commands or {
            "claude-code": ["claude"],
            "codex": ["codex"],
            "powershell": ["pwsh"],
            "bash": ["bash"],
        }

    def resolve(self, runtime: str, terminal_command: str | None = None) -> list[str]:
        if runtime == "custom":
            if terminal_command is None or not terminal_command.strip():
                raise InvalidTerminalCommandError()
            return shlex.split(terminal_command)

        command = self._commands.get(runtime)
        if command is None:
            raise UnknownRuntimeError(runtime)
        return command.copy()
