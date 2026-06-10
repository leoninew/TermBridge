from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from termbridge.api import create_app
from termbridge.di import get_session_service, get_terminal_service
from termbridge.models import (
    CreateSessionRequest,
    CreateShortcutRequest,
    CygwinCheckResponse,
    CygwinSettings,
    RuntimeCheckResponse,
    SessionResponse,
    SessionStatus,
    Shortcut,
    ShortcutListResponse,
    TerminalSettings,
    TmuxAvailabilityResponse,
    UpdateShortcutRequest,
    WindowsCheckResponse,
    WslCheckResponse,
)


class FakeSessionService:
    def __init__(self, *, with_session: bool = True) -> None:
        now = datetime(2026, 6, 8, tzinfo=UTC)
        self.session = SessionResponse(
            id="sess_1",
            name="Test",
            workspace=str(Path.cwd()),
            runtime="cygwin_tmux",
            status=SessionStatus.RUNNING,
            port=9001,
            url="http://127.0.0.1:9001",
            shortcut_id="claude-code",
            shortcut_name="Claude Code",
            host="cygwin_tmux",
            session_persistence="tmux",
            tmux_session_name="Test",
            created_at=now,
            updated_at=now,
        )
        self.sessions = [self.session] if with_session else []
        self.deleted: list[str] = []

    def create(self, request: CreateSessionRequest) -> SessionResponse:
        return self.session.model_copy(
            update={"name": request.name, "workspace": str(request.workspace), "shortcut_id": request.shortcut_id}
        )

    def list_sessions(self) -> list[SessionResponse]:
        return self.sessions

    def get(self, session_id: str) -> SessionResponse:
        return self.session.model_copy(update={"id": session_id})

    def restart(self, session_id: str) -> SessionResponse:
        return self.session.model_copy(update={"id": session_id, "status": SessionStatus.RUNNING})

    def delete(self, session_id: str) -> None:
        self.deleted.append(session_id)


class FakeTerminalService:
    def __init__(self) -> None:
        self.shortcuts = [
            Shortcut(
                id="claude-code",
                name="Claude Code",
                command="claude --dangerously-skip-permissions",
                host="cygwin_tmux",
            )
        ]
        self.deleted: list[str] = []

    def list_shortcuts(self) -> ShortcutListResponse:
        return ShortcutListResponse(shortcuts=self.shortcuts)

    def create_shortcut(self, request: CreateShortcutRequest) -> Shortcut:
        shortcut = Shortcut(id="shortcut_new", **request.model_dump())
        self.shortcuts.append(shortcut)
        return shortcut

    def update_shortcut(self, shortcut_id: str, request: UpdateShortcutRequest) -> Shortcut:
        shortcut = self.shortcuts[0].model_copy(update=request.model_dump(exclude_unset=True))
        self.shortcuts[0] = shortcut
        return shortcut

    def delete_shortcut(self, shortcut_id: str) -> None:
        self.deleted.append(shortcut_id)

    def check_tmux(self, cygwin_bash_path: str) -> TmuxAvailabilityResponse:
        return TmuxAvailabilityResponse(available=True, path="/usr/bin/tmux", version="tmux 3.2")

    def get_settings(self) -> TerminalSettings:
        return TerminalSettings()

    def update_settings(self, request: TerminalSettings) -> TerminalSettings:
        return request

    def check_ttyd(self, ttyd_path: str | None = None) -> RuntimeCheckResponse:
        return RuntimeCheckResponse(available=True, path=ttyd_path or "ttyd", version="ttyd 1.7.7")

    def get_cygwin_settings(self) -> CygwinSettings:
        return CygwinSettings()

    def update_cygwin_settings(self, request: CygwinSettings) -> CygwinSettings:
        return request

    def check_cygwin(self, bash_path: str | None = None) -> CygwinCheckResponse:
        return CygwinCheckResponse(
            bash=RuntimeCheckResponse(available=True, path=bash_path or "/usr/bin/bash", version="GNU bash"),
            tmux=RuntimeCheckResponse(available=True, path="/usr/bin/tmux", version="tmux 3.2"),
        )

    def check_windows(self) -> WindowsCheckResponse:
        return WindowsCheckResponse(
            host=RuntimeCheckResponse(available=True, path="nt"),
            shells=[RuntimeCheckResponse(available=True, path="cmd")],
        )

    def check_wsl(self) -> WslCheckResponse:
        return WslCheckResponse(wsl=RuntimeCheckResponse(available=False, path="wsl", reason="not installed"))


def make_client(service: FakeSessionService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session_service] = lambda: service
    return TestClient(app)


def test_health() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_session_api_routes(tmp_path: Path) -> None:
    service = FakeSessionService()
    client = make_client(service)

    created = client.post(
        "/api/sessions", json={"name": "New", "workspace": str(tmp_path), "shortcut_id": "claude-code"}
    )
    listed = client.get("/api/sessions")
    detail = client.get("/api/sessions/sess_2")
    restarted = client.post("/api/sessions/sess_2/restart")
    deleted = client.delete("/api/sessions/sess_2")

    assert created.status_code == 201
    assert created.json()["name"] == "New"
    assert created.json()["shortcut_id"] == "claude-code"
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert detail.status_code == 200
    assert detail.json()["id"] == "sess_2"
    assert detail.json()["shortcut_name"] == "Claude Code"
    assert detail.json()["session_persistence"] == "tmux"
    assert restarted.status_code == 200
    assert restarted.json()["id"] == "sess_2"
    assert restarted.json()["status"] == "running"
    assert deleted.status_code == 204
    assert service.deleted == ["sess_2"]


def test_shortcut_api_routes() -> None:
    service = FakeTerminalService()
    session_service = FakeSessionService(with_session=False)
    app = create_app()
    app.dependency_overrides[get_terminal_service] = lambda: service
    app.dependency_overrides[get_session_service] = lambda: session_service
    client = TestClient(app)

    listed = client.get("/api/shortcuts")
    created = client.post("/api/shortcuts", json={"name": "Codex", "command": "codex", "host": "cygwin_tmux"})
    updated = client.put("/api/shortcuts/claude-code", json={"command": "claude"})
    deleted = client.delete("/api/shortcuts/claude-code")

    assert listed.status_code == 200
    assert listed.json()["shortcuts"][0]["id"] == "claude-code"
    assert created.status_code == 201
    assert created.json()["id"] == "shortcut_new"
    assert updated.status_code == 200
    assert updated.json()["command"] == "claude"
    assert deleted.status_code == 204
    assert service.deleted == ["claude-code"]


def test_shortcut_delete_rejects_in_use_shortcut() -> None:
    service = FakeTerminalService()
    session_service = FakeSessionService()
    app = create_app()
    app.dependency_overrides[get_terminal_service] = lambda: service
    app.dependency_overrides[get_session_service] = lambda: session_service
    client = TestClient(app)

    response = client.delete("/api/shortcuts/claude-code")

    assert response.status_code == 409
    assert response.json()["detail"] == "Shortcut is in use"
    assert service.deleted == []


def test_tmux_check_api() -> None:
    app = create_app()
    app.dependency_overrides[get_terminal_service] = lambda: FakeTerminalService()
    client = TestClient(app)

    response = client.post("/api/terminals/tmux/check", json={"cygwin_bash_path": "bash.exe"})

    assert response.status_code == 200
    assert response.json() == {"available": True, "path": "/usr/bin/tmux", "version": "tmux 3.2", "reason": None}


def test_environment_api_routes() -> None:
    app = create_app()
    app.dependency_overrides[get_terminal_service] = lambda: FakeTerminalService()
    client = TestClient(app)

    ttyd = client.get("/api/environment/ttyd/check", params={"path": "D:/ttyd.exe"})
    cygwin_settings = client.get("/api/environment/cygwin-settings")
    saved_cygwin_settings = client.put(
        "/api/environment/cygwin-settings",
        json={"bash_path": "D:/cygwin/bin/bash.exe", "tmux_path": "D:/cygwin/bin/tmux.exe"},
    )
    cygwin = client.get("/api/environment/cygwin/check", params={"bash_path": "bash.exe"})
    windows = client.get("/api/environment/windows/check")
    wsl = client.get("/api/environment/wsl/check")

    assert ttyd.status_code == 200
    assert ttyd.json()["path"] == "D:/ttyd.exe"
    assert cygwin_settings.json() == {"bash_path": None, "tmux_path": None}
    assert saved_cygwin_settings.json() == {
        "bash_path": "D:/cygwin/bin/bash.exe",
        "tmux_path": "D:/cygwin/bin/tmux.exe",
    }
    assert cygwin.json()["tmux"]["version"] == "tmux 3.2"
    assert windows.json()["shells"][0]["path"] == "cmd"
    assert wsl.json()["wsl"]["available"] is False
