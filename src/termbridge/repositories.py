import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from termbridge.exceptions import (
    SessionNotFoundError,
    SessionRepositoryError,
    ShortcutRepositoryError,
)
from termbridge.models import SessionEntryRecord, SessionState, ShortcutHost, TerminalState, WorkspaceRecord


class FileSessionRepository:
    def __init__(self, sessions_file: Path) -> None:
        self._sessions_file = sessions_file

    def get_state(self) -> SessionState:
        return self._read_state()

    def save_state(self, state: SessionState) -> SessionState:
        self._write_state(state)
        return state

    def list_workspaces(self) -> list[WorkspaceRecord]:
        return list(self._read_state().workspaces.values())

    def get_workspace(self, workspace_id: str) -> WorkspaceRecord:
        workspace = self._read_state().workspaces.get(workspace_id)
        if workspace is None:
            raise SessionNotFoundError(workspace_id)
        return workspace

    def upsert_workspace(self, workspace: WorkspaceRecord) -> WorkspaceRecord:
        state = self._read_state()
        state.workspaces[workspace.id] = workspace
        self._write_state(state)
        return workspace

    def delete_workspace(self, workspace_id: str) -> WorkspaceRecord:
        state = self._read_state()
        workspace = state.workspaces.get(workspace_id)
        if workspace is None:
            raise SessionNotFoundError(workspace_id)
        del state.workspaces[workspace_id]
        self._write_state(state)
        return workspace

    def reorder_workspaces(self, host: ShortcutHost, workspace_ids: list[str]) -> SessionState:
        state = self._read_state()
        requested = set(workspace_ids)
        host_workspace_ids = [workspace.id for workspace in state.workspaces.values() if workspace.host == host]
        if requested != set(host_workspace_ids) or len(requested) != len(workspace_ids):
            raise SessionRepositoryError("Workspace order must include each workspace in the environment exactly once")

        ordered_ids = iter(workspace_ids)
        reordered: dict[str, WorkspaceRecord] = {}
        for workspace in state.workspaces.values():
            workspace_id = next(ordered_ids) if workspace.host == host else workspace.id
            reordered[workspace_id] = state.workspaces[workspace_id]
        state.workspaces = reordered
        self._write_state(state)
        return state

    def reorder_entries(self, workspace_id: str, entry_ids: list[str]) -> WorkspaceRecord:
        state = self._read_state()
        workspace = state.workspaces.get(workspace_id)
        if workspace is None:
            raise SessionNotFoundError(workspace_id)
        requested = set(entry_ids)
        current_ids = [entry.id for entry in workspace.entries]
        if requested != set(current_ids) or len(requested) != len(entry_ids):
            raise SessionRepositoryError("Session order must include each session in the workspace exactly once")

        entries_by_id = {entry.id: entry for entry in workspace.entries}
        updated = workspace.model_copy(update={"entries": [entries_by_id[entry_id] for entry_id in entry_ids]})
        state.workspaces[workspace.id] = updated
        self._write_state(state)
        return updated

    def list_entries(self) -> list[tuple[WorkspaceRecord, SessionEntryRecord]]:
        return [(workspace, entry) for workspace in self.list_workspaces() for entry in workspace.entries]

    def get_entry(self, entry_id: str) -> tuple[WorkspaceRecord, SessionEntryRecord]:
        for workspace, entry in self.list_entries():
            if entry.id == entry_id:
                return workspace, entry
        raise SessionNotFoundError(entry_id)

    def update_entry(self, entry: SessionEntryRecord) -> SessionEntryRecord:
        state = self._read_state()
        workspace = state.workspaces.get(entry.workspace_id)
        if workspace is None:
            raise SessionNotFoundError(entry.workspace_id)
        entries = [entry if item.id == entry.id else item for item in workspace.entries]
        if all(item.id != entry.id for item in workspace.entries):
            raise SessionNotFoundError(entry.id)
        state.workspaces[workspace.id] = workspace.model_copy(
            update={"entries": entries, "updated_at": entry.updated_at}
        )
        self._write_state(state)
        return entry

    def delete_entry(self, entry_id: str) -> WorkspaceRecord:
        state = self._read_state()
        for workspace in state.workspaces.values():
            entries = [entry for entry in workspace.entries if entry.id != entry_id]
            if len(entries) == len(workspace.entries):
                continue
            updated = workspace.model_copy(update={"entries": entries})
            state.workspaces[workspace.id] = updated
            self._write_state(state)
            return updated
        raise SessionNotFoundError(entry_id)

    def _read_state(self) -> SessionState:
        if not self._sessions_file.exists():
            return SessionState()
        try:
            raw = json.loads(self._sessions_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise SessionRepositoryError("Session registry must be a JSON object")
            return self._decode_state(raw)
        except json.JSONDecodeError as exc:
            raise SessionRepositoryError("Session registry contains invalid JSON") from exc
        except ValidationError as exc:
            raise SessionRepositoryError("Session registry contains invalid session data") from exc

    def _decode_state(self, raw: dict[str, Any]) -> SessionState:
        if set(raw) == {"environments"}:
            workspaces: dict[str, WorkspaceRecord] = {}
            environments = raw["environments"]
            if not isinstance(environments, dict):
                raise SessionRepositoryError("Session registry environments must be a JSON object")
            for workspaces_by_path in environments.values():
                if not isinstance(workspaces_by_path, dict):
                    raise SessionRepositoryError("Session registry workspaces must be JSON objects")
                for workspace_data in workspaces_by_path.values():
                    if not isinstance(workspace_data, dict):
                        raise SessionRepositoryError("Session registry workspace must be a JSON object")
                    sessions = workspace_data.get("sessions", {})
                    if not isinstance(sessions, dict):
                        raise SessionRepositoryError("Session registry sessions must be a JSON object")
                    workspace = WorkspaceRecord.model_validate({**workspace_data, "entries": list(sessions.values())})
                    workspaces[workspace.id] = workspace
            return SessionState(workspaces=workspaces)
        raise SessionRepositoryError("Session registry uses an incompatible schema")

    def _write_state(self, state: SessionState) -> None:
        self._sessions_file.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self._sessions_file.name}.",
            suffix=".tmp",
            dir=self._sessions_file.parent,
            text=True,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                json.dump(self._encode_state(state), temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
            os.replace(temp_path, self._sessions_file)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def _encode_state(self, state: SessionState) -> dict[str, Any]:
        environments: dict[ShortcutHost, dict[str, dict[str, Any]]] = {
            "windows_cygwin": {},
            "windows_wsl": {},
            "linux": {},
        }
        for workspace in state.workspaces.values():
            sessions = {entry.name: entry.model_dump(mode="json") for entry in workspace.entries}
            workspace_data = workspace.model_dump(mode="json", exclude={"entries"})
            workspace_data["sessions"] = sessions
            environments[workspace.host][self._workspace_key(workspace.host, workspace.path)] = workspace_data
        return {"environments": environments}

    def _workspace_key(self, host: ShortcutHost, path: Path) -> str:
        normalized = str(path).replace("\\", "/").rstrip("/")
        return normalized.lower() if host == "windows_cygwin" else normalized


class FileTerminalRepository:
    def __init__(self, terminals_file: Path) -> None:
        self._terminals_file = terminals_file

    def get_state(self) -> TerminalState:
        if not self._terminals_file.exists():
            return TerminalState()
        try:
            raw = json.loads(self._terminals_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ShortcutRepositoryError("Terminal registry must be a JSON object")
            return TerminalState.model_validate(raw)
        except json.JSONDecodeError as exc:
            raise ShortcutRepositoryError("Terminal registry contains invalid JSON") from exc
        except ValidationError as exc:
            raise ShortcutRepositoryError("Terminal registry contains invalid terminal data") from exc

    def save_state(self, state: TerminalState) -> TerminalState:
        self._terminals_file.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self._terminals_file.name}.",
            suffix=".tmp",
            dir=self._terminals_file.parent,
            text=True,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                json.dump(state.model_dump(mode="json"), temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
            os.replace(temp_path, self._terminals_file)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        return state
