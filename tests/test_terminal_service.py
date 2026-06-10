import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from termbridge.exceptions import InvalidTerminalConfigError
from termbridge.models import (
    CreateShortcutRequest,
    TerminalState,
    TmuxAvailabilityResponse,
    UpdateShortcutRequest,
    UpdateTerminalSettingsRequest,
    WindowsCygwinSettings,
)
from termbridge.repositories import FileTerminalRepository
from termbridge.services import TerminalService


def make_service(tmp_path: Path) -> TerminalService:
    return TerminalService(FileTerminalRepository(tmp_path / "terminals.json"))


def _tmux_available() -> TmuxAvailabilityResponse:
    return TmuxAvailabilityResponse(available=True, path="/usr/bin/tmux", version="tmux 3.2")


def test_shortcut_service_initializes_default_shortcuts(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    shortcuts = service.list_shortcuts().shortcuts

    assert [(shortcut.id, shortcut.command, shortcut.host) for shortcut in shortcuts] == [
        ("bash", "bash", "windows_cygwin"),
        ("cmd", "cmd", "windows_cygwin"),
        ("claude-code", "claude --dangerously-skip-permissions", "windows_cygwin"),
        ("codex", "codex -a never --sandbox danger-full-access", "windows_cygwin"),
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


def test_shortcut_service_deletes_default_shortcut(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    service.delete_shortcut("codex")

    assert "codex" not in {shortcut.id for shortcut in service.list_shortcuts().shortcuts}


def test_shortcut_service_rejects_blank_command(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(InvalidTerminalConfigError, match="Shortcut command is required"):
        service.create_shortcut(CreateShortcutRequest(name="Blank", command="   ", host="windows_cygwin"))


def test_shortcut_service_rejects_unsupported_startup_host(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    shortcut = service.create_shortcut(CreateShortcutRequest(name="WSL", command="bash", host="windows_wsl"))

    with pytest.raises(InvalidTerminalConfigError, match="not supported"):
        service.resolve_shortcut_command(shortcut.id, tmp_path, tmux_session_name="sess_test")


def test_shortcut_service_ignores_old_terminal_definitions(tmp_path: Path) -> None:
    repository = FileTerminalRepository(tmp_path / "terminals.json")
    repository.save_state(TerminalState.model_validate({"user_terminals": [{"id": "old", "name": "Old"}]}))

    shortcuts = TerminalService(repository).list_shortcuts().shortcuts

    assert {shortcut.id for shortcut in shortcuts} == {"bash", "cmd", "claude-code", "codex"}


def test_shortcut_service_resolves_windows_cygwin_command(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.update_windows_cygwin_settings(WindowsCygwinSettings(bash_path="bash.exe"))
    shortcut = service.create_shortcut(CreateShortcutRequest(name="Agent", command="agent run", host="windows_cygwin"))

    with patch.object(service, "resolve_ttyd_executable", return_value="ttyd"):
        command, resolved, bash_path = service.resolve_shortcut_command(
            shortcut.id, tmp_path / "workspace with spaces", tmux_session_name="sess_test"
        )

    workspace_path = str(tmp_path / "workspace with spaces").replace("\\", "/")
    assert resolved.id == shortcut.id
    assert bash_path == "bash.exe"
    assert command == ["bash.exe", "-lc", f"cd {workspace_path!r} && exec tmux new-session -A -s sess_test 'agent run'"]


def test_shortcut_service_requires_cygwin_bash_for_host_ready(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(InvalidTerminalConfigError, match="Cygwin bash path is required"):
        service.resolve_shortcut_command("claude-code", tmp_path, tmux_session_name="sess_test")


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


def test_terminal_service_detects_tmux_success(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    completed = subprocess.CompletedProcess(
        args=["bash.exe", "-lc", "cygpath -w $(command -v tmux) && tmux -V"],
        returncode=0,
        stdout="D:\\ProgramFiles\\Cygwin64\\bin\\tmux.exe\ntmux 3.2\n",
        stderr="",
    )

    with patch("termbridge.services.subprocess.run", return_value=completed):
        result = service.check_tmux("bash.exe")

    assert result.available is True
    assert result.path == "D:\\ProgramFiles\\Cygwin64\\bin\\tmux.exe"
    assert result.version == "tmux 3.2"


def test_terminal_service_detects_tmux_unavailable(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    completed = subprocess.CompletedProcess(
        args=["bash.exe", "-lc", "cygpath -w $(command -v tmux) && tmux -V"],
        returncode=1,
        stdout="",
        stderr="tmux: command not found",
    )

    with patch("termbridge.services.subprocess.run", return_value=completed):
        result = service.check_tmux("bash.exe")

    assert result.available is False
    assert result.reason == "tmux: command not found"


def test_terminal_service_detects_tmux_timeout(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with patch("termbridge.services.subprocess.run", side_effect=subprocess.TimeoutExpired("bash.exe", 5)):
        result = service.check_tmux("bash.exe")

    assert result.available is False
    assert result.reason == "tmux detection timed out"


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

    with patch.object(service, "check_tmux", return_value=_tmux_available()):
        with patch("termbridge.services.subprocess.run", return_value=bash):
            result = service.check_windows_cygwin("bash.exe")

    assert result.bash.available is True
    assert result.bash.path == "D:\\ProgramFiles\\Cygwin64\\bin\\bash.exe"
    assert result.tmux is not None
    assert result.tmux.version == "tmux 3.2"


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
    wsl = subprocess.CompletedProcess(args=["wsl", "--status"], returncode=0, stdout="Default Version: 2\n", stderr="")
    tmux = subprocess.CompletedProcess(
        args=["wsl", "sh", "-lc", "command -v tmux && tmux -V"],
        returncode=0,
        stdout="/usr/bin/tmux\ntmux 3.2\n",
        stderr="",
    )

    with patch("termbridge.services.shutil.which", return_value="wsl"):
        with patch("termbridge.services.subprocess.run", side_effect=[wsl, tmux]):
            result = service.check_windows_wsl()

    assert result.wsl.available is True
    assert result.tmux is not None
    assert result.tmux.path == "/usr/bin/tmux"
    assert result.tmux.version == "tmux 3.2"


def test_terminal_service_reports_linux_unavailable_on_non_linux_host(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with patch("termbridge.services.platform.system", return_value="Windows"):
        result = service.check_linux()

    assert result.host.available is False
    assert result.host.reason == "Linux environment is unavailable on this host"
    assert result.shell is None
    assert result.tmux is None
