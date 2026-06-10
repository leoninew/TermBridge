import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ProcessHandle:
    pid: int


class ProcessAdapter(Protocol):
    def start(self, command: list[str], cwd: Path) -> ProcessHandle: ...

    def terminate(self, handle: ProcessHandle) -> None: ...

    def is_running(self, handle: ProcessHandle) -> bool: ...


class TtydProcessAdapter:
    def __init__(self) -> None:
        self._processes: dict[int, subprocess.Popen[bytes]] = {}

    def start(self, command: list[str], cwd: Path) -> ProcessHandle:
        process = subprocess.Popen(command, cwd=cwd)
        self._processes[process.pid] = process
        return ProcessHandle(pid=process.pid)

    def terminate(self, handle: ProcessHandle) -> None:
        process = self._processes.get(handle.pid)
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        self._processes.pop(handle.pid, None)

    def is_running(self, handle: ProcessHandle) -> bool:
        process = self._processes.get(handle.pid)
        if process is None:
            return False
        return process.poll() is None
