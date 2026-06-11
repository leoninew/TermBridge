from pathlib import Path
from typing import cast

import pytest

from termbridge.exceptions import InvalidTerminalConfigError, WorkspaceNotFoundError
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


class FailingProcessAdapter(FakeProcessAdapter):
    def start(self, command: list[str], cwd: Path) -> ProcessHandle:
        raise RuntimeError("process failed")


class FakeShortcutService:
    def __init__(self, ttyd_executable: str = "custom-ttyd") -> None:
        self.ttyd_executable = ttyd_executable
        self.created_windows: list[tuple[Shortcut, Path, str, str]] = []
        self.killed_windows: list[tuple[str, Path, str | None]] = []
        self.killed_sessions: list[tuple[str, Path, str]] = []
        self.window_exists = True
        self.window_by_name: str | None = None
        self.shortcut = Shortcut(
            id="claude-code",
            name="Claude Code",
            command="claude",
            host="windows_cygwin",
        )

    def resolve_shortcut(self, shortcut_id: str) -> Shortcut:
        return self.shortcut.model_copy(update={"id": shortcut_id})

    def create_tmux_window(
        self, shortcut: Shortcut, workspace: Path, *, tmux_session_name: str, window_name: str
    ) -> str:
        self.created_windows.append((shortcut, workspace, tmux_session_name, window_name))
        return f"@{len(self.created_windows)}"

    def build_tmux_attach_command(
        self, host: str, workspace: Path, *, tmux_session_name: str, tmux_window_id: str | None
    ) -> list[str]:
        return ["bash.exe", "-lc", f"tmux select-window -t {tmux_window_id} && exec tmux attach -t {tmux_session_name}"]

    def kill_tmux_window(self, host: str, workspace: Path, *, tmux_window_id: str | None) -> None:
        self.killed_windows.append((host, workspace, tmux_window_id))

    def kill_tmux_session(self, host: str, workspace: Path, *, tmux_session_name: str) -> None:
        self.killed_sessions.append((host, workspace, tmux_session_name))

    def tmux_window_exists(self, host: str, workspace: Path, *, tmux_window_id: str | None) -> bool:
        return self.window_exists

    def find_tmux_window_by_name(self, host: str, workspace: Path, *, tmux_session_name: str, window_name: str) -> str | None:
        return self.window_by_name

    def resolve_ttyd_executable(self, host: str, cygwin_bash_path: str | None = None) -> str:
        return self.ttyd_executable


def make_service(
    tmp_path: Path,
    process: FakeProcessAdapter | None = None,
    *,
    shortcut_service: FakeShortcutService | None = None,
) -> SessionService:
    settings = Settings(
        ttyd_executable="ttyd",
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


def test_service_creates_entry_with_workspace_tmux_session(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)

    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    assert response.name == "Test"
    assert response.runtime == "windows_cygwin"
    assert response.shortcut_id == "claude-code"
    assert response.shortcut_name == "Claude Code"
    assert response.tmux_session_name is not None
    assert response.tmux_session_name.startswith("tb_cyg_")
    assert response.tmux_session_name != "Test"
    assert response.port == 9201
    assert shortcuts.created_windows[0][2] == response.tmux_session_name
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
                f"tmux select-window -t @1 && exec tmux attach -t {response.tmux_session_name}",
            ],
            tmp_path.resolve(),
        )
    ]


def test_service_reuses_workspace_for_same_host_and_path(tmp_path: Path) -> None:
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, shortcut_service=shortcuts)

    first = service.create(CreateSessionRequest(name="One", workspace=tmp_path, shortcut_id="claude-code"))
    second = service.create(CreateSessionRequest(name="Two", workspace=tmp_path, shortcut_id="claude-code"))

    assert first.workspace_id == second.workspace_id
    assert first.tmux_session_name == second.tmux_session_name
    assert [item[3] for item in shortcuts.created_windows] == ["One", "Two"]


def test_service_rejects_duplicate_session_name_in_workspace(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create(CreateSessionRequest(name="Same", workspace=tmp_path, shortcut_id="claude-code"))

    with pytest.raises(InvalidTerminalConfigError, match="Session name already exists"):
        service.create(CreateSessionRequest(name="Same", workspace=tmp_path, shortcut_id="claude-code"))


def test_service_uses_different_workspace_for_different_paths(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    service = make_service(tmp_path)

    first = service.create(CreateSessionRequest(name="Same", workspace=tmp_path, shortcut_id="claude-code"))
    second = service.create(CreateSessionRequest(name="Same", workspace=other, shortcut_id="claude-code"))

    assert first.workspace_id != second.workspace_id
    assert first.tmux_session_name != second.tmux_session_name


def test_service_preserves_linux_workspace_path_case(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    assert service._workspace_id("linux", Path("/tmp/Repo")) != service._workspace_id("linux", Path("/tmp/repo"))
    assert service._workspace_id("windows_cygwin", Path("D:/Repo")) == service._workspace_id(
        "windows_cygwin", Path("D:/repo")
    )


def test_service_cleans_tmux_window_when_create_process_start_fails(tmp_path: Path) -> None:
    process = FailingProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)

    with pytest.raises(RuntimeError, match="process failed"):
        service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    assert shortcuts.killed_windows == [("windows_cygwin", tmp_path.resolve(), "@1")]
    assert service.list_sessions() == []


def test_service_stop_keeps_record_and_removes_managed_window(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    stopped = service.stop(response.id)

    assert stopped.status == "stopped"
    assert stopped.url == ""
    assert process.terminated == [ProcessHandle(pid=100)]
    assert shortcuts.killed_windows == [("windows_cygwin", tmp_path.resolve(), "@1")]
    assert service.get(response.id).status == "stopped"
    assert service._repository.get_entry(response.id)[1].tmux_window_id is None
    assert service.get(response.id).tmux_session_name == response.tmux_session_name


def test_service_close_all_keeps_records_and_removes_windows_and_sessions(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    first = service.create(CreateSessionRequest(name="One", workspace=tmp_path, shortcut_id="claude-code"))
    second = service.create(CreateSessionRequest(name="Two", workspace=tmp_path, shortcut_id="claude-code"))

    response = service.close_all()
    sessions = service.list_sessions()

    assert response.stopped_count == 2
    assert response.tmux_session_count == 1
    assert process.terminated == [ProcessHandle(pid=100), ProcessHandle(pid=101)]
    assert shortcuts.killed_windows == [
        ("windows_cygwin", tmp_path.resolve(), "@1"),
        ("windows_cygwin", tmp_path.resolve(), "@2"),
    ]
    assert shortcuts.killed_sessions == [("windows_cygwin", tmp_path.resolve(), first.tmux_session_name)]
    assert [session.id for session in sessions] == [first.id, second.id]
    assert [session.status for session in sessions] == ["stopped", "stopped"]


def test_service_delete_last_entry_keeps_workspace_and_removes_workspace_session(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    service.delete(response.id)
    tree = service.list_tree()

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert process.terminated == [ProcessHandle(pid=100)]
    assert shortcuts.killed_windows == [("windows_cygwin", tmp_path.resolve(), "@1")]
    assert shortcuts.killed_sessions == [("windows_cygwin", tmp_path.resolve(), response.tmux_session_name)]
    assert service.list_sessions() == []
    assert len(cygwin.workspaces) == 1
    assert cygwin.workspaces[0].entries == []


def test_service_delete_one_entry_keeps_workspace_session(tmp_path: Path) -> None:
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, shortcut_service=shortcuts)
    first = service.create(CreateSessionRequest(name="One", workspace=tmp_path, shortcut_id="claude-code"))
    second = service.create(CreateSessionRequest(name="Two", workspace=tmp_path, shortcut_id="claude-code"))

    service.delete(first.id)

    assert shortcuts.killed_sessions == []
    assert [session.id for session in service.list_sessions()] == [second.id]


def test_service_delete_workspace_removes_entries_and_workspace_session(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    first = service.create(CreateSessionRequest(name="One", workspace=tmp_path, shortcut_id="claude-code"))
    service.create(CreateSessionRequest(name="Two", workspace=tmp_path, shortcut_id="claude-code"))

    service.delete_workspace(first.workspace_id)

    assert process.terminated == [ProcessHandle(pid=100), ProcessHandle(pid=101)]
    assert shortcuts.killed_windows == [
        ("windows_cygwin", tmp_path.resolve(), "@1"),
        ("windows_cygwin", tmp_path.resolve(), "@2"),
    ]
    assert shortcuts.killed_sessions == [("windows_cygwin", tmp_path.resolve(), first.tmux_session_name)]
    assert service.list_sessions() == []
    cygwin = next(environment for environment in service.list_tree().environments if environment.host == "windows_cygwin")
    assert cygwin.workspaces == []


def test_service_refresh_stops_entry_when_tmux_window_disappears(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    shortcuts.window_exists = False

    refreshed = service.get(response.id)

    assert refreshed.status == "stopped"
    assert refreshed.url == ""
    assert service.get(response.id).status == "stopped"


def test_service_starts_stopped_entry_with_existing_window(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    process.running = False
    stopped = service.get(response.id)

    started = service.start(stopped.id)

    assert started.status == "running"
    assert started.port == 9201
    assert [item[3] for item in shortcuts.created_windows] == ["Test"]
    assert process.started[-1][0][8] == f"tmux select-window -t @1 && exec tmux attach -t {response.tmux_session_name}"


def test_service_starts_stopped_entry_with_named_window_when_recorded_window_is_missing(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    process.running = False
    stopped = service.get(response.id)
    shortcuts.window_exists = False
    shortcuts.window_by_name = "@7"

    started = service.start(stopped.id)

    assert started.status == "running"
    assert started.port == 9201
    assert [item[3] for item in shortcuts.created_windows] == ["Test"]
    assert process.started[-1][0][8] == f"tmux select-window -t @7 && exec tmux attach -t {response.tmux_session_name}"


def test_service_starts_stopped_entry_with_new_window_when_existing_window_is_missing(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    process.running = False
    stopped = service.get(response.id)
    shortcuts.window_exists = False

    started = service.start(stopped.id)

    assert started.status == "running"
    assert started.port == 9201
    assert [item[3] for item in shortcuts.created_windows] == ["Test", "Test"]
    assert process.started[-1][0][8] == f"tmux select-window -t @2 && exec tmux attach -t {response.tmux_session_name}"


def test_service_rejects_start_when_shortcut_host_changed(tmp_path: Path) -> None:
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    stopped = service.stop(response.id)
    shortcuts.shortcut = shortcuts.shortcut.model_copy(update={"host": "windows_wsl"})

    with pytest.raises(InvalidTerminalConfigError, match="Shortcut host does not match session workspace"):
        service.start(stopped.id)


def test_service_start_running_entry_is_noop(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    started = service.start(response.id)

    assert started.id == response.id
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
    assert refreshed.url == ""


def test_service_lists_tree_grouped_by_environment_and_workspace(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    tree = service.list_tree()

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert cygwin.workspaces[0].id == response.workspace_id
    assert cygwin.workspaces[0].entries[0].id == response.id
