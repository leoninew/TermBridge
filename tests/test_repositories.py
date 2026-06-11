from pathlib import Path

import pytest

from termbridge.exceptions import SessionNotFoundError, SessionRepositoryError
from termbridge.models import SessionEntryRecord, SessionState, SessionStatus, TerminalState, WorkspaceRecord, utc_now
from termbridge.repositories import FileSessionRepository, FileTerminalRepository


def make_workspace(workspace_id: str = "ws_1") -> WorkspaceRecord:
    now = utc_now()
    entry = SessionEntryRecord(
        id="sess_1",
        workspace_id=workspace_id,
        name="Test",
        runtime="windows_cygwin",
        command=["ttyd", "--port", "9001", "bash"],
        port=9001,
        status=SessionStatus.RUNNING,
        pid=123,
        created_at=now,
        updated_at=now,
        url="http://127.0.0.1:9001",
        shortcut_id="cygwin-bash",
        shortcut_name="bash",
        host="windows_cygwin",
        tmux_session_name="tb_cyg_123",
        tmux_window_id="@1",
    )
    return WorkspaceRecord(
        id=workspace_id,
        host="windows_cygwin",
        path=Path.cwd(),
        name="TermBridge",
        tmux_session_name="tb_cyg_123",
        created_at=now,
        updated_at=now,
        entries=[entry],
    )


def test_repository_workspace_and_entry_crud(tmp_path: Path) -> None:
    repository = FileSessionRepository(tmp_path / "sessions.json")
    workspace = make_workspace()

    repository.upsert_workspace(workspace)
    assert repository.get_workspace(workspace.id).id == workspace.id
    assert repository.list_workspaces() == [workspace]
    assert repository.get_entry("sess_1")[1].id == "sess_1"

    updated_entry = workspace.entries[0].model_copy(update={"status": SessionStatus.STOPPED})
    repository.update_entry(updated_entry)
    assert repository.get_entry("sess_1")[1].status == SessionStatus.STOPPED

    empty_workspace = repository.delete_entry("sess_1")
    assert empty_workspace.entries == []
    assert repository.list_workspaces()[0].entries == []


def test_repository_missing_file_lists_empty(tmp_path: Path) -> None:
    assert FileSessionRepository(tmp_path / "missing.json").list_workspaces() == []


def test_repository_missing_session_raises(tmp_path: Path) -> None:
    repository = FileSessionRepository(tmp_path / "sessions.json")
    with pytest.raises(SessionNotFoundError):
        repository.get_entry("missing")


def test_repository_rejects_incompatible_flat_session_registry(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.json"
    sessions_file.write_text('{"sess_1": {"id": "sess_1"}}', encoding="utf-8")

    with pytest.raises(SessionRepositoryError, match="incompatible schema"):
        FileSessionRepository(sessions_file).list_workspaces()


def test_repository_invalid_json_raises(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.json"
    sessions_file.write_text("not-json", encoding="utf-8")

    with pytest.raises(SessionRepositoryError):
        FileSessionRepository(sessions_file).list_workspaces()


def test_session_repository_creates_missing_parent_directory(tmp_path: Path) -> None:
    sessions_file = tmp_path / "missing" / "state" / "sessions.json"

    FileSessionRepository(sessions_file).save_state(SessionState(workspaces={"ws_1": make_workspace()}))

    assert sessions_file.is_file()


def test_terminal_repository_creates_missing_parent_directory(tmp_path: Path) -> None:
    terminals_file = tmp_path / "missing" / "state" / "terminals.json"

    FileTerminalRepository(terminals_file).save_state(TerminalState())

    assert terminals_file.is_file()
