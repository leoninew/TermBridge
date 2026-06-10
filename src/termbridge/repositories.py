import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from termbridge.exceptions import (
    DuplicateSessionError,
    SessionNotFoundError,
    SessionRepositoryError,
    ShortcutRepositoryError,
)
from termbridge.models import SessionRecord, TerminalState


class FileSessionRepository:
    def __init__(self, sessions_file: Path) -> None:
        self._sessions_file = sessions_file

    def create(self, session: SessionRecord) -> SessionRecord:
        sessions = self._read_all()
        if session.id in sessions:
            raise DuplicateSessionError(session.id)
        sessions[session.id] = session
        self._write_all(sessions)
        return session

    def list(self) -> list[SessionRecord]:
        return list(self._read_all().values())

    def get(self, session_id: str) -> SessionRecord:
        session = self._read_all().get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def update(self, session: SessionRecord) -> SessionRecord:
        sessions = self._read_all()
        if session.id not in sessions:
            raise SessionNotFoundError(session.id)
        sessions[session.id] = session
        self._write_all(sessions)
        return session

    def delete(self, session_id: str) -> None:
        sessions = self._read_all()
        if session_id not in sessions:
            raise SessionNotFoundError(session_id)
        del sessions[session_id]
        self._write_all(sessions)

    def _read_all(self) -> dict[str, SessionRecord]:
        if not self._sessions_file.exists():
            return {}
        try:
            raw = json.loads(self._sessions_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise SessionRepositoryError("Session registry must be a JSON object")
            return {session_id: SessionRecord.model_validate(value) for session_id, value in raw.items()}
        except json.JSONDecodeError as exc:
            raise SessionRepositoryError("Session registry contains invalid JSON") from exc
        except ValidationError as exc:
            raise SessionRepositoryError("Session registry contains invalid session data") from exc

    def _write_all(self, sessions: dict[str, SessionRecord]) -> None:
        self._sessions_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {session_id: session.model_dump(mode="json") for session_id, session in sessions.items()}
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self._sessions_file.name}.",
            suffix=".tmp",
            dir=self._sessions_file.parent,
            text=True,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                json.dump(payload, temp_file, ensure_ascii=False, indent=2)
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
