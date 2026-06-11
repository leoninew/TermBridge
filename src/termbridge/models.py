from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


ShortcutHost = Literal["windows_cygwin", "windows_wsl", "linux"]
EnvironmentReadiness = Literal["not_ready", "ready"]


class CreateSessionRequest(BaseModel):
    name: str = Field(min_length=1)
    workspace: Path
    shortcut_id: str = Field(min_length=1)


class SessionEntryRecord(BaseModel):
    id: str
    workspace_id: str
    name: str
    runtime: str
    command: list[str]
    port: int
    status: SessionStatus
    pid: int | None = None
    created_at: datetime
    updated_at: datetime
    url: str
    shortcut_id: str
    shortcut_name: str
    host: ShortcutHost
    session_persistence: Literal["none", "tmux"] = "tmux"
    tmux_session_name: str
    tmux_window_id: str | None = None


class WorkspaceRecord(BaseModel):
    id: str
    host: ShortcutHost
    path: Path
    name: str
    tmux_session_name: str
    created_at: datetime
    updated_at: datetime
    entries: list[SessionEntryRecord] = Field(default_factory=list)


class SessionState(BaseModel):
    workspaces: dict[str, WorkspaceRecord] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    workspace: str
    runtime: str
    status: SessionStatus
    port: int
    url: str
    shortcut_id: str | None = None
    shortcut_name: str | None = None
    host: ShortcutHost | None = None
    session_persistence: Literal["none", "tmux"] = "tmux"
    tmux_session_name: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entry(cls, workspace: WorkspaceRecord, entry: SessionEntryRecord) -> "SessionResponse":
        return cls(
            id=entry.id,
            workspace_id=workspace.id,
            name=entry.name,
            workspace=str(workspace.path),
            runtime=entry.runtime,
            status=entry.status,
            port=entry.port,
            url=entry.url,
            shortcut_id=entry.shortcut_id,
            shortcut_name=entry.shortcut_name,
            host=entry.host,
            session_persistence=entry.session_persistence,
            tmux_session_name=entry.tmux_session_name,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )

    @classmethod
    def from_record(cls, record: SessionEntryRecord) -> "SessionResponse":
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            name=record.name,
            workspace="",
            runtime=record.runtime,
            status=record.status,
            port=record.port,
            url=record.url,
            shortcut_id=record.shortcut_id,
            shortcut_name=record.shortcut_name,
            host=record.host,
            session_persistence=record.session_persistence,
            tmux_session_name=record.tmux_session_name,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class SessionWorkspaceResponse(BaseModel):
    id: str
    host: ShortcutHost
    name: str
    path: str
    status: SessionStatus
    entries: list[SessionResponse]


class SessionEnvironmentResponse(BaseModel):
    host: ShortcutHost
    label: str
    workspaces: list[SessionWorkspaceResponse]


class SessionTreeResponse(BaseModel):
    environments: list[SessionEnvironmentResponse]


class CloseAllSessionsResponse(BaseModel):
    stopped_count: int
    tmux_session_count: int


class Shortcut(BaseModel):
    id: str
    name: str
    command: str
    host: ShortcutHost
    description: str | None = None


class ShortcutListResponse(BaseModel):
    shortcuts: list[Shortcut]


class CreateShortcutRequest(BaseModel):
    name: str = Field(min_length=1)
    command: str = Field(min_length=1)
    host: ShortcutHost
    description: str | None = None


class UpdateShortcutRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    command: str | None = Field(default=None, min_length=1)
    host: ShortcutHost | None = None
    description: str | None = None


class TerminalSettings(BaseModel):
    ttyd_mode: Literal["auto", "explicit"] = "auto"
    ttyd_path: str | None = None


class WindowsCygwinSettings(BaseModel):
    readiness: EnvironmentReadiness = "not_ready"
    bash_path: str | None = None
    tmux_path: str | None = None
    checked_at: datetime | None = None
    last_error: str | None = None


class WindowsWslSettings(BaseModel):
    readiness: EnvironmentReadiness = "not_ready"
    wsl_path: str | None = None
    wsl_version: str | None = None
    default_distro: str | None = None
    automount_root: str | None = None
    tmux_path: str | None = None
    tmux_version: str | None = None
    shell_path: str | None = None
    checked_at: datetime | None = None
    last_error: str | None = None


class LinuxSettings(BaseModel):
    readiness: EnvironmentReadiness = "not_ready"
    shell_path: str | None = None
    tmux_path: str | None = None
    checked_at: datetime | None = None
    last_error: str | None = None


class UpdateTerminalSettingsRequest(BaseModel):
    ttyd_mode: Literal["auto", "explicit"] = "auto"
    ttyd_path: str | None = None


class TerminalState(BaseModel):
    shortcuts: list[Shortcut] = Field(default_factory=list)
    settings: TerminalSettings = Field(default_factory=TerminalSettings)
    windows_cygwin_settings: WindowsCygwinSettings = Field(default_factory=WindowsCygwinSettings)
    windows_wsl_settings: WindowsWslSettings = Field(default_factory=WindowsWslSettings)
    linux_settings: LinuxSettings = Field(default_factory=LinuxSettings)


class RuntimeCheckResponse(BaseModel):
    available: bool
    path: str | None = None
    version: str | None = None
    reason: str | None = None


class WindowsCygwinCheckResponse(BaseModel):
    host: RuntimeCheckResponse
    bash: RuntimeCheckResponse
    tmux: RuntimeCheckResponse | None = None


class WindowsWslCheckResponse(BaseModel):
    host: RuntimeCheckResponse
    wsl: RuntimeCheckResponse
    tmux: RuntimeCheckResponse | None = None


class LinuxCheckResponse(BaseModel):
    host: RuntimeCheckResponse
    shell: RuntimeCheckResponse | None = None
    tmux: RuntimeCheckResponse | None = None


class EnvironmentSummary(BaseModel):
    host: ShortcutHost
    label: str
    readiness: EnvironmentReadiness
    available_on_host: bool
    checked_at: datetime | None = None
    last_error: str | None = None


class EnvironmentListResponse(BaseModel):
    environments: list[EnvironmentSummary]


class RuntimeCheckRequest(BaseModel):
    path: str | None = None


class WindowsCygwinCheckRequest(BaseModel):
    bash_path: str | None = None


class WorkspaceRoot(BaseModel):
    path: str
    name: str
    type: Literal["drive"] = "drive"


class WorkspaceTreeNode(BaseModel):
    path: str
    name: str
    type: Literal["directory"] = "directory"
    has_children: bool


class WorkspaceRootsResponse(BaseModel):
    roots: list[WorkspaceRoot]


class WorkspaceTreeResponse(BaseModel):
    path: str
    name: str
    children: list[WorkspaceTreeNode]


def utc_now() -> datetime:
    return datetime.now(UTC)
