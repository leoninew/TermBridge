from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from termbridge.exceptions import WorkspaceNotFoundError
from termbridge.models import CreateSessionRequest, Shortcut
from termbridge.ports import PortAllocator
from termbridge.process import ProcessHandle
from termbridge.repositories import FileSessionRepository
from termbridge.runtime import RuntimeRegistry
from termbridge.services import SessionService, TerminalService
from termbridge.settings import Settings


class FakeProcessAdapter:
    def __init__(self) -> None:
        self.started: list[tuple[list[str], Path]] = []
        self.terminated: list[ProcessHandle] = []
        self.running = True
        self.next_pid = 100

    def start(self, command: list[str], cwd: Path) -> ProcessHandle:
        self.started.append((command, cwd))
        handle = ProcessHandle(pid=self.next_pid)
        self.next_pid += 1
        return handle

    def terminate(self, handle: ProcessHandle) -> None:
        self.terminated.append(handle)

    def is_running(self, handle: ProcessHandle) -> bool:
        return self.running


class FakeShortcutService:
    def __init__(self, ttyd_executable: str = "custom-ttyd") -> None:
        self.ttyd_executable = ttyd_executable
        self.shortcut = Shortcut(
            id="claude-code",
            name="Claude Code",
            command="claude --dangerously-skip-permissions",
            host="windows_cygwin",
        )

    def normalize_tmux_session_name(self, name: str, fallback: str) -> str:
        return name or fallback

    def resolve_shortcut_command(
        self, shortcut_id: str, workspace: Path, *, tmux_session_name: str
    ) -> tuple[list[str], Shortcut, str]:
        return ["bash.exe", "-lc", f"tmux attach -t {tmux_session_name}"], self.shortcut, "bash.exe"

    def resolve_ttyd_executable(self, host: str, cygwin_bash_path: str | None = None) -> str:
        return self.ttyd_executable


def make_service(
    tmp_path: Path,
    process: FakeProcessAdapter | None = None,
    *,
    use_wsl: bool = False,
    shortcut_service: FakeShortcutService | None = None,
) -> SessionService:
    settings = Settings(
        ttyd_executable="ttyd",
        use_wsl=use_wsl,
        host="127.0.0.1",
        port_start=9201,
        port_end=9205,
        state_dir=tmp_path / "state",
    )
    return SessionService(
        settings=settings,
        repository=FileSessionRepository(settings.sessions_file),
        runtime_registry=RuntimeRegistry(),
        port_allocator=PortAllocator(settings.host, settings.port_start, settings.port_end),
        process_adapter=process or FakeProcessAdapter(),
        terminal_service=cast(TerminalService, shortcut_service or FakeShortcutService()),
    )


def test_service_creates_session_with_shortcut(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process)

    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    assert response.name == "Test"
    assert response.runtime == "windows_cygwin"
    assert response.shortcut_id == "claude-code"
    assert response.shortcut_name == "Claude Code"
    assert response.tmux_session_name == "Test"
    assert response.port == 9201
    assert process.started == [
        (
            [
                "custom-ttyd",
                "--writable",
                "--port",
                "9201",
                "--cwd",
                str(tmp_path.resolve()),
                "bash.exe",
                "-lc",
                "tmux attach -t Test",
            ],
            tmp_path.resolve(),
        )
    ]


def test_service_wraps_ttyd_command_with_wsl_when_enabled(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process, use_wsl=True)

    service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    assert process.started[0][0][0] == "wsl"
    assert process.started[0][0][1] == "custom-ttyd"


def test_service_delete_terminates_process_and_removes_session(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    with patch("termbridge.services.subprocess.run") as run:
        service.delete(response.id)

    assert process.terminated == [ProcessHandle(pid=100)]
    run.assert_called_once_with(
        ["bash.exe", "-lc", "tmux kill-session -t Test"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert service.list_sessions() == []


def test_service_deletes_session_when_tmux_cleanup_fails(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    with patch("termbridge.services.subprocess.run", side_effect=OSError("boom")):
        service.delete(response.id)

    assert service.list_sessions() == []


def test_service_restarts_stopped_session(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    process.running = False

    restarted = service.restart(response.id)

    assert restarted.status == "running"
    assert restarted.port == 9201
    assert restarted.url == "http://127.0.0.1:9201"
    assert process.started[-1] == process.started[0]


def test_service_restart_running_session_is_noop(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    restarted = service.restart(response.id)

    assert restarted.id == response.id
    assert len(process.started) == 1


def test_service_rejects_missing_workspace(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(WorkspaceNotFoundError):
        service.create(CreateSessionRequest(name="Test", workspace=tmp_path / "missing", shortcut_id="claude-code"))


def test_service_refreshes_stopped_status(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    process.running = False

    refreshed = service.get(response.id)

    assert refreshed.status == "stopped"
