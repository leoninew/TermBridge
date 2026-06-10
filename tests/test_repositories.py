from pathlib import Path

import pytest

from termbridge.exceptions import SessionNotFoundError, SessionRepositoryError
from termbridge.models import SessionRecord, SessionStatus, TerminalState, utc_now
from termbridge.repositories import FileSessionRepository, FileTerminalRepository


def make_session(session_id: str = "sess_1", port: int = 9001) -> SessionRecord:
    now = utc_now()
    return SessionRecord(
        id=session_id,
        name="Test",
        workspace=Path.cwd(),
        runtime="bash",
        command=["ttyd", "--port", str(port), "bash"],
        port=port,
        status=SessionStatus.RUNNING,
        pid=123,
        created_at=now,
        updated_at=now,
        url=f"http://127.0.0.1:{port}",
    )


def test_repository_crud(tmp_path: Path) -> None:
    repository = FileSessionRepository(tmp_path / "sessions.json")
    session = make_session()

    repository.create(session)
    assert repository.get(session.id).id == session.id
    assert repository.list() == [session]

    updated = session.model_copy(update={"status": SessionStatus.STOPPED})
    repository.update(updated)
    assert repository.get(session.id).status == SessionStatus.STOPPED

    repository.delete(session.id)
    assert repository.list() == []


def test_repository_missing_file_lists_empty(tmp_path: Path) -> None:
    assert FileSessionRepository(tmp_path / "missing.json").list() == []


def test_repository_missing_session_raises(tmp_path: Path) -> None:
    repository = FileSessionRepository(tmp_path / "sessions.json")
    with pytest.raises(SessionNotFoundError):
        repository.get("missing")


def test_repository_invalid_json_raises(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.json"
    sessions_file.write_text("not-json", encoding="utf-8")

    with pytest.raises(SessionRepositoryError):
        FileSessionRepository(sessions_file).list()


def test_session_repository_creates_missing_parent_directory(tmp_path: Path) -> None:
    sessions_file = tmp_path / "missing" / "state" / "sessions.json"

    FileSessionRepository(sessions_file).create(make_session())

    assert sessions_file.is_file()


def test_terminal_repository_creates_missing_parent_directory(tmp_path: Path) -> None:
    terminals_file = tmp_path / "missing" / "state" / "terminals.json"

    FileTerminalRepository(terminals_file).save_state(TerminalState())

    assert terminals_file.is_file()
