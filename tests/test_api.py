import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import websockets
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from termbridge.api import create_app
from termbridge.di import get_session_service, get_terminal_service
from termbridge.models import (
    CloseAllSessionsResponse,
    CreateSessionRequest,
    CreateShortcutRequest,
    EnvironmentListResponse,
    EnvironmentSummary,
    LinuxCheckResponse,
    ReorderSessionsRequest,
    ReorderWorkspacesRequest,
    RuntimeCheckResponse,
    SessionEnvironmentResponse,
    SessionResponse,
    SessionStatus,
    SessionTreeResponse,
    SessionWorkspaceResponse,
    ShortcutEnvironmentResponse,
    ShortcutListResponse,
    ShortcutResponse,
    TerminalSettings,
    TtydCredential,
    UpdateShortcutRequest,
    WindowsCygwinCheckResponse,
    WindowsCygwinSettings,
    WindowsWslCheckResponse,
    WindowsWslSettings,
)
from termbridge.services import TerminalProxyTarget
from termbridge.ttyd import TTYD_THEMES


class FakeSessionService:
    def __init__(self, *, with_session: bool = True, fail_list: bool = False) -> None:
        self.fail_list = fail_list
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
        self.deleted_workspaces: list[str] = []
        self.close_all_called = False

    def create(self, request: CreateSessionRequest) -> SessionResponse:
        return self.session.model_copy(
            update={"name": request.name, "workspace": str(request.workspace), "shortcut_id": request.shortcut_id}
        )

    def list_sessions(self) -> list[SessionResponse]:
        if self.fail_list:
            raise RuntimeError("boom")
        return self.sessions

    def get(self, session_id: str) -> SessionResponse:
        return self.session.model_copy(update={"id": session_id})

    def terminal_proxy_target(self, session_id: str) -> TerminalProxyTarget:
        return TerminalProxyTarget(
            base_url="http://127.0.0.1:19001",
            credential=TtydCredential(username="termbridge", password="secret"),
        )

    def start(self, session_id: str) -> SessionResponse:
        return self.session.model_copy(update={"id": session_id, "status": SessionStatus.RUNNING})

    def stop(self, session_id: str) -> SessionResponse:
        return self.session.model_copy(update={"id": session_id, "status": SessionStatus.STOPPED, "url": ""})

    def close_all(self) -> CloseAllSessionsResponse:
        self.close_all_called = True
        return CloseAllSessionsResponse(stopped_count=len(self.sessions), tmux_session_count=1 if self.sessions else 0)

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

    def reorder_workspaces(self, host: str, request: ReorderWorkspacesRequest) -> SessionTreeResponse:
        return self.list_tree()

    def reorder_sessions(self, workspace_id: str, request: ReorderSessionsRequest) -> SessionTreeResponse:
        self.sessions = [
            next(session for session in self.sessions if session.id == session_id) for session_id in request.session_ids
        ]
        return self.list_tree()

    def delete(self, session_id: str) -> None:
        self.deleted.append(session_id)

    def delete_workspace(self, workspace_id: str) -> None:
        self.deleted_workspaces.append(workspace_id)


class FakeTerminalService:
    def __init__(self) -> None:
        self.shortcuts = [
            ShortcutResponse(
                id="claude-code",
                name="Claude Code",
                command="claude",
                host="windows_cygwin",
                used_session_count=1,
            )
        ]
        self.deleted: list[str] = []

    def list_shortcuts(self) -> ShortcutListResponse:
        return ShortcutListResponse(
            environments=[
                ShortcutEnvironmentResponse(
                    host="windows_cygwin",
                    label="Cygwin",
                    shortcuts=self.shortcuts,
                ),
                ShortcutEnvironmentResponse(host="windows_wsl", label="WSL", shortcuts=[]),
                ShortcutEnvironmentResponse(host="linux", label="Linux", shortcuts=[]),
            ]
        )

    def create_shortcut(self, request: CreateShortcutRequest) -> ShortcutResponse:
        shortcut = ShortcutResponse(id="shortcut_new", used_session_count=0, **request.model_dump())
        self.shortcuts.append(shortcut)
        return shortcut

    def update_shortcut(self, shortcut_id: str, request: UpdateShortcutRequest) -> ShortcutResponse:
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


def test_web_static_routes(tmp_path: Path) -> None:
    web_dir = tmp_path / "web"
    assets_dir = web_dir / "assets"
    assets_dir.mkdir(parents=True)
    index_file = web_dir / "index.html"
    index_file.write_text("<html><body>TermBridge</body></html>", encoding="utf-8")
    asset_file = assets_dir / "app.js"
    asset_file.write_text("console.log('termbridge')", encoding="utf-8")
    client = TestClient(create_app(web_dir=web_dir))

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
    assert missing_api.json() == {"code": "not_found", "error": "Not found"}
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
    started = client.post("/api/sessions/sess_2/start")
    stopped = client.post("/api/sessions/sess_2/stop")
    close_all = client.post("/api/sessions/close-all")
    reordered_workspaces = client.put(
        "/api/session-tree/environments/windows_cygwin/workspaces/order",
        json={"workspace_ids": ["ws_1"]},
    )
    reordered_sessions = client.put(
        "/api/session-workspaces/ws_1/sessions/order",
        json={"session_ids": ["sess_1"]},
    )
    deleted_workspace = client.delete("/api/session-workspaces/ws_1")
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
    assert reordered_workspaces.status_code == 200
    assert reordered_workspaces.json()["environments"][0]["workspaces"][0]["id"] == "ws_1"
    assert reordered_sessions.status_code == 200
    assert reordered_sessions.json()["environments"][0]["workspaces"][0]["entries"][0]["id"] == "sess_1"
    assert started.status_code == 200
    assert started.json()["id"] == "sess_2"
    assert started.json()["status"] == "running"
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    assert close_all.status_code == 200
    assert close_all.json() == {"stopped_count": 1, "tmux_session_count": 1}
    assert service.close_all_called is True
    assert deleted_workspace.status_code == 204
    assert deleted.status_code == 204
    assert service.deleted_workspaces == ["ws_1"]
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
    assert listed.json()["environments"][0]["shortcuts"][0]["id"] == "claude-code"
    assert listed.json()["environments"][0]["shortcuts"][0]["used_session_count"] == 1
    assert created.status_code == 201
    assert created.json()["id"] == "shortcut_new"
    assert updated.status_code == 200
    assert updated.json()["command"] == "claude"
    assert deleted.status_code == 204
    assert service.deleted == ["claude-code"]


def test_api_validation_error_uses_structured_error() -> None:
    client = make_client(FakeSessionService())

    response = client.post("/api/sessions", json={"name": "Missing fields"})

    assert response.status_code == 422
    assert response.json() == {"code": "validation_error", "error": "Validation error"}


def test_api_unhandled_exception_uses_structured_error() -> None:
    client = make_client(FakeSessionService(fail_list=True))

    response = client.get("/api/sessions")

    assert response.status_code == 500
    assert response.json() == {"code": "internal_error", "error": "Internal server error"}


def test_terminal_http_proxy_adds_basic_auth_header() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200, content=b"terminal", headers={"content-type": "text/plain", "transfer-encoding": "chunked"}
        )

    app = create_app(serve_web=False)
    app.dependency_overrides[get_session_service] = lambda: FakeSessionService()
    app.router.on_startup.clear()
    client = TestClient(app)
    transport = httpx.MockTransport(handler)

    class MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    try:
        response = client.get("/terminal/sess_1/token?x=1&theme=light")
    finally:
        monkeypatch.undo()

    assert response.status_code == 200
    assert response.text == "terminal"
    assert response.headers["content-type"] == "text/plain"
    assert "transfer-encoding" not in response.headers
    assert captured["authorization"] == "Basic dGVybWJyaWRnZTpzZWNyZXQ="
    upstream_url = urlsplit(str(captured["url"]))
    assert f"{upstream_url.scheme}://{upstream_url.netloc}{upstream_url.path}" == "http://127.0.0.1:19001/token"
    upstream_query = parse_qs(upstream_url.query)
    assert upstream_query == {"x": ["1"], "theme": [TTYD_THEMES["light"]]}


def test_terminal_websocket_upstream_close_is_not_logged_as_proxy_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class ClosingUpstream:
        close_code: int | None = None
        close_reason: str | None = None

        async def __aenter__(self) -> "ClosingUpstream":
            return self

        async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

        def __aiter__(self) -> "ClosingUpstream":
            return self

        async def __anext__(self) -> str:
            raise websockets.ConnectionClosedError(None, None)

        async def send(self, message: str | bytes) -> None:
            return None

        async def close(self) -> None:
            return None

    app = create_app(serve_web=False)
    app.dependency_overrides[get_session_service] = lambda: FakeSessionService()
    app.router.on_startup.clear()
    client = TestClient(app)
    monkeypatch.setattr(websockets, "connect", lambda *args, **kwargs: ClosingUpstream())
    records: list[logging.LogRecord] = []

    class ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    api_logger = logging.getLogger("termbridge.api")
    handler = ListHandler()
    api_logger.addHandler(handler)
    try:
        with caplog.at_level(logging.INFO, logger="termbridge.api"):
            with client.websocket_connect("/terminal/sess_1/ws", subprotocols=["tty"]) as websocket:
                with pytest.raises(WebSocketDisconnect):
                    websocket.receive_text()
    finally:
        api_logger.removeHandler(handler)

    assert not any("Terminal websocket proxy failed" in record.getMessage() for record in records)
    assert any("Terminal websocket upstream disconnected" in record.getMessage() for record in records)


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
