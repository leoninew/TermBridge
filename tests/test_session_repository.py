import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from termbridge.exceptions import SessionRepositoryError
from termbridge.models import SessionEntryRecord, SessionState, SessionStatus, WorkspaceRecord
from termbridge.repositories import FileSessionRepository


def make_workspace(tmp_path: Path) -> WorkspaceRecord:
    now = datetime(2026, 6, 11, tzinfo=UTC)
    entry = SessionEntryRecord(
        id="sess_one",
        workspace_id="ws_one",
        name="Agent",
        runtime="windows_cygwin",
        command=[],
        port=19001,
        status=SessionStatus.RUNNING,
        pid=100,
        created_at=now,
        updated_at=now,
        url="http://127.0.0.1:19001",
        shortcut_id="shortcut_one",
        shortcut_name="Claude Code",
        host="windows_cygwin",
        tmux_session_name="tb_cyg_one",
        tmux_window_id="@1",
    )
    return WorkspaceRecord(
        id="ws_one",
        host="windows_cygwin",
        path=tmp_path / "Repo",
        name="Repo",
        tmux_session_name="tb_cyg_one",
        created_at=now,
        updated_at=now,
        entries=[entry],
    )


def test_session_repository_writes_environment_workspace_session_schema(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.json"
    workspace = make_workspace(tmp_path)
    repository = FileSessionRepository(sessions_file)

    repository.save_state(SessionState(workspaces={workspace.id: workspace}))

    raw = json.loads(sessions_file.read_text(encoding="utf-8"))
    workspace_key = str(workspace.path).replace("\\", "/").lower()
    assert set(raw) == {"environments"}
    assert set(raw["environments"]) == {"windows_cygwin", "windows_wsl", "linux"}
    assert raw["environments"]["windows_cygwin"][workspace_key]["sessions"]["Agent"]["id"] == "sess_one"


def test_session_repository_rejects_legacy_workspace_schema(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.json"
    workspace = make_workspace(tmp_path)
    sessions_file.write_text(
        json.dumps({"workspaces": {workspace.id: workspace.model_dump(mode="json")}}),
        encoding="utf-8",
    )
    repository = FileSessionRepository(sessions_file)

    with pytest.raises(SessionRepositoryError, match="incompatible schema"):
        repository.get_state()


def test_session_repository_reads_environment_workspace_session_schema(tmp_path: Path) -> None:
    sessions_file = tmp_path / "sessions.json"
    workspace = make_workspace(tmp_path)
    repository = FileSessionRepository(sessions_file)
    repository.save_state(SessionState(workspaces={workspace.id: workspace}))

    state = FileSessionRepository(sessions_file).get_state()

    assert list(state.workspaces) == ["ws_one"]
    assert state.workspaces["ws_one"].entries[0].tmux_window_id == "@1"
