import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from termbridge.exceptions import InvalidTerminalConfigError
from termbridge.models import (
    CreateShortcutRequest,
    LinuxSettings,
    RuntimeCheckResponse,
    TerminalState,
    UpdateShortcutRequest,
    UpdateTerminalSettingsRequest,
    WindowsCygwinSettings,
    WindowsWslSettings,
)
from termbridge.repositories import FileTerminalRepository
from termbridge.services import TerminalService


def make_service(tmp_path: Path) -> TerminalService:
    return TerminalService(FileTerminalRepository(tmp_path / "terminals.json"))


def _tmux_available() -> RuntimeCheckResponse:
    return RuntimeCheckResponse(available=True, path="/usr/bin/tmux", version="tmux 3.2")


def test_shortcut_service_initializes_default_shortcuts(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    shortcuts = service.list_shortcuts().shortcuts

    assert [(shortcut.id, shortcut.command, shortcut.host) for shortcut in shortcuts] == [
        ("cygwin-bash", "bash", "windows_cygwin"),
        ("cygwin-cmd", "cmd", "windows_cygwin"),
        ("cygwin-claude-code", "claude --dangerously-skip-permissions", "windows_cygwin"),
        ("cygwin-codex", "codex -a never --sandbox danger-full-access", "windows_cygwin"),
        ("wsl-bash", "bash", "windows_wsl"),
        ("wsl-claude-code", "claude --dangerously-skip-permissions", "windows_wsl"),
        ("wsl-codex", "codex -a never --sandbox danger-full-access", "windows_wsl"),
    ]


def test_shortcut_service_creates_and_persists_shortcut(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    shortcut = service.create_shortcut(
        CreateShortcutRequest(name="Agent", command="agent run", host="windows_cygwin", description="Run agent")
    )

    restored = make_service(tmp_path).list_shortcuts().shortcuts
    by_id = {item.id: item for item in restored}
    assert by_id[shortcut.id].command == "agent run"
    assert by_id[shortcut.id].description == "Run agent"


def test_shortcut_service_updates_shortcut(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    shortcut = service.create_shortcut(CreateShortcutRequest(name="Agent", command="agent run", host="windows_cygwin"))

    updated = service.update_shortcut(shortcut.id, UpdateShortcutRequest(command="agent run --verbose"))

    assert updated.command == "agent run --verbose"


def test_shortcut_service_rejects_duplicate_name_in_same_host(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_shortcut(CreateShortcutRequest(name="Agent", command="agent run", host="windows_cygwin"))

    with pytest.raises(InvalidTerminalConfigError, match="Shortcut name already exists"):
        service.create_shortcut(CreateShortcutRequest(name="Agent", command="agent other", host="windows_cygwin"))

    shortcut = service.create_shortcut(CreateShortcutRequest(name="Agent", command="agent run", host="windows_wsl"))

    assert shortcut.name == "Agent"


def test_shortcut_service_rejects_duplicate_name_when_updating_host(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_shortcut(CreateShortcutRequest(name="Agent", command="agent run", host="windows_cygwin"))
    other = service.create_shortcut(CreateShortcutRequest(name="Other", command="agent other", host="windows_wsl"))

    with pytest.raises(InvalidTerminalConfigError, match="Shortcut name already exists"):
        service.update_shortcut(other.id, UpdateShortcutRequest(name="Agent", host="windows_cygwin"))


def test_shortcut_service_deletes_default_shortcut(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    service.delete_shortcut("cygwin-codex")

    assert "cygwin-codex" not in {shortcut.id for shortcut in service.list_shortcuts().shortcuts}


def test_shortcut_service_rejects_blank_command(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(InvalidTerminalConfigError, match="Shortcut command is required"):
        service.create_shortcut(CreateShortcutRequest(name="Blank", command="   ", host="windows_cygwin"))


def test_shortcut_service_requires_wsl_ready_for_wsl_host(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    shortcut = service.create_shortcut(CreateShortcutRequest(name="WSL", command="bash", host="windows_wsl"))

    with pytest.raises(InvalidTerminalConfigError, match="Windows/WSL environment is not ready"):
        service.resolve_shortcut_command(shortcut.id, tmp_path, tmux_session_name="sess_test")


def test_shortcut_service_ignores_old_terminal_definitions(tmp_path: Path) -> None:
    repository = FileTerminalRepository(tmp_path / "terminals.json")
    repository.save_state(TerminalState.model_validate({"user_terminals": [{"id": "old", "name": "Old"}]}))

    shortcuts = TerminalService(repository).list_shortcuts().shortcuts

    assert {shortcut.id for shortcut in shortcuts} == {
        "cygwin-bash",
        "cygwin-cmd",
        "cygwin-claude-code",
        "cygwin-codex",
        "wsl-bash",
        "wsl-claude-code",
        "wsl-codex",
    }


def test_shortcut_service_resolves_windows_cygwin_command(tmp_path: Path) -> None:
    repository = FileTerminalRepository(tmp_path / "terminals.json")
    state = repository.get_state()
    state.windows_cygwin_settings = WindowsCygwinSettings(readiness="ready", bash_path="bash.exe")
    repository.save_state(state)
    service = TerminalService(repository)
    shortcut = service.create_shortcut(CreateShortcutRequest(name="Agent", command="agent run", host="windows_cygwin"))

    with patch.object(service, "resolve_ttyd_executable", return_value="ttyd"):
        command, resolved, cleanup_command = service.resolve_shortcut_command(
            shortcut.id, tmp_path / "workspace with spaces", tmux_session_name="sess_test"
        )

    workspace_path = str(tmp_path / "workspace with spaces").replace("\\", "/")
    assert resolved.id == shortcut.id
    assert cleanup_command == ["bash.exe", "-lc", "tmux kill-session -t sess_test"]
    assert command == ["bash.exe", "-lc", f"cd {workspace_path!r} && exec tmux new-session -A -s sess_test 'agent run'"]


def test_shortcut_service_resolves_windows_wsl_command(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.update_windows_wsl_settings(WindowsWslSettings(readiness="ready", wsl_path="wsl", tmux_path="/usr/bin/tmux"))
    shortcut = service.create_shortcut(CreateShortcutRequest(name="WSL", command="agent run", host="windows_wsl"))
    workspace = Path(r"D:\SourceCodes\agentic\cc-switch")

    with patch.object(service, "resolve_ttyd_executable", return_value="ttyd"):
        with patch("termbridge.services.subprocess.run") as run:
            command, resolved, cleanup_command = service.resolve_shortcut_command(
                shortcut.id, workspace, tmux_session_name="sess_test"
            )

    run.assert_not_called()
    assert resolved.id == shortcut.id
    assert cleanup_command == ["wsl", "sh", "-lc", "tmux kill-session -t sess_test"]
    assert command == [
        "wsl",
        "--cd",
        str(workspace),
        "sh",
        "-lc",
        "exec tmux new-session -A -s sess_test 'agent run'",
    ]


def test_terminal_service_creates_wsl_tmux_window_from_wsl_cd_workspace(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.update_windows_wsl_settings(WindowsWslSettings(readiness="ready", wsl_path="wsl", tmux_path="/usr/bin/tmux"))
    shortcut = service.create_shortcut(CreateShortcutRequest(name="WSL", command="agent run", host="windows_wsl"))
    workspace = Path(r"D:\SourceCodes\agentic\cc-switch")
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="@3\n", stderr="")

    with patch("termbridge.services.subprocess.run", return_value=completed) as run:
        window_id = service.create_tmux_window(
            shortcut,
            workspace,
            tmux_session_name="tb_wsl_workspace",
            window_name="Agent",
        )

    assert window_id == "@3"
    run.assert_called_once()
    command = run.call_args.args[0]
    assert command[:4] == ["wsl", "--cd", str(workspace), "sh"]
    assert f"-c {workspace}" not in command[5]
    assert "tmux new-session -d -s tb_wsl_workspace -c ." in command[5]
    assert "tmux new-window -P -F '#{window_id}' -t tb_wsl_workspace -n Agent -c . 'agent run'" in command[5]


def test_shortcut_service_resolves_linux_command_when_ready(tmp_path: Path) -> None:
    repository = FileTerminalRepository(tmp_path / "terminals.json")
    service = TerminalService(repository)
    state = repository.get_state()
    state.linux_settings = LinuxSettings(readiness="ready", shell_path="/bin/sh", tmux_path="/usr/bin/tmux")
    repository.save_state(state)
    shortcut = service.create_shortcut(CreateShortcutRequest(name="Linux", command="agent run", host="linux"))

    with patch.object(service, "resolve_ttyd_executable", return_value="ttyd"):
        command, resolved, cleanup_command = service.resolve_shortcut_command(
            shortcut.id, tmp_path / "workspace with spaces", tmux_session_name="sess_test"
        )

    assert resolved.id == shortcut.id
    assert cleanup_command == ["/bin/sh", "-lc", "tmux kill-session -t sess_test"]
    assert command[:2] == ["/bin/sh", "-lc"]
    assert "exec tmux new-session -A -s sess_test 'agent run'" in command[2]


def test_shortcut_service_requires_cygwin_ready_for_host_ready(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(InvalidTerminalConfigError, match="Windows/Cygwin environment is not ready"):
        service.resolve_shortcut_command("cygwin-claude-code", tmp_path, tmux_session_name="sess_test")


def test_shortcut_service_normalizes_tmux_session_name(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    assert service.normalize_tmux_session_name("hello world/测试", "fallback") == "hello-world"
    assert service.normalize_tmux_session_name("测试", "fallback") == "fallback"


def test_terminal_service_persists_ttyd_settings(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    service.update_settings(UpdateTerminalSettingsRequest(ttyd_mode="explicit", ttyd_path="D:/ttyd.exe"))

    settings = make_service(tmp_path).get_settings()
    assert settings.ttyd_mode == "explicit"
    assert settings.ttyd_path == "D:/ttyd.exe"



def test_terminal_service_lists_environments(tmp_path: Path) -> None:
    repository = FileTerminalRepository(tmp_path / "terminals.json")
    service = TerminalService(repository)
    state = repository.get_state()
    state.windows_cygwin_settings = WindowsCygwinSettings(readiness="ready", bash_path="bash.exe")
    repository.save_state(state)

    with patch("termbridge.services.os.name", "nt"):
        response = service.list_environments()

    by_host = {environment.host: environment for environment in response.environments}
    assert by_host["windows_cygwin"].readiness == "ready"
    assert by_host["windows_cygwin"].available_on_host is True
    assert by_host["windows_wsl"].available_on_host is True
    assert by_host["linux"].available_on_host is False


def test_terminal_service_rejects_explicit_ttyd_without_path(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(InvalidTerminalConfigError):
        service.update_settings(UpdateTerminalSettingsRequest(ttyd_mode="explicit"))


def test_terminal_service_persists_cygwin_settings(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    service.update_windows_cygwin_settings(
        service.get_windows_cygwin_settings().model_copy(update={"bash_path": "bash.exe"})
    )

    settings = make_service(tmp_path).get_windows_cygwin_settings()
    assert settings.bash_path == "bash.exe"


def test_terminal_service_preserves_cygwin_readiness_when_paths_do_not_change(tmp_path: Path) -> None:
    repository = FileTerminalRepository(tmp_path / "terminals.json")
    state = repository.get_state()
    state.windows_cygwin_settings = WindowsCygwinSettings(
        readiness="ready", bash_path="bash.exe", tmux_path="tmux.exe"
    )
    repository.save_state(state)
    service = TerminalService(repository)

    settings = service.update_windows_cygwin_settings(
        WindowsCygwinSettings(readiness="not_ready", bash_path="bash.exe", tmux_path="tmux.exe")
    )

    assert settings.readiness == "ready"
    assert settings.bash_path == "bash.exe"


def test_terminal_service_resets_cygwin_readiness_when_paths_change(tmp_path: Path) -> None:
    repository = FileTerminalRepository(tmp_path / "terminals.json")
    state = repository.get_state()
    state.windows_cygwin_settings = WindowsCygwinSettings(
        readiness="ready", bash_path="old-bash.exe", tmux_path="old-tmux.exe"
    )
    repository.save_state(state)
    service = TerminalService(repository)

    settings = service.update_windows_cygwin_settings(
        WindowsCygwinSettings(readiness="ready", bash_path="new-bash.exe", tmux_path="old-tmux.exe")
    )

    assert settings.readiness == "not_ready"
    assert settings.checked_at is None
    assert settings.bash_path == "new-bash.exe"


def test_terminal_service_detects_ttyd_success(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    completed = subprocess.CompletedProcess(args=["ttyd", "--version"], returncode=0, stdout="ttyd 1.7.7\n", stderr="")

    with patch("termbridge.services.subprocess.run", return_value=completed):
        result = service.check_ttyd("ttyd")

    assert result.available is True
    assert result.path == "ttyd"
    assert result.version == "ttyd 1.7.7"


def test_terminal_service_detects_ttyd_unavailable(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with patch("termbridge.services.shutil.which", return_value=None):
        result = service.check_ttyd()

    assert result.available is False
    assert result.reason == "ttyd is not available in PATH"


def test_terminal_service_detects_ttyd_exe_first_on_windows(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    completed = subprocess.CompletedProcess(
        args=["D:/cygwin/bin/ttyd.exe", "--version"], returncode=0, stdout="ttyd 1.7.7\n", stderr=""
    )

    with patch("termbridge.services.os.name", "nt"):
        with patch("termbridge.services.shutil.which", side_effect=["D:/cygwin/bin/ttyd.EXE"]):
            with patch("termbridge.services.subprocess.run", return_value=completed):
                result = service.check_ttyd()

    assert result.available is True
    assert result.path == "D:/cygwin/bin/ttyd.exe"


def test_terminal_service_resolves_ttyd_from_windows_path_for_cygwin_host(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with patch("termbridge.services.os.name", "nt"):
        with patch("termbridge.services.shutil.which", side_effect=["D:/tools/ttyd.exe"]):
            with patch("termbridge.services.subprocess.run") as run:
                result = service.resolve_ttyd_executable("windows_cygwin", "D:/ProgramFiles/Cygwin64/bin/bash.exe")

    assert result == "D:/tools/ttyd.exe"
    run.assert_not_called()


def test_terminal_service_detects_cygwin_and_tmux(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.update_windows_cygwin_settings(
        service.get_windows_cygwin_settings().model_copy(update={"bash_path": "/usr/bin/bash"})
    )
    bash = subprocess.CompletedProcess(
        args=["bash.exe", "-lc", "cygpath -w $(command -v bash) && bash --version"],
        returncode=0,
        stdout="D:\\ProgramFiles\\Cygwin64\\bin\\bash.exe\nGNU bash 5.2\n",
        stderr="",
    )

    with patch.object(service, "_check_cygwin_tmux", return_value=_tmux_available()):
        with patch("termbridge.services.subprocess.run", return_value=bash):
            result = service.check_windows_cygwin("bash.exe")

    settings = make_service(tmp_path).get_windows_cygwin_settings()
    assert result.bash.available is True
    assert result.bash.path == "D:\\ProgramFiles\\Cygwin64\\bin\\bash.exe"
    assert result.tmux is not None
    assert result.tmux.version == "tmux 3.2"
    assert settings.readiness == "ready"
    assert settings.tmux_path == "/usr/bin/tmux"


def test_terminal_service_ignores_persisted_cygwin_unix_path(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.update_windows_cygwin_settings(
        service.get_windows_cygwin_settings().model_copy(update={"bash_path": "/usr/bin/bash"})
    )

    with patch("termbridge.services.shutil.which", return_value=None):
        with patch("termbridge.services.Path.exists", return_value=False):
            result = service.check_windows_cygwin()

    assert result.bash.available is False
    assert result.bash.reason == "Cygwin bash was not found"


def test_terminal_service_detects_windows_wsl_and_tmux(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    wsl_path = "C:/WINDOWS/system32/wsl.exe"
    wsl = subprocess.CompletedProcess(
        args=[wsl_path, "--version"],
        returncode=0,
        stdout=(
            "W\x00S\x00L\x00 \x00v\x00e\x00r\x00s\x00i\x00o\x00n\x00:\x00 \x002\x00.\x004\x00.\x001\x002\x00.\x000\x00\n"
            "Kernel version: 5.15.167.4-1\n"
            "WSLg version: 1.0.65\n"
        ),
        stderr="",
    )
    tmux = subprocess.CompletedProcess(
        args=[wsl_path, "sh", "-lc", "command -v tmux && tmux -V"],
        returncode=0,
        stdout="/usr/bin/tmux\ntmux 3.2\n",
        stderr="",
    )

    with patch("termbridge.services.os.name", "nt"):
        with patch("termbridge.services.shutil.which", return_value="C:/WINDOWS/system32/wsl.EXE"):
            with patch("termbridge.services.subprocess.run", side_effect=[wsl, tmux]):
                result = service.check_windows_wsl()

    settings = make_service(tmp_path).get_windows_wsl_settings()
    assert result.wsl.available is True
    assert result.wsl.path == wsl_path
    assert result.wsl.version == "WSL version: 2.4.12.0"
    assert result.tmux is not None
    assert result.tmux.path == "/usr/bin/tmux"
    assert result.tmux.version == "tmux 3.2"
    assert settings.readiness == "ready"
    assert settings.wsl_path == wsl_path
    assert settings.wsl_version == "WSL version: 2.4.12.0"
    assert settings.tmux_path == "/usr/bin/tmux"
    assert settings.tmux_version == "tmux 3.2"


def test_terminal_service_reports_linux_unavailable_on_non_linux_host(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with patch("termbridge.services.platform.system", return_value="Windows"):
        result = service.check_linux()

    assert result.host.available is False
    assert result.host.reason == "Linux environment is unavailable on this host"
    assert result.shell is None
    assert result.tmux is None
