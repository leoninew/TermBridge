import shlex
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Protocol

from termbridge.settings import Settings


@dataclass(frozen=True)
class ProcessHandle:
    pid: int


class ProcessAdapter(Protocol):
    def start(
        self,
        command: list[str],
        cwd: Path,
        *,
        log_file: Path | None = None,
        suppress_output: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> ProcessHandle: ...

    def terminate(self, handle: ProcessHandle) -> None: ...

    def is_running(self, handle: ProcessHandle) -> bool: ...


class TtydProcessAdapter:
    def __init__(self, settings: Settings) -> None:
        self._processes: dict[int, subprocess.Popen[bytes]] = {}
        self._log_files: dict[int, BinaryIO] = {}
        self._settings = settings

    def start(
        self,
        command: list[str],
        cwd: Path,
        *,
        log_file: Path | None = None,
        suppress_output: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> ProcessHandle:
        output: BinaryIO | int | None = None
        log_output: BinaryIO | None = None
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_output = log_file.open("ab")
            self._write_log_header(log_output, command, cwd, log_file)
            output = log_output
        elif suppress_output:
            output = subprocess.DEVNULL
        try:
            process = subprocess.Popen(command, cwd=cwd, stdout=output, stderr=output, env=env)
        except Exception:
            if log_output is not None:
                log_output.close()
            raise
        self._processes[process.pid] = process
        if log_output is not None:
            self._write_log_pid(log_output, process.pid)
            self._log_files[process.pid] = log_output
        return ProcessHandle(pid=process.pid)

    def terminate(self, handle: ProcessHandle) -> None:
        process = self._processes.get(handle.pid)
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=self._settings.process_shutdown_timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=self._settings.process_shutdown_timeout_seconds)
        self._processes.pop(handle.pid, None)
        self._close_log_file(handle.pid)

    def is_running(self, handle: ProcessHandle) -> bool:
        process = self._processes.get(handle.pid)
        if process is None:
            return False
        if process.poll() is None:
            return True
        self._processes.pop(handle.pid, None)
        self._close_log_file(handle.pid)
        return False

    def _write_log_header(self, output: BinaryIO, command: list[str], cwd: Path, log_file: Path) -> None:
        timestamp = datetime.now(UTC).isoformat()
        quoted_command = " ".join(shlex.quote(item) for item in command)
        session_id = log_file.stem
        header = (
            "[TermBridge] Starting ttyd process\n"
            f"timestamp={timestamp}\n"
            f"session_id={session_id}\n"
            f"cwd={cwd}\n"
            f"command={quoted_command}\n"
            "pid=<pending>\n"
            "--- ttyd stdout/stderr ---\n"
        )
        output.write(header.encode("utf-8"))
        output.flush()

    def _write_log_pid(self, output: BinaryIO, pid: int) -> None:
        output.write(f"[TermBridge] ttyd pid={pid}\n".encode())
        output.flush()

    def _close_log_file(self, pid: int) -> None:
        output = self._log_files.pop(pid, None)
        if output is not None:
            output.close()
