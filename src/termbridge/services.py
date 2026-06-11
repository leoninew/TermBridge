from __future__ import annotations

import ctypes
import hashlib
import logging
import os
import platform
import re
import shlex
import shutil
import subprocess
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from termbridge.exceptions import (
    InvalidTerminalConfigError,
    SessionNotFoundError,
    ShortcutNotFoundError,
    WorkspaceBrowserError,
    WorkspaceNotFoundError,
    WorkspacePathNotDirectoryError,
    WorkspacePathNotFoundError,
)
from termbridge.models import (
    CloseAllSessionsResponse,
    CreateSessionRequest,
    CreateShortcutRequest,
    EnvironmentListResponse,
    EnvironmentSummary,
    LinuxCheckResponse,
    LinuxSettings,
    RuntimeCheckResponse,
    SessionEntryRecord,
    SessionEnvironmentResponse,
    SessionResponse,
    SessionStatus,
    SessionTreeResponse,
    SessionWorkspaceResponse,
    Shortcut,
    ShortcutHost,
    ShortcutListResponse,
    TerminalSettings,
    TerminalState,
    UpdateShortcutRequest,
    UpdateTerminalSettingsRequest,
    WindowsCygwinCheckResponse,
    WindowsCygwinSettings,
    WindowsWslCheckResponse,
    WindowsWslSettings,
    WorkspaceRecord,
    WorkspaceRoot,
    WorkspaceRootsResponse,
    WorkspaceTreeNode,
    WorkspaceTreeResponse,
    utc_now,
)
from termbridge.ports import PortAllocator
from termbridge.process import ProcessAdapter, ProcessHandle
from termbridge.repositories import FileSessionRepository, FileTerminalRepository
from termbridge.runtime import RuntimeRegistry
from termbridge.settings import Settings

logger = logging.getLogger(__name__)


class WorkspaceBrowserService:
    def list_roots(self) -> WorkspaceRootsResponse:
        roots = []
        if os.name == "nt":
            for code in range(ord("A"), ord("Z") + 1):
                name = f"{chr(code)}:"
                path = Path(f"{name}/")
                if self._can_read_directory(path):
                    roots.append(WorkspaceRoot(path=str(path.resolve()), name=name))
        else:
            root = Path("/")
            if self._can_read_directory(root):
                roots.append(WorkspaceRoot(path=str(root.resolve()), name="/"))
        return WorkspaceRootsResponse(roots=roots)

    def list_children(self, path: Path, *, show_hidden: bool = False) -> WorkspaceTreeResponse:
        directory = path.expanduser().resolve()
        logger.info("Listing workspace directory path=%s show_hidden=%s", directory, show_hidden)
        if not directory.exists():
            raise WorkspacePathNotFoundError(directory)
        if not directory.is_dir():
            raise WorkspacePathNotDirectoryError(directory)

        try:
            children = [
                WorkspaceTreeNode(
                    path=str(child),
                    name=child.name,
                    has_children=self._has_child_directory(child, show_hidden=show_hidden),
                )
                for child in sorted(directory.iterdir(), key=lambda item: item.name.lower())
                if self._can_read_directory(child) and (show_hidden or not self._is_hidden(child))
            ]
        except OSError as exc:
            raise WorkspaceBrowserError(f"Failed to list workspace path: {directory}") from exc
        return WorkspaceTreeResponse(path=str(directory), name=directory.name or str(directory), children=children)

    def _can_read_directory(self, path: Path) -> bool:
        try:
            return path.is_dir()
        except OSError:
            return False

    def _has_child_directory(self, path: Path, *, show_hidden: bool) -> bool:
        try:
            return any(
                self._can_read_directory(child) and (show_hidden or not self._is_hidden(child))
                for child in path.iterdir()
            )
        except OSError:
            return False

    def _is_hidden(self, path: Path) -> bool:
        if path.name.startswith("."):
            return True
        if os.name != "nt":
            return False
        try:
            attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        except OSError:
            return False
        return attributes != -1 and bool(attributes & 0x2)


class TerminalService:
    def __init__(self, repository: FileTerminalRepository, *, tmux_command_timeout_seconds: float = 10) -> None:
        self._repository = repository
        self._tmux_command_timeout_seconds = tmux_command_timeout_seconds

    def list_shortcuts(self) -> ShortcutListResponse:
        state = self._ensure_default_shortcuts(self._repository.get_state())
        return ShortcutListResponse(shortcuts=state.shortcuts)

    def create_shortcut(self, request: CreateShortcutRequest) -> Shortcut:
        state = self._ensure_default_shortcuts(self._repository.get_state())
        shortcut = Shortcut(
            id=f"shortcut_{uuid4().hex}",
            name=request.name.strip(),
            command=request.command.strip(),
            host=request.host,
            description=request.description,
        )
        self._validate_shortcut(shortcut)
        self._ensure_unique_shortcut_name(state.shortcuts, shortcut)
        state.shortcuts.append(shortcut)
        self._repository.save_state(state)
        return shortcut

    def update_shortcut(self, shortcut_id: str, request: UpdateShortcutRequest) -> Shortcut:
        state = self._ensure_default_shortcuts(self._repository.get_state())
        for index, shortcut in enumerate(state.shortcuts):
            if shortcut.id == shortcut_id:
                update = request.model_dump(exclude_unset=True)
                if "name" in update and update["name"] is not None:
                    update["name"] = update["name"].strip()
                if "command" in update and update["command"] is not None:
                    update["command"] = update["command"].strip()
                updated = shortcut.model_copy(update=update)
                self._validate_shortcut(updated)
                self._ensure_unique_shortcut_name(state.shortcuts, updated, ignored_shortcut_id=shortcut.id)
                state.shortcuts[index] = updated
                self._repository.save_state(state)
                return updated
        raise ShortcutNotFoundError(shortcut_id)

    def delete_shortcut(self, shortcut_id: str) -> None:
        state = self._ensure_default_shortcuts(self._repository.get_state())
        remaining = [shortcut for shortcut in state.shortcuts if shortcut.id != shortcut_id]
        if len(remaining) == len(state.shortcuts):
            raise ShortcutNotFoundError(shortcut_id)
        state.shortcuts = remaining
        self._repository.save_state(state)

    def get_settings(self) -> TerminalSettings:
        return self._repository.get_state().settings

    def update_settings(self, request: UpdateTerminalSettingsRequest) -> TerminalSettings:
        if request.ttyd_mode == "explicit" and not request.ttyd_path:
            raise InvalidTerminalConfigError("ttyd path is required for explicit mode")
        state = self._repository.get_state()
        state.settings = TerminalSettings(
            ttyd_mode=request.ttyd_mode,
            ttyd_path=request.ttyd_path,
        )
        self._repository.save_state(state)
        return state.settings

    def list_environments(self) -> EnvironmentListResponse:
        state = self._repository.get_state()
        is_windows = os.name == "nt"
        is_linux = platform.system().lower() == "linux"
        return EnvironmentListResponse(
            environments=[
                EnvironmentSummary(
                    host="windows_cygwin",
                    label="Cygwin on Windows",
                    readiness=state.windows_cygwin_settings.readiness,
                    available_on_host=is_windows,
                    checked_at=state.windows_cygwin_settings.checked_at,
                    last_error=state.windows_cygwin_settings.last_error
                    or (None if is_windows else "Windows/Cygwin is only available on Windows hosts"),
                ),
                EnvironmentSummary(
                    host="windows_wsl",
                    label="WSL on Windows",
                    readiness=state.windows_wsl_settings.readiness,
                    available_on_host=is_windows,
                    checked_at=state.windows_wsl_settings.checked_at,
                    last_error=state.windows_wsl_settings.last_error
                    or (None if is_windows else "Windows/WSL is only available on Windows hosts"),
                ),
                EnvironmentSummary(
                    host="linux",
                    label="Linux",
                    readiness=state.linux_settings.readiness,
                    available_on_host=is_linux,
                    checked_at=state.linux_settings.checked_at,
                    last_error=state.linux_settings.last_error
                    or (None if is_linux else "Linux environment is unavailable on this host"),
                ),
            ],
        )

    def get_windows_cygwin_settings(self) -> WindowsCygwinSettings:
        return self._repository.get_state().windows_cygwin_settings

    def update_windows_cygwin_settings(self, request: WindowsCygwinSettings) -> WindowsCygwinSettings:
        state = self._repository.get_state()
        current = state.windows_cygwin_settings
        paths_changed = request.bash_path != current.bash_path or request.tmux_path != current.tmux_path
        state.windows_cygwin_settings = current.model_copy(
            update={
                "readiness": "not_ready" if paths_changed else current.readiness,
                "bash_path": request.bash_path,
                "tmux_path": request.tmux_path,
                "checked_at": None if paths_changed else current.checked_at,
                "last_error": None if paths_changed else current.last_error,
            }
        )
        self._repository.save_state(state)
        return state.windows_cygwin_settings

    def get_windows_wsl_settings(self) -> WindowsWslSettings:
        return self._repository.get_state().windows_wsl_settings

    def update_windows_wsl_settings(self, request: WindowsWslSettings) -> WindowsWslSettings:
        state = self._repository.get_state()
        state.windows_wsl_settings = request
        self._repository.save_state(state)
        return state.windows_wsl_settings

    def check_ttyd(self, ttyd_path: str | None = None) -> RuntimeCheckResponse:
        executable = ttyd_path or self._resolve_executable("ttyd", windows_names=("ttyd.exe", "ttyd"))
        if not executable:
            return RuntimeCheckResponse(available=False, reason="ttyd is not available in PATH")
        return self._check_executable_version(executable, [["--version"], ["-v"]])

    def check_windows_cygwin(self, bash_path: str | None = None) -> WindowsCygwinCheckResponse:
        host = RuntimeCheckResponse(
            available=os.name == "nt",
            path=os.name,
            reason=None if os.name == "nt" else "Windows/Cygwin is only available on Windows hosts",
        )
        resolved_bash = (
            self._to_windows_executable_path(bash_path)
            or self._to_windows_executable_path(self._resolve_configured_windows_cygwin_bash())
            or self._detect_cygwin_bash_path()
        )
        if not resolved_bash:
            response = WindowsCygwinCheckResponse(
                host=host,
                bash=RuntimeCheckResponse(available=False, reason="Cygwin bash was not found"),
            )
            self._save_windows_cygwin_check(response)
            return response
        bash = self._check_bash(resolved_bash)
        if not bash.available:
            response = WindowsCygwinCheckResponse(host=host, bash=bash)
            self._save_windows_cygwin_check(response)
            return response
        tmux = self._check_cygwin_tmux(bash.path or resolved_bash)
        response = WindowsCygwinCheckResponse(host=host, bash=bash, tmux=tmux)
        self._save_windows_cygwin_check(response)
        return response

    def check_windows_wsl(self) -> WindowsWslCheckResponse:
        host = RuntimeCheckResponse(
            available=os.name == "nt",
            path=os.name,
            reason=None if os.name == "nt" else "Windows/WSL is only available on Windows hosts",
        )
        wsl = self._check_windows_wsl_executable()
        tmux = self._check_windows_wsl_tmux(wsl.path) if wsl.available else None
        response = WindowsWslCheckResponse(host=host, wsl=wsl, tmux=tmux)
        self._save_windows_wsl_check(response)
        return response

    def _check_windows_wsl_executable(self) -> RuntimeCheckResponse:
        wsl_path = self._resolve_executable("wsl", windows_names=("wsl.exe", "wsl")) or "wsl"
        wsl = self._check_executable_version(wsl_path, [["--version"], ["-v"]])
        if wsl.version:
            wsl = wsl.model_copy(update={"version": wsl.version.replace("\x00", "")})
        if not wsl.available:
            wsl = self._run_check([wsl_path, "--status"])
        return wsl

    def _check_windows_wsl_tmux(self, wsl_path: str | None = None) -> RuntimeCheckResponse:
        executable = wsl_path or self._check_windows_wsl_executable().path or "wsl"
        return self._check_wsl_tmux(executable)

    def check_linux(self) -> LinuxCheckResponse:
        is_linux = platform.system().lower() == "linux"
        host = RuntimeCheckResponse(
            available=is_linux,
            path=platform.system(),
            reason=None if is_linux else "Linux environment is unavailable on this host",
        )
        if not is_linux:
            response = LinuxCheckResponse(host=host)
            self._save_linux_check(response)
            return response
        shell_path = shutil.which("bash") or shutil.which("sh")
        shell = RuntimeCheckResponse(
            available=bool(shell_path),
            path=shell_path,
            reason=None if shell_path else "shell is not available in PATH",
        )
        tmux_path = shutil.which("tmux")
        tmux = (
            self._check_executable_version(tmux_path, [["-V"]])
            if tmux_path
            else RuntimeCheckResponse(
                available=False,
                reason="tmux is not available in PATH",
            )
        )
        response = LinuxCheckResponse(host=host, shell=shell, tmux=tmux)
        self._save_linux_check(response)
        return response

    def _check_cygwin_tmux(self, cygwin_bash_path: str) -> RuntimeCheckResponse:
        try:
            result = subprocess.run(
                [cygwin_bash_path, "-lc", "cygpath -w $(command -v tmux) && tmux -V"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return RuntimeCheckResponse(available=False, reason="tmux detection timed out")
        except OSError as exc:
            return RuntimeCheckResponse(available=False, reason=f"failed to run Cygwin bash: {exc}")

        output = result.stdout.strip().splitlines()
        if result.returncode != 0 or len(output) < 2:
            reason = result.stderr.strip() or "tmux is not available in Cygwin PATH"
            return RuntimeCheckResponse(available=False, reason=reason)
        return RuntimeCheckResponse(available=True, path=output[0], version=output[1])

    def resolve_shortcut_command(
        self, shortcut_id: str, workspace: Path, *, tmux_session_name: str
    ) -> tuple[list[str], Shortcut, list[str] | None]:
        shortcut = self._find_shortcut(shortcut_id)
        if shortcut.host == "windows_cygwin":
            bash_path = self._ensure_windows_cygwin_ready()
            workspace_path = self._to_forward_slash(workspace)
            command = (
                f"cd {shlex.quote(workspace_path)} && exec tmux new-session -A "
                f"-s {shlex.quote(tmux_session_name)} {shlex.quote(shortcut.command)}"
            )
            cleanup_command = [bash_path, "-lc", f"tmux kill-session -t {shlex.quote(tmux_session_name)}"]
            return [bash_path, "-lc", command], shortcut, cleanup_command
        if shortcut.host == "windows_wsl":
            self._ensure_windows_wsl_ready()
            command = (
                f"exec tmux new-session -A -s {shlex.quote(tmux_session_name)} "
                f"{shlex.quote(shortcut.command)}"
            )
            cleanup_command = ["wsl", "sh", "-lc", f"tmux kill-session -t {shlex.quote(tmux_session_name)}"]
            return ["wsl", "--cd", str(workspace), "sh", "-lc", command], shortcut, cleanup_command
        shell_path = self._ensure_linux_ready()
        workspace_path = str(workspace)
        command = (
            f"cd {shlex.quote(workspace_path)} && exec tmux new-session -A "
            f"-s {shlex.quote(tmux_session_name)} {shlex.quote(shortcut.command)}"
        )
        cleanup_command = [shell_path, "-lc", f"tmux kill-session -t {shlex.quote(tmux_session_name)}"]
        return [shell_path, "-lc", command], shortcut, cleanup_command

    def resolve_shortcut(self, shortcut_id: str) -> Shortcut:
        shortcut = self._find_shortcut(shortcut_id)
        if shortcut.host == "windows_cygwin":
            self._ensure_windows_cygwin_ready()
        elif shortcut.host == "windows_wsl":
            self._ensure_windows_wsl_ready()
        else:
            self._ensure_linux_ready()
        return shortcut

    def create_tmux_window(
        self, shortcut: Shortcut, workspace: Path, *, tmux_session_name: str, window_name: str
    ) -> str:
        result = self._run_tmux_command(
            shortcut.host,
            workspace,
            self._create_window_script(shortcut, workspace, tmux_session_name, window_name),
        )
        output = result.stdout.strip().splitlines()
        if result.returncode != 0 or not output:
            raise InvalidTerminalConfigError(result.stderr.strip() or "tmux window could not be created")
        return output[-1]

    def build_tmux_attach_command(
        self, host: ShortcutHost, workspace: Path, *, tmux_session_name: str, tmux_window_id: str | None
    ) -> list[str]:
        select_window = f"tmux select-window -t {shlex.quote(tmux_window_id)} && " if tmux_window_id else ""
        command = f"{select_window}exec tmux attach-session -t {shlex.quote(tmux_session_name)}"
        return self._runtime_shell_command(host, workspace, command)

    def tmux_window_exists(self, host: ShortcutHost, workspace: Path, *, tmux_window_id: str | None) -> bool:
        if not tmux_window_id:
            return False
        result = self._run_tmux_command(host, workspace, f"tmux display-message -p -t {shlex.quote(tmux_window_id)} '#{{window_id}}'")
        return result.returncode == 0 and result.stdout.strip() == tmux_window_id

    def find_tmux_window_by_name(
        self, host: ShortcutHost, workspace: Path, *, tmux_session_name: str, window_name: str
    ) -> str | None:
        result = self._run_tmux_command(
            host,
            workspace,
            f"tmux list-windows -t {shlex.quote(tmux_session_name)} -F '#{{window_id}}\t#{{window_name}}'",
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            window_id, _, name = line.partition("\t")
            if name == window_name:
                return window_id
        return None

    def tmux_session_exists(self, host: ShortcutHost, workspace: Path, *, tmux_session_name: str) -> bool:
        result = self._run_tmux_command(host, workspace, f"tmux has-session -t {shlex.quote(tmux_session_name)}")
        return result.returncode == 0

    def kill_tmux_window(self, host: ShortcutHost, workspace: Path, *, tmux_window_id: str | None) -> None:
        if not tmux_window_id:
            return
        self._run_tmux_cleanup(host, workspace, f"tmux kill-window -t {shlex.quote(tmux_window_id)}")

    def kill_tmux_session(self, host: ShortcutHost, workspace: Path, *, tmux_session_name: str) -> None:
        self._run_tmux_cleanup(host, workspace, f"tmux kill-session -t {shlex.quote(tmux_session_name)}")

    def resolve_ttyd_executable(self, host: ShortcutHost | str, cygwin_bash_path: str | None = None) -> str:
        settings = self.get_settings()
        if settings.ttyd_mode == "explicit":
            if not settings.ttyd_path:
                raise InvalidTerminalConfigError("ttyd path is required for explicit mode")
            return settings.ttyd_path
        return self._resolve_executable("ttyd", windows_names=("ttyd.exe", "ttyd")) or "ttyd"

    def normalize_tmux_session_name(self, name: str, fallback: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("-._")
        return normalized or fallback

    def _create_window_script(
        self, shortcut: Shortcut, workspace: Path, tmux_session_name: str, window_name: str
    ) -> str:
        quoted_session = shlex.quote(tmux_session_name)
        quoted_window = shlex.quote(window_name)
        quoted_command = shlex.quote(shortcut.command)
        quoted_workspace = shlex.quote(self._workspace_shell_path(shortcut.host, workspace))
        create_session = (
            f"tmux new-session -d -P -F '#{{window_id}}' -s {quoted_session} "
            f"-n {quoted_window} -c {quoted_workspace} {quoted_command}"
        )
        create_window = (
            f"tmux new-window -P -F '#{{window_id}}' -t {quoted_session} "
            f"-n {quoted_window} -c {quoted_workspace} {quoted_command}"
        )
        return f"tmux has-session -t {quoted_session} 2>/dev/null && {create_window} || {create_session}"

    def _run_tmux_command(self, host: ShortcutHost, workspace: Path, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self._runtime_shell_command(host, workspace, command),
            capture_output=True,
            text=True,
            timeout=self._tmux_command_timeout_seconds,
            check=False,
        )

    def _run_tmux_cleanup(self, host: ShortcutHost, workspace: Path, command: str) -> None:
        try:
            result = self._run_tmux_command(host, workspace, command)
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("Failed to cleanup tmux state host=%s workspace=%s error=%s", host, workspace, exc)
            return
        if result.returncode != 0:
            logger.warning("Failed to cleanup tmux state host=%s workspace=%s stderr=%s", host, workspace, result.stderr.strip())

    def _runtime_shell_command(self, host: ShortcutHost, workspace: Path, command: str) -> list[str]:
        if host == "windows_cygwin":
            bash_path = self._ensure_windows_cygwin_ready()
            return [bash_path, "-lc", command]
        if host == "windows_wsl":
            self._ensure_windows_wsl_ready()
            return ["wsl", "--cd", str(workspace), "sh", "-lc", command]
        shell_path = self._ensure_linux_ready()
        return [shell_path, "-lc", command]

    def _workspace_shell_path(self, host: ShortcutHost, workspace: Path) -> str:
        if host == "windows_cygwin":
            return self._to_forward_slash(workspace)
        if host == "windows_wsl":
            return "."
        return str(workspace)

    def _find_shortcut(self, shortcut_id: str) -> Shortcut:
        for shortcut in self.list_shortcuts().shortcuts:
            if shortcut.id == shortcut_id:
                return shortcut
        raise ShortcutNotFoundError(shortcut_id)

    def _ensure_default_shortcuts(self, state: TerminalState) -> TerminalState:
        if state.shortcuts:
            return state
        state.shortcuts = [
            Shortcut(
                id="cygwin-bash",
                name="bash",
                command="bash",
                host="windows_cygwin",
                description="Start bash in Windows/Cygwin tmux",
            ),
            Shortcut(
                id="cygwin-cmd",
                name="cmd",
                command="cmd",
                host="windows_cygwin",
                description="Start cmd in Windows/Cygwin tmux",
            ),
            Shortcut(
                id="cygwin-claude",
                name="Claude Code",
                command="claude",
                host="windows_cygwin",
                description="Start Claude Code in Windows/Cygwin tmux",
            ),
            Shortcut(
                id="cygwin-claude-unrestricted",
                name="Claude Code (unrestricted)",
                command="claude --dangerously-skip-permissions",
                host="windows_cygwin",
                description="Start Claude Code without permission prompts in Windows/Cygwin tmux",
            ),
            Shortcut(
                id="cygwin-codex",
                name="Codex",
                command="codex",
                host="windows_cygwin",
                description="Start Codex in Windows/Cygwin tmux",
            ),
            Shortcut(
                id="cygwin-codex-full-access",
                name="Codex (full access)",
                command="codex -a never --sandbox danger-full-access",
                host="windows_cygwin",
                description="Start Codex without sandbox restrictions in Windows/Cygwin tmux",
            ),
            Shortcut(
                id="wsl-bash",
                name="bash",
                command="bash",
                host="windows_wsl",
                description="Start bash in Windows/WSL tmux",
            ),
            Shortcut(
                id="wsl-claude",
                name="Claude Code",
                command="claude",
                host="windows_wsl",
                description="Start Claude Code in Windows/WSL tmux",
            ),
            Shortcut(
                id="wsl-claude-unrestricted",
                name="Claude Code (unrestricted)",
                command="claude --dangerously-skip-permissions",
                host="windows_wsl",
                description="Start Claude Code without permission prompts in Windows/WSL tmux",
            ),
            Shortcut(
                id="wsl-codex",
                name="Codex",
                command="codex",
                host="windows_wsl",
                description="Start Codex in Windows/WSL tmux",
            ),
            Shortcut(
                id="wsl-codex-full-access",
                name="Codex (full access)",
                command="codex -a never --sandbox danger-full-access",
                host="windows_wsl",
                description="Start Codex without sandbox restrictions in Windows/WSL tmux",
            ),
        ]
        self._repository.save_state(state)
        return state

    def _validate_shortcut(self, shortcut: Shortcut) -> None:
        if not shortcut.name.strip():
            raise InvalidTerminalConfigError("Shortcut name is required")
        if not shortcut.command.strip():
            raise InvalidTerminalConfigError("Shortcut command is required")

    def _ensure_unique_shortcut_name(
        self, shortcuts: Sequence[Shortcut], shortcut: Shortcut, *, ignored_shortcut_id: str | None = None
    ) -> None:
        for existing in shortcuts:
            if existing.id == ignored_shortcut_id:
                continue
            if existing.host == shortcut.host and existing.name == shortcut.name:
                raise InvalidTerminalConfigError("Shortcut name already exists in this environment")

    def _ensure_windows_cygwin_ready(self) -> str:
        settings = self.get_windows_cygwin_settings()
        if settings.readiness != "ready":
            raise InvalidTerminalConfigError("Windows/Cygwin environment is not ready. Please check it in environment settings.")
        if not settings.bash_path:
            raise InvalidTerminalConfigError("Cygwin bash path is required for this shortcut")
        self.resolve_ttyd_executable("windows_cygwin", settings.bash_path)
        return settings.bash_path

    def _ensure_windows_wsl_ready(self) -> None:
        settings = self.get_windows_wsl_settings()
        if settings.readiness != "ready":
            raise InvalidTerminalConfigError("Windows/WSL environment is not ready. Please check it in environment settings.")
        self.resolve_ttyd_executable("windows_wsl")

    def _ensure_linux_ready(self) -> str:
        settings = self._repository.get_state().linux_settings
        if settings.readiness != "ready":
            raise InvalidTerminalConfigError("Linux environment is not ready. Please check it in environment settings.")
        if not settings.shell_path:
            raise InvalidTerminalConfigError("Linux shell path is required for this shortcut")
        self.resolve_ttyd_executable("linux")
        return settings.shell_path

    def _save_windows_cygwin_check(self, response: WindowsCygwinCheckResponse) -> None:
        ready = response.host.available and response.bash.available and bool(response.tmux and response.tmux.available)
        state = self._repository.get_state()
        state.windows_cygwin_settings = state.windows_cygwin_settings.model_copy(
            update={
                "readiness": "ready" if ready else "not_ready",
                "bash_path": response.bash.path or state.windows_cygwin_settings.bash_path,
                "tmux_path": response.tmux.path if response.tmux and response.tmux.path else state.windows_cygwin_settings.tmux_path,
                "checked_at": utc_now(),
                "last_error": None if ready else self._first_error(response.host, response.bash, response.tmux),
            }
        )
        self._repository.save_state(state)

    def _save_windows_wsl_check(self, response: WindowsWslCheckResponse) -> None:
        ready = response.host.available and response.wsl.available and bool(response.tmux and response.tmux.available)
        state = self._repository.get_state()
        state.windows_wsl_settings = state.windows_wsl_settings.model_copy(
            update={
                "readiness": "ready" if ready else "not_ready",
                "wsl_path": response.wsl.path or state.windows_wsl_settings.wsl_path,
                "wsl_version": response.wsl.version or state.windows_wsl_settings.wsl_version,
                "tmux_path": response.tmux.path if response.tmux and response.tmux.path else state.windows_wsl_settings.tmux_path,
                "tmux_version": response.tmux.version
                if response.tmux and response.tmux.version
                else state.windows_wsl_settings.tmux_version,
                "checked_at": utc_now(),
                "last_error": None if ready else self._first_error(response.host, response.wsl, response.tmux),
            }
        )
        self._repository.save_state(state)

    def _save_linux_check(self, response: LinuxCheckResponse) -> None:
        ready = response.host.available and bool(response.shell and response.shell.available) and bool(
            response.tmux and response.tmux.available
        )
        state = self._repository.get_state()
        state.linux_settings = LinuxSettings(
            readiness="ready" if ready else "not_ready",
            shell_path=response.shell.path if response.shell and response.shell.path else state.linux_settings.shell_path,
            tmux_path=response.tmux.path if response.tmux and response.tmux.path else state.linux_settings.tmux_path,
            checked_at=utc_now(),
            last_error=None if ready else self._first_error(response.host, response.shell, response.tmux),
        )
        self._repository.save_state(state)

    def _first_error(self, *checks: RuntimeCheckResponse | None) -> str | None:
        for check in checks:
            if check is not None and not check.available:
                return check.reason or "environment check failed"
        return None

    def _check_executable_version(self, executable: str, version_args: list[list[str]]) -> RuntimeCheckResponse:
        last_reason = ""
        for args in version_args:
            result = self._run_check([executable, *args])
            if result.available:
                return result
            last_reason = result.reason or last_reason
        return RuntimeCheckResponse(available=False, path=executable, reason=last_reason or "version check failed")

    def _run_check(self, command: list[str]) -> RuntimeCheckResponse:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
        except subprocess.TimeoutExpired:
            return RuntimeCheckResponse(available=False, path=command[0], reason="detection timed out")
        except OSError as exc:
            return RuntimeCheckResponse(available=False, path=command[0], reason=str(exc))
        output = (result.stdout.strip() or result.stderr.strip()).splitlines()
        if result.returncode != 0:
            return RuntimeCheckResponse(
                available=False,
                path=command[0],
                reason=result.stderr.strip() or result.stdout.strip() or "command failed",
            )
        return RuntimeCheckResponse(available=True, path=command[0], version=output[0] if output else None)

    def _check_bash(self, bash_path: str) -> RuntimeCheckResponse:
        try:
            result = subprocess.run(
                [bash_path, "-lc", "cygpath -w $(command -v bash) && bash --version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return RuntimeCheckResponse(available=False, path=bash_path, reason="Cygwin bash detection timed out")
        except OSError as exc:
            return RuntimeCheckResponse(available=False, path=bash_path, reason=str(exc))
        output = result.stdout.strip().splitlines()
        if result.returncode != 0:
            return RuntimeCheckResponse(
                available=False,
                path=bash_path,
                reason=result.stderr.strip() or "Cygwin bash is not available",
            )
        detected_path = output[0] if output else bash_path
        version = output[1] if len(output) > 1 else None
        return RuntimeCheckResponse(available=True, path=detected_path, version=version)

    def _check_wsl_tmux(self, wsl_path: str) -> RuntimeCheckResponse:
        try:
            result = subprocess.run(
                [wsl_path, "sh", "-lc", "command -v tmux && tmux -V"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return RuntimeCheckResponse(available=False, path="tmux", reason="WSL tmux detection timed out")
        except OSError as exc:
            return RuntimeCheckResponse(available=False, path="tmux", reason=str(exc))
        output = result.stdout.strip().splitlines()
        if result.returncode != 0 or len(output) < 2:
            return RuntimeCheckResponse(
                available=False,
                path="tmux",
                reason=result.stderr.strip() or "tmux is not available in default WSL",
            )
        return RuntimeCheckResponse(available=True, path=output[0], version=output[1])

    def _resolve_configured_windows_cygwin_bash(self) -> str | None:
        return self.get_windows_cygwin_settings().bash_path

    def _resolve_executable(self, name: str, *, windows_names: tuple[str, ...] | None = None) -> str | None:
        names = windows_names if os.name == "nt" and windows_names else (name,)
        for candidate_name in names:
            candidate = shutil.which(candidate_name)
            if candidate:
                return self._normalize_executable_path(candidate)
        return None

    def _normalize_executable_path(self, path: str) -> str:
        if os.name != "nt" or not path.lower().endswith(".exe"):
            return path
        return f"{path[:-4]}.exe"

    def _detect_cygwin_bash_path(self) -> str | None:
        candidates = [
            self._resolve_executable("bash"),
            "D:/ProgramFiles/Cygwin64/bin/bash.exe",
            "C:/cygwin64/bin/bash.exe",
            "C:/cygwin/bin/bash.exe",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return None

    def _to_windows_executable_path(self, path: str | None) -> str | None:
        if not path or path.startswith("/"):
            return None
        return path

    def _to_forward_slash(self, path: Path) -> str:
        return str(path).replace("\\", "/")


class SessionService:
    def __init__(
        self,
        settings: Settings,
        repository: FileSessionRepository,
        runtime_registry: RuntimeRegistry,
        port_allocator: PortAllocator,
        process_adapter: ProcessAdapter,
        terminal_service: TerminalService | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._runtime_registry = runtime_registry
        self._port_allocator = port_allocator
        self._process_adapter = process_adapter
        self._terminal_service = terminal_service

    def create(self, request: CreateSessionRequest) -> SessionResponse:
        logger.info(
            "Creating session name=%s shortcut=%s workspace=%s", request.name, request.shortcut_id, request.workspace
        )
        workspace_path = self._resolve_workspace(request.workspace)
        terminal_service = self._require_terminal_service()
        shortcut = terminal_service.resolve_shortcut(request.shortcut_id)
        now = utc_now()
        workspace = self._get_or_create_workspace(shortcut.host, workspace_path, now)
        if any(entry.name == request.name for entry in workspace.entries):
            raise InvalidTerminalConfigError("Session name already exists in this workspace")
        entry_id = f"sess_{uuid4().hex}"
        tmux_window_id = terminal_service.create_tmux_window(
            shortcut,
            workspace.path,
            tmux_session_name=workspace.tmux_session_name,
            window_name=request.name,
        )
        entry = SessionEntryRecord(
            id=entry_id,
            workspace_id=workspace.id,
            name=request.name,
            runtime=shortcut.host,
            command=[],
            port=0,
            status=SessionStatus.STARTING,
            pid=None,
            created_at=now,
            updated_at=now,
            url="",
            shortcut_id=shortcut.id,
            shortcut_name=shortcut.name,
            host=shortcut.host,
            tmux_session_name=workspace.tmux_session_name,
            tmux_window_id=tmux_window_id,
        )
        try:
            entry = self._start_entry(entry, workspace)
            workspace = workspace.model_copy(update={"entries": [*workspace.entries, entry], "updated_at": entry.updated_at})
            self._repository.upsert_workspace(workspace)
        except Exception:
            self._cleanup_started_entry(workspace, entry)
            raise
        logger.info("Session entry created entry_id=%s workspace_id=%s pid=%s", entry.id, workspace.id, entry.pid)
        return SessionResponse.from_entry(workspace, entry)

    def list_sessions(self) -> list[SessionResponse]:
        workspaces = self._refresh_workspaces(self._repository.list_workspaces())
        return [SessionResponse.from_entry(workspace, entry) for workspace in workspaces for entry in workspace.entries]

    def list_tree(self) -> SessionTreeResponse:
        workspaces = self._refresh_workspaces(self._repository.list_workspaces())
        labels = self._environment_labels()
        environments = []
        for host in ("windows_cygwin", "windows_wsl", "linux"):
            host_workspaces = [workspace for workspace in workspaces if workspace.host == host]
            environments.append(
                SessionEnvironmentResponse(
                    host=host,
                    label=labels[host],
                    workspaces=[self._workspace_response(workspace) for workspace in host_workspaces],
                )
            )
        return SessionTreeResponse(environments=environments)

    def get(self, session_id: str) -> SessionResponse:
        workspace, entry = self._repository.get_entry(session_id)
        entry = self._refresh_entry(workspace, entry)
        return SessionResponse.from_entry(workspace, entry)

    def start(self, session_id: str) -> SessionResponse:
        logger.info("Starting session entry_id=%s", session_id)
        workspace, entry = self._repository.get_entry(session_id)
        entry = self._refresh_entry(workspace, entry)
        if entry.status == SessionStatus.RUNNING:
            return SessionResponse.from_entry(workspace, entry)
        terminal_service = self._require_terminal_service()
        shortcut = terminal_service.resolve_shortcut(entry.shortcut_id)
        if shortcut.host != workspace.host:
            raise InvalidTerminalConfigError("Shortcut host does not match session workspace")
        if not terminal_service.tmux_window_exists(workspace.host, workspace.path, tmux_window_id=entry.tmux_window_id):
            tmux_window_id = terminal_service.find_tmux_window_by_name(
                workspace.host,
                workspace.path,
                tmux_session_name=workspace.tmux_session_name,
                window_name=entry.name,
            ) or terminal_service.create_tmux_window(
                shortcut,
                workspace.path,
                tmux_session_name=workspace.tmux_session_name,
                window_name=entry.name,
            )
            entry = entry.model_copy(update={"tmux_window_id": tmux_window_id})
        try:
            entry = self._start_entry(entry, workspace)
            self._repository.update_entry(entry)
        except Exception:
            self._cleanup_started_entry(workspace, entry)
            raise
        return SessionResponse.from_entry(workspace, entry)

    def stop(self, session_id: str) -> SessionResponse:
        logger.info("Stopping session entry_id=%s", session_id)
        workspace, entry = self._repository.get_entry(session_id)
        terminal_service = self._require_terminal_service()
        terminal_service.kill_tmux_window(workspace.host, workspace.path, tmux_window_id=entry.tmux_window_id)
        updated = self._stop_entry(workspace, entry)
        self._repository.update_entry(updated)
        return SessionResponse.from_entry(workspace, updated)

    def close_all(self) -> CloseAllSessionsResponse:
        logger.info("Closing all session entries")
        state = self._repository.get_state()
        terminal_service = self._require_terminal_service()
        stopped_count = 0
        tmux_session_count = 0
        now = utc_now()
        for workspace in state.workspaces.values():
            updated_entries = []
            for entry in workspace.entries:
                if entry.pid is not None:
                    self._process_adapter.terminate(ProcessHandle(pid=entry.pid))
                terminal_service.kill_tmux_window(workspace.host, workspace.path, tmux_window_id=entry.tmux_window_id)
                updated_entries.append(
                    entry.model_copy(
                        update={"status": SessionStatus.STOPPED, "pid": None, "url": "", "tmux_window_id": None, "updated_at": now}
                    )
                )
                stopped_count += int(entry.status != SessionStatus.STOPPED or entry.pid is not None or entry.tmux_window_id is not None)
            if workspace.entries:
                terminal_service.kill_tmux_session(
                    workspace.host,
                    workspace.path,
                    tmux_session_name=workspace.tmux_session_name,
                )
                tmux_session_count += 1
            state.workspaces[workspace.id] = workspace.model_copy(update={"entries": updated_entries, "updated_at": now})
        self._repository.save_state(state)
        return CloseAllSessionsResponse(stopped_count=stopped_count, tmux_session_count=tmux_session_count)

    def delete(self, session_id: str) -> None:
        logger.info("Deleting session entry_id=%s", session_id)
        workspace, entry = self._repository.get_entry(session_id)
        if entry.pid is not None:
            self._process_adapter.terminate(ProcessHandle(pid=entry.pid))
        self._require_terminal_service().kill_tmux_window(workspace.host, workspace.path, tmux_window_id=entry.tmux_window_id)
        remaining_workspace = self._repository.delete_entry(session_id)
        if not remaining_workspace.entries:
            self._require_terminal_service().kill_tmux_session(
                workspace.host,
                workspace.path,
                tmux_session_name=workspace.tmux_session_name,
            )
        logger.info("Session entry deleted entry_id=%s", session_id)

    def delete_workspace(self, workspace_id: str) -> None:
        logger.info("Deleting workspace workspace_id=%s", workspace_id)
        workspace = self._repository.delete_workspace(workspace_id)
        terminal_service = self._require_terminal_service()
        for entry in workspace.entries:
            if entry.pid is not None:
                self._process_adapter.terminate(ProcessHandle(pid=entry.pid))
            terminal_service.kill_tmux_window(workspace.host, workspace.path, tmux_window_id=entry.tmux_window_id)
        terminal_service.kill_tmux_session(workspace.host, workspace.path, tmux_session_name=workspace.tmux_session_name)

    def _stop_entry(
        self, workspace: WorkspaceRecord, entry: SessionEntryRecord, *, now: datetime | None = None
    ) -> SessionEntryRecord:
        if entry.pid is not None:
            self._process_adapter.terminate(ProcessHandle(pid=entry.pid))
        return entry.model_copy(
            update={
                "status": SessionStatus.STOPPED,
                "pid": None,
                "url": "",
                "tmux_window_id": None,
                "updated_at": now or utc_now(),
            }
        )

    def _start_entry(self, entry: SessionEntryRecord, workspace: WorkspaceRecord) -> SessionEntryRecord:
        terminal_service = self._require_terminal_service()
        used_ports = [item.port for _, item in self._repository.list_entries() if item.id != entry.id and item.port]
        port = self._port_allocator.allocate(used_ports)
        runtime_command = terminal_service.build_tmux_attach_command(
            workspace.host,
            workspace.path,
            tmux_session_name=workspace.tmux_session_name,
            tmux_window_id=entry.tmux_window_id,
        )
        ttyd_executable = terminal_service.resolve_ttyd_executable(workspace.host)
        command = self._build_ttyd_command(port, workspace.path, runtime_command, ttyd_executable)
        log_file, suppress_output = self._ttyd_log_options(entry.id)
        handle = self._process_adapter.start(
            command,
            workspace.path,
            log_file=log_file,
            suppress_output=suppress_output,
        )
        return entry.model_copy(
            update={
                "command": command,
                "port": port,
                "status": SessionStatus.RUNNING,
                "pid": handle.pid,
                "updated_at": utc_now(),
                "url": self._build_url(port),
            }
        )

    def _cleanup_started_entry(self, workspace: WorkspaceRecord, entry: SessionEntryRecord) -> None:
        if entry.pid is not None:
            self._process_adapter.terminate(ProcessHandle(pid=entry.pid))
        self._require_terminal_service().kill_tmux_window(workspace.host, workspace.path, tmux_window_id=entry.tmux_window_id)

    def _refresh_workspaces(self, workspaces: list[WorkspaceRecord]) -> list[WorkspaceRecord]:
        return [self._refresh_workspace(workspace) for workspace in workspaces]

    def _refresh_workspace(self, workspace: WorkspaceRecord) -> WorkspaceRecord:
        entries = [self._refresh_entry(workspace, entry) for entry in workspace.entries]
        if entries == workspace.entries:
            return workspace
        return workspace.model_copy(update={"entries": entries})

    def _refresh_entry(self, workspace: WorkspaceRecord, entry: SessionEntryRecord) -> SessionEntryRecord:
        if entry.status != SessionStatus.RUNNING or entry.pid is None:
            return entry
        terminal_service = self._require_terminal_service()
        if self._process_adapter.is_running(ProcessHandle(pid=entry.pid)) and terminal_service.tmux_window_exists(
            workspace.host,
            workspace.path,
            tmux_window_id=entry.tmux_window_id,
        ):
            return entry
        tmux_window_id = (
            entry.tmux_window_id
            if terminal_service.tmux_window_exists(workspace.host, workspace.path, tmux_window_id=entry.tmux_window_id)
            else None
        )
        updated = entry.model_copy(
            update={"status": SessionStatus.STOPPED, "pid": None, "url": "", "tmux_window_id": tmux_window_id, "updated_at": utc_now()}
        )
        try:
            self._repository.update_entry(updated)
        except SessionNotFoundError:
            logger.warning("Session entry disappeared while refreshing status entry_id=%s", entry.id)
        return updated

    def _workspace_response(self, workspace: WorkspaceRecord) -> SessionWorkspaceResponse:
        entries = [SessionResponse.from_entry(workspace, entry) for entry in workspace.entries]
        status = SessionStatus.RUNNING if any(entry.status == SessionStatus.RUNNING for entry in workspace.entries) else SessionStatus.STOPPED
        return SessionWorkspaceResponse(
            id=workspace.id,
            host=workspace.host,
            name=workspace.name,
            path=str(workspace.path),
            status=status,
            entries=entries,
        )

    def _get_or_create_workspace(self, host: ShortcutHost, workspace_path: Path, now: datetime) -> WorkspaceRecord:
        workspace_id = self._workspace_id(host, workspace_path)
        state = self._repository.get_state()
        existing = state.workspaces.get(workspace_id)
        if existing is not None:
            return existing
        return WorkspaceRecord(
            id=workspace_id,
            host=host,
            path=workspace_path,
            name=workspace_path.name or str(workspace_path),
            tmux_session_name=self._tmux_session_name(host, workspace_path),
            created_at=now,
            updated_at=now,
            entries=[],
        )

    def _workspace_id(self, host: ShortcutHost, workspace_path: Path) -> str:
        digest = hashlib.sha256(f"{host}:{self._normalized_workspace_path(host, workspace_path)}".encode()).hexdigest()
        return f"ws_{digest[:16]}"

    def _tmux_session_name(self, host: ShortcutHost, workspace_path: Path) -> str:
        digest = hashlib.sha256(f"{host}:{self._normalized_workspace_path(host, workspace_path)}".encode()).hexdigest()
        host_part = {"windows_cygwin": "cyg", "windows_wsl": "wsl", "linux": "lin"}[host]
        return f"tb_{host_part}_{digest[:16]}"

    def _normalized_workspace_path(self, host: ShortcutHost, workspace_path: Path) -> str:
        normalized = str(workspace_path).replace("\\", "/").rstrip("/")
        return normalized.lower() if host == "windows_cygwin" else normalized

    def _resolve_workspace(self, workspace: Path) -> Path:
        workspace_path = workspace.expanduser().resolve()
        if not workspace_path.is_dir():
            logger.warning("Session workspace not found workspace=%s", workspace_path)
            raise WorkspaceNotFoundError(workspace_path)
        return workspace_path

    def _require_terminal_service(self) -> TerminalService:
        if self._terminal_service is None:
            raise InvalidTerminalConfigError("Shortcut service is not available")
        return self._terminal_service

    def _environment_labels(self) -> dict[ShortcutHost, str]:
        return {
            "windows_cygwin": "Cygwin",
            "windows_wsl": "WSL",
            "linux": "Linux",
        }

    def _ttyd_log_options(self, session_id: str) -> tuple[Path | None, bool]:
        if self._settings.ttyd_log_mode == "file":
            return self._settings.state_dir / "logs" / "ttyd" / f"{session_id}.log", False
        if self._settings.ttyd_log_mode == "none":
            return None, True
        return None, False

    def _build_ttyd_command(
        self, port: int, workspace: Path, runtime_command: Sequence[str], ttyd_executable: str
    ) -> list[str]:
        return [
            ttyd_executable,
            "--writable",
            "--port",
            str(port),
            "--cwd",
            str(workspace),
            *runtime_command,
        ]

    def _build_url(self, port: int) -> str:
        if self._settings.public_base_url:
            return f"{self._settings.public_base_url.rstrip('/')}/{port}"
        return f"http://{self._settings.host}:{port}"
