from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Literal, cast

import pytest

from termbridge.exceptions import InvalidTerminalConfigError, SessionTerminalUnavailableError, WorkspaceNotFoundError
from termbridge.models import (
    CreateSessionRequest,
    ReorderSessionsRequest,
    ReorderWorkspacesRequest,
    SessionStatus,
    Shortcut,
)
from termbridge.ports import PortAllocator
from termbridge.process import ProcessHandle
from termbridge.repositories import FileSessionRepository
from termbridge.runtime import RuntimeRegistry
from termbridge.services import (
    SessionService,
    TerminalService,
    TmuxListWindowsError,
    TmuxWindowListing,
    parse_tmux_window_line,
)
from termbridge.settings import Settings
from termbridge.ttyd import ttyd_client_options


class FakeProcessAdapter:
    def __init__(self) -> None:
        self.started: list[tuple[list[str], Path, Path | None, bool, Mapping[str, str] | None]] = []
        self.terminated: list[ProcessHandle] = []
        self.running = True
        self.next_pid = 100

    def start(
        self,
        command: list[str],
        cwd: Path,
        *,
        log_file: Path | None = None,
        suppress_output: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> ProcessHandle:
        self.started.append((command, cwd, log_file, suppress_output, env))
        handle = ProcessHandle(pid=self.next_pid)
        self.next_pid += 1
        return handle

    def terminate(self, handle: ProcessHandle) -> None:
        self.terminated.append(handle)

    def is_running(self, handle: ProcessHandle) -> bool:
        return self.running


class FailingProcessAdapter(FakeProcessAdapter):
    def start(
        self,
        command: list[str],
        cwd: Path,
        *,
        log_file: Path | None = None,
        suppress_output: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> ProcessHandle:
        raise RuntimeError("process failed")


class FakeShortcutService:
    def __init__(self, ttyd_executable: str = "custom-ttyd", runtime_env: Mapping[str, str] | None = None) -> None:
        self.ttyd_executable = ttyd_executable
        self.runtime_env = runtime_env
        self.created_windows: list[tuple[Shortcut, Path, str, str]] = []
        self.killed_windows: list[tuple[str, Path, str | None]] = []
        self.killed_sessions: list[tuple[str, Path, str]] = []
        self.window_exists = True
        self.window_exists_calls: list[tuple[str, Path, str | None]] = []
        self.listed_tmux_window_hosts: list[str] = []
        self.tmux_windows: dict[str, list[TmuxWindowListing]] = {}
        self.tmux_window_by_id: dict[str, TmuxWindowListing] = {}
        self.tmux_list_error: Exception | None = None
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
        tmux_window_id = f"@{len(self.created_windows)}"
        listing = TmuxWindowListing(tmux_session_name=tmux_session_name, window_index="0", window_name=window_name)
        self.tmux_windows.setdefault(shortcut.host, []).append(listing)
        self.tmux_window_by_id[tmux_window_id] = listing
        return tmux_window_id

    def build_tmux_attach_command(
        self, host: str, workspace: Path, *, tmux_session_name: str, tmux_window_id: str | None
    ) -> list[str]:
        return ["bash.exe", "-lc", f"tmux select-window -t {tmux_window_id} && exec tmux attach -t {tmux_session_name}"]

    def kill_tmux_window(self, host: str, workspace: Path, *, tmux_window_id: str | None) -> None:
        self.killed_windows.append((host, workspace, tmux_window_id))
        if tmux_window_id is not None:
            killed = self.tmux_window_by_id.pop(tmux_window_id, None)
            if killed is not None:
                self.tmux_windows[host] = [listing for listing in self.tmux_windows.get(host, []) if listing != killed]

    def kill_tmux_session(self, host: str, workspace: Path, *, tmux_session_name: str) -> None:
        self.killed_sessions.append((host, workspace, tmux_session_name))

    def tmux_window_exists(self, host: str, workspace: Path, *, tmux_window_id: str | None) -> bool:
        self.window_exists_calls.append((host, workspace, tmux_window_id))
        return self.window_exists

    def list_tmux_windows(self, host: str) -> list[TmuxWindowListing]:
        self.listed_tmux_window_hosts.append(host)
        if self.tmux_list_error is not None:
            raise self.tmux_list_error
        return self.tmux_windows.get(host, [])

    def find_tmux_window_by_name(
        self, host: str, workspace: Path, *, tmux_session_name: str, window_name: str
    ) -> str | None:
        return self.window_by_name

    def resolve_ttyd_executable(self, host: str, cygwin_bash_path: str | None = None) -> str:
        return self.ttyd_executable

    def runtime_process_env(self, host: str) -> Mapping[str, str] | None:
        return self.runtime_env


def make_service(
    tmp_path: Path,
    process: FakeProcessAdapter | None = None,
    *,
    shortcut_service: FakeShortcutService | None = None,
    ttyd_log_mode: Literal["none", "console", "file"] = "none",
    ttyd_interface: str = "127.0.0.1",
    ttyd_credential_mode: Literal["basic", "none"] = "basic",
    ttyd_credential_username: str = "termbridge",
    ttyd_credential_password: str = "",
    public_base_url: str | None = None,
    ttyd_writable: bool = True,
    ttyd_port_open: bool | Callable[[int], bool] = True,
) -> SessionService:
    settings = Settings(
        ttyd_executable="ttyd",
        host="127.0.0.1",
        port_start=9201,
        port_end=9205,
        state_dir=tmp_path / "state",
        public_base_url=public_base_url,
        ttyd_log_mode=ttyd_log_mode,
        ttyd_interface=ttyd_interface,
        ttyd_credential_mode=ttyd_credential_mode,
        ttyd_credential_username=ttyd_credential_username,
        ttyd_credential_password=ttyd_credential_password,
        ttyd_writable=ttyd_writable,
    )
    service = SessionService(
        settings=settings,
        repository=FileSessionRepository(settings.sessions_file),
        runtime_registry=RuntimeRegistry(),
        port_allocator=PortAllocator(settings.host, settings.port_start, settings.port_end),
        process_adapter=process or FakeProcessAdapter(),
        terminal_service=cast(TerminalService, shortcut_service or FakeShortcutService()),
    )
    service._ttyd_port_checker = ttyd_port_open if callable(ttyd_port_open) else lambda _port: ttyd_port_open
    return service


def record_ttyd_checks(ports: list[int], result: bool) -> Callable[[int], bool]:
    def check(port: int) -> bool:
        ports.append(port)
        return result

    return check



def assert_ttyd_client_options(command: list[str]) -> None:
    options = [command[index + 1] for index, item in enumerate(command) if item == "--client-option"]

    assert options == [f"{key}={value}" for key, value in ttyd_client_options().items()]
    assert any(option.startswith('theme={"background":"#020617"') for option in options)


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
    entry = service._repository.get_entry(response.id)[1]
    assert entry.ttyd_credential is not None
    assert entry.ttyd_credential.username == "termbridge"
    assert len(entry.ttyd_credential.password) >= 12
    assert response.url == f"/terminal/{response.id}/"
    command = process.started[0][0]
    assert command[:10] == [
        "custom-ttyd",
        "--writable",
        "--interface",
        "127.0.0.1",
        "--port",
        "9201",
        "--cwd",
        str(tmp_path.resolve()),
        "--credential",
        f"termbridge:{entry.ttyd_credential.password}",
    ]
    assert_ttyd_client_options(command)
    assert command[-3:] == [
        "bash.exe",
        "-lc",
        f"tmux select-window -t @1 && exec tmux attach -t {response.tmux_session_name}",
    ]
    assert process.started == [(command, tmp_path.resolve(), None, True, None)]


def test_service_uses_ttyd_log_file_when_file_mode_is_enabled(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process, ttyd_log_mode="file")

    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    assert process.started[0][2] == tmp_path / "state" / "logs" / "ttyd" / f"{response.id}.log"
    assert process.started[0][3] is False


def test_service_omits_ttyd_writable_flag_when_disabled(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process, ttyd_writable=False)

    service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    assert "--writable" not in process.started[0][0]


def test_service_omits_ttyd_credential_when_mode_is_none(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process, ttyd_credential_mode="none")

    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    command = process.started[0][0]
    entry = service._repository.get_entry(response.id)[1]

    assert "--credential" not in command
    assert response.url == f"/terminal/{response.id}/"
    assert entry.ttyd_credential is None


def test_service_uses_explicit_ttyd_credential_password(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(
        tmp_path,
        process,
        ttyd_credential_username="admin@example.test",
        ttyd_credential_password="p@ss word:123",
    )

    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    command = process.started[0][0]
    entry = service._repository.get_entry(response.id)[1]

    assert command[command.index("--credential") + 1] == "admin@example.test:p@ss word:123"
    assert response.url == f"/terminal/{response.id}/"
    assert entry.ttyd_credential is not None
    assert entry.ttyd_credential.username == "admin@example.test"
    assert entry.ttyd_credential.password == "p@ss word:123"


def test_service_reuses_generated_ttyd_credential_when_session_restarts(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    original = service._repository.get_entry(response.id)[1].ttyd_credential
    assert original is not None

    stopped = service.stop(response.id)
    restarted = service.start(stopped.id)
    restarted_credential = service._repository.get_entry(restarted.id)[1].ttyd_credential

    assert restarted_credential == original
    assert process.started[-1][0][process.started[-1][0].index("--credential") + 1] == f"termbridge:{original.password}"
    assert restarted.url == f"/terminal/{restarted.id}/"


def test_service_uses_configured_ttyd_interface(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process, ttyd_interface="192.0.2.10")

    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    command = process.started[0][0]
    credential = service._repository.get_entry(response.id)[1].ttyd_credential
    assert credential is not None

    assert command[command.index("--interface") + 1] == "192.0.2.10"
    assert response.url == f"/terminal/{response.id}/"


def test_service_builds_public_base_terminal_proxy_url(tmp_path: Path) -> None:
    service = make_service(tmp_path, public_base_url="http://example.test/base")

    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    assert response.url == f"http://example.test/base/terminal/{response.id}/"


def test_service_returns_terminal_proxy_target_for_running_session(tmp_path: Path) -> None:
    service = make_service(tmp_path, ttyd_credential_password="secret")
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    target = service.terminal_proxy_target(response.id)

    assert target.base_url == "http://127.0.0.1:9201"
    assert target.credential is not None
    assert target.credential.username == "termbridge"
    assert target.credential.password == "secret"


def test_service_rejects_terminal_proxy_target_for_stopped_session(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    stopped = service.stop(response.id)

    with pytest.raises(InvalidTerminalConfigError, match="not running"):
        service.terminal_proxy_target(stopped.id)


def test_service_replaces_generated_ttyd_credential_when_username_changes(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    original = service._repository.get_entry(response.id)[1].ttyd_credential
    assert original is not None
    stopped = service.stop(response.id)

    renamed_service = make_service(tmp_path, process, ttyd_credential_username="other-user")
    restarted = renamed_service.start(stopped.id)
    updated = renamed_service._repository.get_entry(restarted.id)[1].ttyd_credential
    assert updated is not None

    assert updated.username == "other-user"
    assert updated.password != original.password
    assert process.started[-1][0][process.started[-1][0].index("--credential") + 1] == f"other-user:{updated.password}"
    assert restarted.url == f"/terminal/{restarted.id}/"


def test_service_uses_console_ttyd_log_mode_when_enabled(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process, ttyd_log_mode="console")

    service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    assert process.started[0][2] is None
    assert process.started[0][3] is False


def test_service_passes_runtime_env_to_ttyd_process(tmp_path: Path) -> None:
    runtime_env = {"PATH": "D:/ProgramFiles/Cygwin/bin;C:/Program Files/Git/usr/bin"}
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process, shortcut_service=FakeShortcutService(runtime_env=runtime_env))

    service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    assert process.started[0][4] == runtime_env


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
    cygwin = next(
        environment for environment in service.list_tree().environments if environment.host == "windows_cygwin"
    )
    assert cygwin.workspaces == []


def test_service_refresh_disconnects_entry_when_ttyd_port_closes(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts, ttyd_port_open=False)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    refreshed = service.get(response.id)
    entry = service._repository.get_entry(response.id)[1]

    assert refreshed.status == SessionStatus.DISCONNECTED
    assert refreshed.url == f"/terminal/{response.id}/"
    assert entry.pid == 100
    assert entry.tmux_window_id == "@1"


def test_service_refresh_keeps_running_when_ttyd_port_is_open_without_process_cache(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    _, entry = service._repository.get_entry(response.id)
    service = make_service(tmp_path, FakeProcessAdapter())
    service._repository.update_entry(entry.model_copy(update={"status": SessionStatus.DISCONNECTED, "pid": None, "url": ""}))

    refreshed = service.get(response.id)

    assert refreshed.status == SessionStatus.RUNNING
    assert refreshed.url == ""


def test_service_refresh_stops_entry_when_tmux_window_disappears(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    shortcuts.window_exists = False

    refreshed = service.get(response.id)
    entry = service._repository.get_entry(response.id)[1]

    assert refreshed.status == SessionStatus.STOPPED
    assert refreshed.url == f"/terminal/{response.id}/"
    assert entry.pid == 100
    assert entry.tmux_window_id == "@1"
    assert service.get(response.id).status == SessionStatus.STOPPED


def test_service_refresh_promotes_stopped_entry_with_existing_window_to_disconnected(tmp_path: Path) -> None:
    service = make_service(tmp_path, ttyd_port_open=False)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    _, entry = service._repository.get_entry(response.id)
    service._repository.update_entry(entry.model_copy(update={"status": SessionStatus.STOPPED, "pid": None, "url": ""}))

    refreshed = service.get(response.id)

    assert refreshed.status == SessionStatus.DISCONNECTED
    assert service._repository.get_entry(response.id)[1].tmux_window_id == "@1"


def test_service_refresh_stops_disconnected_entry_when_tmux_window_disappears(tmp_path: Path) -> None:
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    _, entry = service._repository.get_entry(response.id)
    service._repository.update_entry(
        entry.model_copy(update={"status": SessionStatus.DISCONNECTED, "pid": None, "url": ""})
    )
    shortcuts.window_exists = False

    refreshed = service.get(response.id)

    assert refreshed.status == SessionStatus.STOPPED
    assert service._repository.get_entry(response.id)[1].tmux_window_id == "@1"


def test_service_rejects_terminal_proxy_for_disconnected_entry(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process, ttyd_port_open=False)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    disconnected = service.get(response.id)

    with pytest.raises(SessionTerminalUnavailableError):
        service.terminal_proxy_target(disconnected.id)


def test_service_starts_disconnected_entry_with_existing_window(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    service._ttyd_port_checker = lambda _port: False
    stopped = service.get(response.id)

    started = service.start(stopped.id)

    assert started.status == "running"
    assert started.port == 9201
    assert [item[3] for item in shortcuts.created_windows] == ["Test"]
    assert process.started[-1][0][-1] == f"tmux select-window -t @1 && exec tmux attach -t {response.tmux_session_name}"


def test_service_starts_stopped_entry_with_named_window_when_recorded_window_is_missing(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    service._ttyd_port_checker = lambda _port: False
    stopped = service.get(response.id)
    shortcuts.window_exists = False
    shortcuts.window_by_name = "@7"

    started = service.start(stopped.id)

    assert started.status == "running"
    assert started.port == 9201
    assert [item[3] for item in shortcuts.created_windows] == ["Test"]
    assert process.started[-1][0][-1] == f"tmux select-window -t @7 && exec tmux attach -t {response.tmux_session_name}"


def test_service_starts_stopped_entry_with_new_window_when_existing_window_is_missing(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, process, shortcut_service=shortcuts)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    service._ttyd_port_checker = lambda _port: False
    stopped = service.get(response.id)
    shortcuts.window_exists = False

    started = service.start(stopped.id)

    assert started.status == "running"
    assert started.port == 9201
    assert [item[3] for item in shortcuts.created_windows] == ["Test", "Test"]
    assert process.started[-1][0][-1] == f"tmux select-window -t @2 && exec tmux attach -t {response.tmux_session_name}"


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


def test_service_lists_tree_grouped_by_environment_and_workspace(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    tree = service.list_tree()

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert cygwin.workspaces[0].id == response.workspace_id
    assert cygwin.workspaces[0].status == SessionStatus.RUNNING
    assert cygwin.workspaces[0].entries[0].id == response.id


def test_service_list_tree_reports_disconnected_workspace_status(tmp_path: Path) -> None:
    process = FakeProcessAdapter()
    service = make_service(tmp_path, process, ttyd_port_open=False)
    service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    tree = service.list_tree()

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert cygwin.workspaces[0].status == SessionStatus.DISCONNECTED
    assert cygwin.workspaces[0].entries[0].status == SessionStatus.DISCONNECTED


def test_parse_tmux_window_line_cleans_default_output() -> None:
    listing = parse_tmux_window_line("tb_cyg_3d134fa1d1d50ef3:0: 特性开发* (1 panes) [230x54]")

    assert listing == TmuxWindowListing(
        tmux_session_name="tb_cyg_3d134fa1d1d50ef3",
        window_index="0",
        window_name="特性开发",
    )
    assert parse_tmux_window_line("not-a-tmux-window-line") is None



def test_service_list_tree_refresh_false_skips_status_checks(tmp_path: Path) -> None:
    shortcuts = FakeShortcutService()
    ttyd_checked_ports: list[int] = []
    service = make_service(
        tmp_path,
        shortcut_service=shortcuts,
        ttyd_port_open=record_ttyd_checks(ttyd_checked_ports, False),
    )
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    _, entry = service._repository.get_entry(response.id)
    service._repository.update_entry(entry.model_copy(update={"status": SessionStatus.DISCONNECTED, "pid": None, "url": ""}))

    tree = service.list_tree(refresh=False)

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert cygwin.workspaces[0].entries[0].status == SessionStatus.DISCONNECTED
    assert shortcuts.listed_tmux_window_hosts == []
    assert shortcuts.window_exists_calls == []
    assert ttyd_checked_ports == []



def test_service_list_tree_uses_one_tmux_listing_per_host(tmp_path: Path) -> None:
    shortcuts = FakeShortcutService()
    service = make_service(tmp_path, shortcut_service=shortcuts)
    service.create(CreateSessionRequest(name="One", workspace=tmp_path, shortcut_id="claude-code"))
    service.create(CreateSessionRequest(name="Two", workspace=tmp_path, shortcut_id="claude-code"))

    tree = service.list_tree()

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert [entry.status for entry in cygwin.workspaces[0].entries] == [SessionStatus.RUNNING, SessionStatus.RUNNING]
    assert shortcuts.listed_tmux_window_hosts == ["windows_cygwin"]
    assert shortcuts.window_exists_calls == []



def test_service_list_tree_stops_missing_tmux_window_without_ttyd_check(tmp_path: Path) -> None:
    shortcuts = FakeShortcutService()
    ttyd_checked_ports: list[int] = []
    service = make_service(
        tmp_path,
        shortcut_service=shortcuts,
        ttyd_port_open=record_ttyd_checks(ttyd_checked_ports, True),
    )
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    shortcuts.tmux_windows["windows_cygwin"] = []

    tree = service.list_tree()
    entry = service._repository.get_entry(response.id)[1]

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert cygwin.workspaces[0].entries[0].status == SessionStatus.STOPPED
    assert entry.tmux_window_id == "@1"
    assert ttyd_checked_ports == []



def test_service_list_tree_marks_existing_window_without_ttyd_as_disconnected(tmp_path: Path) -> None:
    service = make_service(tmp_path, ttyd_port_open=False)
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))

    tree = service.list_tree()

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert cygwin.workspaces[0].entries[0].status == SessionStatus.DISCONNECTED
    assert service._repository.get_entry(response.id)[1].tmux_window_id == "@1"



def test_service_list_tree_keeps_status_when_tmux_listing_fails(tmp_path: Path) -> None:
    shortcuts = FakeShortcutService()
    ttyd_checked_ports: list[int] = []
    service = make_service(
        tmp_path,
        shortcut_service=shortcuts,
        ttyd_port_open=record_ttyd_checks(ttyd_checked_ports, False),
    )
    response = service.create(CreateSessionRequest(name="Test", workspace=tmp_path, shortcut_id="claude-code"))
    shortcuts.tmux_list_error = TmuxListWindowsError("tmux failed")

    tree = service.list_tree()
    entry = service._repository.get_entry(response.id)[1]

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert cygwin.workspaces[0].entries[0].status == SessionStatus.RUNNING
    assert entry.tmux_window_id == "@1"
    assert ttyd_checked_ports == []



def test_service_reorders_workspaces_in_environment(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = service.create(CreateSessionRequest(name="One", workspace=first_dir, shortcut_id="claude-code"))
    second = service.create(CreateSessionRequest(name="Two", workspace=second_dir, shortcut_id="claude-code"))

    tree = service.reorder_workspaces(
        "windows_cygwin",
        ReorderWorkspacesRequest(workspace_ids=[second.workspace_id, first.workspace_id]),
    )

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert [workspace.id for workspace in cygwin.workspaces] == [second.workspace_id, first.workspace_id]


def test_service_reorders_sessions_in_workspace(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    first = service.create(CreateSessionRequest(name="One", workspace=tmp_path, shortcut_id="claude-code"))
    second = service.create(CreateSessionRequest(name="Two", workspace=tmp_path, shortcut_id="claude-code"))

    tree = service.reorder_sessions(
        first.workspace_id,
        ReorderSessionsRequest(session_ids=[second.id, first.id]),
    )

    cygwin = next(environment for environment in tree.environments if environment.host == "windows_cygwin")
    assert [session.id for session in cygwin.workspaces[0].entries] == [second.id, first.id]


def test_service_rejects_incomplete_session_order(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    first = service.create(CreateSessionRequest(name="One", workspace=tmp_path, shortcut_id="claude-code"))
    service.create(CreateSessionRequest(name="Two", workspace=tmp_path, shortcut_id="claude-code"))

    with pytest.raises(InvalidTerminalConfigError, match="Session order"):
        service.reorder_sessions(first.workspace_id, ReorderSessionsRequest(session_ids=[first.id]))
