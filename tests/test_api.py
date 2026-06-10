from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from termbridge.api import create_app
from termbridge.di import get_session_service, get_terminal_service
from termbridge.models import (
    CreateSessionRequest,
    CreateShortcutRequest,
    EnvironmentListResponse,
    EnvironmentSummary,
    LinuxCheckResponse,
    RuntimeCheckResponse,
    SessionEnvironmentResponse,
    SessionResponse,
    SessionStatus,
    SessionTreeResponse,
    SessionWorkspaceResponse,
    Shortcut,
    ShortcutListResponse,
    TerminalSettings,
    UpdateShortcutRequest,
    WindowsCygwinCheckResponse,
    WindowsCygwinSettings,
    WindowsWslCheckResponse,
    WindowsWslSettings,
)


class FakeSessionService:
    def __init__(self, *, with_session: bool = True) -> None:
        now = datetime(2026, 6, 8, tzinfo=UTC)
        self.session = SessionResponse(
            id="sess_1",
            workspace_id="ws_1",
            name="Test",
            workspace=str(Path.cwd()),
            runtime="windows_cygwin",
            status=SessionStatus.RUNNING,
            port=9001,
            url="http://127.0.0.1:9001",
            shortcut_id="claude-code",
            shortcut_name="Claude Code",
            host="windows_cygwin",
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

    def stop(self, session_id: str) -> SessionResponse:
        return self.session.model_copy(update={"id": session_id, "status": SessionStatus.STOPPED, "url": ""})

    def list_tree(self) -> SessionTreeResponse:
        return SessionTreeResponse(
            environments=[
                SessionEnvironmentResponse(
                    host="windows_cygwin",
                    label="Windows/Cygwin",
                    workspaces=[
                        SessionWorkspaceResponse(
                            id="ws_1",
                            host="windows_cygwin",
                            name="TermBridge",
                            path=str(Path.cwd()),
                            status=SessionStatus.RUNNING,
                            entries=self.sessions,
                        )
                    ]
                    if self.sessions
                    else [],
                )
            ]
        )

    def delete(self, session_id: str) -> None:
        self.deleted.append(session_id)


class FakeTerminalService:
    def __init__(self) -> None:
        self.shortcuts = [
            Shortcut(
                id="claude-code",
                name="Claude Code",
                command="claude --dangerously-skip-permissions",
                host="windows_cygwin",
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

    def get_settings(self) -> TerminalSettings:
        return TerminalSettings()

    def update_settings(self, request: TerminalSettings) -> TerminalSettings:
        return request

    def check_ttyd(self, ttyd_path: str | None = None) -> RuntimeCheckResponse:
        return RuntimeCheckResponse(available=True, path=ttyd_path or "ttyd", version="ttyd 1.7.7")

    def list_environments(self) -> EnvironmentListResponse:
        return EnvironmentListResponse(
            environments=[
                EnvironmentSummary(
                    host="windows_cygwin",
                    label="Windows/Cygwin",
                    readiness="not_ready",
                    available_on_host=True,
                ),
                EnvironmentSummary(
                    host="windows_wsl",
                    label="Windows/WSL",
                    readiness="not_ready",
                    available_on_host=True,
                ),
                EnvironmentSummary(
                    host="linux",
                    label="Linux",
                    readiness="not_ready",
                    available_on_host=False,
                    last_error="Linux environment is unavailable on this host",
                ),
            ],
        )

    def get_windows_cygwin_settings(self) -> WindowsCygwinSettings:
        return WindowsCygwinSettings()

    def update_windows_cygwin_settings(self, request: WindowsCygwinSettings) -> WindowsCygwinSettings:
        return request

    def check_windows_cygwin(self, bash_path: str | None = None) -> WindowsCygwinCheckResponse:
        return WindowsCygwinCheckResponse(
            host=RuntimeCheckResponse(available=True, path="nt"),
            bash=RuntimeCheckResponse(available=True, path=bash_path or "/usr/bin/bash", version="GNU bash"),
            tmux=RuntimeCheckResponse(available=True, path="/usr/bin/tmux", version="tmux 3.2"),
        )

    def get_windows_wsl_settings(self) -> WindowsWslSettings:
        return WindowsWslSettings()

    def update_windows_wsl_settings(self, request: WindowsWslSettings) -> WindowsWslSettings:
        return request

    def check_windows_wsl(self) -> WindowsWslCheckResponse:
        return WindowsWslCheckResponse(
            host=RuntimeCheckResponse(available=True, path="nt"),
            wsl=RuntimeCheckResponse(available=False, path="wsl", reason="not installed"),
        )

    def check_linux(self) -> LinuxCheckResponse:
        return LinuxCheckResponse(
            host=RuntimeCheckResponse(
                available=False, path="Windows", reason="Linux environment is unavailable on this host"
            )
        )


def make_client(service: FakeSessionService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session_service] = lambda: service
    return TestClient(app)


def test_health() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_static_routes(tmp_path: Path) -> None:
    frontend_dir = tmp_path / "frontend"
    assets_dir = frontend_dir / "assets"
    assets_dir.mkdir(parents=True)
    index_file = frontend_dir / "index.html"
    index_file.write_text("<html><body>TermBridge</body></html>", encoding="utf-8")
    asset_file = assets_dir / "app.js"
    asset_file.write_text("console.log('termbridge')", encoding="utf-8")
    client = TestClient(create_app(frontend_dir=frontend_dir))

    root = client.get("/")
    environment = client.get("/environment")
    shortcuts = client.get("/shortcuts")
    asset = client.get("/assets/app.js")
    missing_api = client.get("/api/missing")
    health_response = client.get("/health")

    assert root.status_code == 200
    assert "TermBridge" in root.text
    assert environment.status_code == 200
    assert "TermBridge" in environment.text
    assert shortcuts.status_code == 200
    assert "TermBridge" in shortcuts.text
    assert asset.status_code == 200
    assert asset.text == "console.log('termbridge')"
    assert missing_api.status_code == 404
    assert missing_api.json() == {"detail": "Not found"}
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}


def test_session_api_routes(tmp_path: Path) -> None:
    service = FakeSessionService()
    client = make_client(service)

    created = client.post(
        "/api/sessions", json={"name": "New", "workspace": str(tmp_path), "shortcut_id": "claude-code"}
    )
    listed = client.get("/api/sessions")
    detail = client.get("/api/sessions/sess_2")
    tree = client.get("/api/session-tree")
    restarted = client.post("/api/sessions/sess_2/restart")
    stopped = client.post("/api/sessions/sess_2/stop")
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
    assert tree.status_code == 200
    assert tree.json()["environments"][0]["workspaces"][0]["entries"][0]["id"] == "sess_1"
    assert restarted.status_code == 200
    assert restarted.json()["id"] == "sess_2"
    assert restarted.json()["status"] == "running"
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
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
    created = client.post("/api/shortcuts", json={"name": "Codex", "command": "codex", "host": "windows_cygwin"})
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


def test_environment_api_routes() -> None:
    app = create_app()
    app.dependency_overrides[get_terminal_service] = lambda: FakeTerminalService()
    client = TestClient(app)

    ttyd = client.post("/api/environment/ttyd/check", json={"path": "D:/ttyd.exe"})
    environments = client.get("/api/environments")
    windows_cygwin_settings = client.get("/api/environment/windows-cygwin/settings")
    saved_windows_cygwin_settings = client.put(
        "/api/environment/windows-cygwin/settings",
        json={
            "readiness": "not_ready",
            "bash_path": "D:/cygwin/bin/bash.exe",
            "tmux_path": "D:/cygwin/bin/tmux.exe",
            "checked_at": None,
            "last_error": None,
        },
    )
    windows_cygwin = client.post("/api/environment/windows-cygwin/check", json={"bash_path": "bash.exe"})
    windows_wsl_settings = client.get("/api/environment/windows-wsl/settings")
    windows_wsl = client.post("/api/environment/windows-wsl/check")
    linux = client.post("/api/environment/linux/check")

    assert ttyd.status_code == 200
    assert ttyd.json()["path"] == "D:/ttyd.exe"
    assert environments.status_code == 200
    assert len(environments.json()["environments"]) == 3
    assert windows_cygwin_settings.json()["readiness"] == "not_ready"
    assert windows_cygwin_settings.json()["bash_path"] is None
    assert saved_windows_cygwin_settings.json()["bash_path"] == "D:/cygwin/bin/bash.exe"
    assert saved_windows_cygwin_settings.json()["tmux_path"] == "D:/cygwin/bin/tmux.exe"
    assert windows_cygwin.json()["host"]["available"] is True
    assert windows_cygwin.json()["tmux"]["version"] == "tmux 3.2"
    assert windows_wsl_settings.json()["readiness"] == "not_ready"
    assert windows_wsl.json()["wsl"]["available"] is False
    assert linux.json()["host"]["available"] is False
