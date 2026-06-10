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


class CreateSessionRequest(BaseModel):
    name: str = Field(min_length=1)
    workspace: Path
    shortcut_id: str = Field(min_length=1)


class SessionRecord(BaseModel):
    id: str
    name: str
    workspace: Path
    runtime: str
    command: list[str]
    port: int
    status: SessionStatus
    pid: int | None = None
    created_at: datetime
    updated_at: datetime
    url: str
    shortcut_id: str | None = None
    shortcut_name: str | None = None
    host: ShortcutHost | None = None
    session_persistence: Literal["none", "tmux"] = "none"
    tmux_bash_path: str | None = None
    tmux_session_name: str | None = None


class SessionResponse(BaseModel):
    id: str
    name: str
    workspace: str
    runtime: str
    status: SessionStatus
    port: int
    url: str
    shortcut_id: str | None = None
    shortcut_name: str | None = None
    host: ShortcutHost | None = None
    session_persistence: Literal["none", "tmux"] = "none"
    tmux_session_name: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: SessionRecord) -> "SessionResponse":
        return cls(
            id=record.id,
            name=record.name,
            workspace=str(record.workspace),
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
    host: ShortcutHost = "windows_cygwin"
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
    bash_path: str | None = None
    tmux_path: str | None = None


class UpdateTerminalSettingsRequest(BaseModel):
    ttyd_mode: Literal["auto", "explicit"] = "auto"
    ttyd_path: str | None = None


class TerminalState(BaseModel):
    shortcuts: list[Shortcut] = Field(default_factory=list)
    settings: TerminalSettings = Field(default_factory=TerminalSettings)
    windows_cygwin_settings: WindowsCygwinSettings = Field(default_factory=WindowsCygwinSettings)


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


class TmuxAvailabilityRequest(BaseModel):
    cygwin_bash_path: str = Field(min_length=1)


class TmuxAvailabilityResponse(BaseModel):
    available: bool
    path: str | None = None
    version: str | None = None
    reason: str | None = None


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
