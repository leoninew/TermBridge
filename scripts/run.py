"""Run TermBridge frontend and backend development servers together."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"


class DevProcess:
    def __init__(self, name: str, command: Sequence[str], cwd: Path) -> None:
        self.name = name
        self.command = resolve_command(command)
        self.cwd = cwd
        self.process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        print(f"[{self.name}] starting: {' '.join(self.command)}", flush=True)
        if os.name == "nt":
            self.process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            return
        self.process = subprocess.Popen(self.command, cwd=self.cwd, start_new_session=True)

    def poll(self) -> int | None:
        if self.process is None:
            return None
        return self.process.poll()

    def terminate(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        print(f"[{self.name}] stopping", flush=True)
        if os.name == "nt":
            self._kill_windows_tree(force=False)
            return
        subprocess.run(["kill", "-TERM", f"-{self.process.pid}"], check=False)

    def kill(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        print(f"[{self.name}] killing", flush=True)
        if os.name == "nt":
            self._kill_windows_tree(force=True)
            return
        subprocess.run(["kill", "-KILL", f"-{self.process.pid}"], check=False)

    def wait(self, timeout: float | None = None) -> int | None:
        if self.process is None:
            return None
        return self.process.wait(timeout=timeout)

    def _kill_windows_tree(self, *, force: bool) -> None:
        if self.process is None:
            return
        command = ["taskkill", "/PID", str(self.process.pid), "/T"]
        if force:
            command.append("/F")
        subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def resolve_command(command: Sequence[str]) -> list[str]:
    resolved = list(command)
    executable = shutil.which(resolved[0])
    if executable:
        resolved[0] = executable
    return resolved


PROCESSES = [
    DevProcess(
        "fastapi",
        [sys.executable, "-m", "termbridge.main", "--host", "127.0.0.1", "--port", "9008", "--reload"],
        ROOT,
    ),
    DevProcess("web", ["yarn", "dev"], WEB_DIR),
]


stopping = False


def stop_processes() -> None:
    global stopping
    if stopping:
        return
    stopping = True

    for process in PROCESSES:
        process.terminate()

    deadline = time.monotonic() + 5
    for process in PROCESSES:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()

    for process in PROCESSES:
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()


def handle_signal(signum: int, _frame: object) -> None:
    print(f"\n[dev] received signal {signum}; stopping servers", flush=True)
    stop_processes()
    raise SystemExit(128 + signum)


def main() -> int:
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    if os.name == "nt" and hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, handle_signal)

    try:
        for process in PROCESSES:
            process.start()

        while True:
            for process in PROCESSES:
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"[dev] {process.name} exited with code {exit_code}; stopping remaining servers", flush=True)
                    stop_processes()
                    return exit_code
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[dev] interrupted; stopping servers", flush=True)
        stop_processes()
        return 130
    except Exception:
        stop_processes()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
