import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from termbridge.exceptions import (
    SessionNotFoundError,
    SessionRepositoryError,
    ShortcutRepositoryError,
)
from termbridge.models import SessionEntryRecord, SessionState, TerminalState, WorkspaceRecord


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

    def delete_workspace(self, workspace_id: str) -> None:
        state = self._read_state()
        if workspace_id not in state.workspaces:
            raise SessionNotFoundError(workspace_id)
        del state.workspaces[workspace_id]
        self._write_state(state)

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
        state.workspaces[workspace.id] = workspace.model_copy(update={"entries": entries, "updated_at": entry.updated_at})
        self._write_state(state)
        return entry

    def delete_entry(self, entry_id: str) -> WorkspaceRecord | None:
        state = self._read_state()
        for workspace in state.workspaces.values():
            entries = [entry for entry in workspace.entries if entry.id != entry_id]
            if len(entries) == len(workspace.entries):
                continue
            if entries:
                updated = workspace.model_copy(update={"entries": entries})
                state.workspaces[workspace.id] = updated
                self._write_state(state)
                return updated
            del state.workspaces[workspace.id]
            self._write_state(state)
            return None
        raise SessionNotFoundError(entry_id)

    def _read_state(self) -> SessionState:
        if not self._sessions_file.exists():
            return SessionState()
        try:
            raw = json.loads(self._sessions_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise SessionRepositoryError("Session registry must be a JSON object")
            if any(key != "workspaces" for key in raw):
                raise SessionRepositoryError("Session registry uses an incompatible schema")
            return SessionState.model_validate(raw)
        except json.JSONDecodeError as exc:
            raise SessionRepositoryError("Session registry contains invalid JSON") from exc
        except ValidationError as exc:
            raise SessionRepositoryError("Session registry contains invalid session data") from exc

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
                json.dump(state.model_dump(mode="json"), temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
            os.replace(temp_path, self._sessions_file)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise


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
