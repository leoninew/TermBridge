from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from termbridge.di import SessionServiceDep, TerminalServiceDep, WorkspaceBrowserServiceDep
from termbridge.exceptions import (
    InvalidTerminalCommandError,
    InvalidTerminalConfigError,
    NoAvailablePortError,
    SessionNotFoundError,
    SessionRepositoryError,
    ShortcutNotFoundError,
    ShortcutRepositoryError,
    UnknownRuntimeError,
    WorkspaceBrowserError,
    WorkspaceNotFoundError,
    WorkspacePathNotDirectoryError,
    WorkspacePathNotFoundError,
)
from termbridge.logging import configure_logging
from termbridge.middleware import RequestLoggingMiddleware
from termbridge.models import (
    CloseAllSessionsResponse,
    CreateSessionRequest,
    CreateShortcutRequest,
    EnvironmentListResponse,
    LinuxCheckResponse,
    RuntimeCheckRequest,
    RuntimeCheckResponse,
    SessionResponse,
    SessionTreeResponse,
    Shortcut,
    ShortcutListResponse,
    TerminalSettings,
    UpdateShortcutRequest,
    UpdateTerminalSettingsRequest,
    WindowsCygwinCheckRequest,
    WindowsCygwinCheckResponse,
    WindowsCygwinSettings,
    WindowsWslCheckResponse,
    WindowsWslSettings,
    WorkspaceRootsResponse,
    WorkspaceTreeResponse,
)
from termbridge.settings import load_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/workspaces/roots", response_model=WorkspaceRootsResponse)
def list_workspace_roots(service: WorkspaceBrowserServiceDep) -> WorkspaceRootsResponse:
    try:
        return service.list_roots()
    except WorkspaceBrowserError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/api/workspaces/tree", response_model=WorkspaceTreeResponse)
def list_workspace_tree(
    service: WorkspaceBrowserServiceDep,
    path: str = Query(min_length=1),
    show_hidden: bool = False,
) -> WorkspaceTreeResponse:
    try:
        return service.list_children(Path(path), show_hidden=show_hidden)
    except WorkspacePathNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WorkspacePathNotDirectoryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except WorkspaceBrowserError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/api/shortcuts", response_model=ShortcutListResponse)
def list_shortcuts(service: TerminalServiceDep) -> ShortcutListResponse:
    try:
        return service.list_shortcuts()
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/api/shortcuts", response_model=Shortcut, status_code=status.HTTP_201_CREATED)
def create_shortcut(request: CreateShortcutRequest, service: TerminalServiceDep) -> Shortcut:
    try:
        return service.create_shortcut(request)
    except InvalidTerminalConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.put("/api/shortcuts/{shortcut_id}", response_model=Shortcut)
def update_shortcut(shortcut_id: str, request: UpdateShortcutRequest, service: TerminalServiceDep) -> Shortcut:
    try:
        return service.update_shortcut(shortcut_id, request)
    except ShortcutNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shortcut not found") from exc
    except InvalidTerminalConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.delete("/api/shortcuts/{shortcut_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shortcut(shortcut_id: str, service: TerminalServiceDep, session_service: SessionServiceDep) -> Response:
    try:
        if any(session.shortcut_id == shortcut_id for session in session_service.list_sessions()):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shortcut is in use")
        service.delete_shortcut(shortcut_id)
    except HTTPException:
        raise
    except ShortcutNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shortcut not found") from exc
    except (SessionRepositoryError, ShortcutRepositoryError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/terminal-settings", response_model=TerminalSettings)
def get_terminal_settings(service: TerminalServiceDep) -> TerminalSettings:
    try:
        return service.get_settings()
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.put("/api/terminal-settings", response_model=TerminalSettings)
def update_terminal_settings(request: UpdateTerminalSettingsRequest, service: TerminalServiceDep) -> TerminalSettings:
    try:
        return service.update_settings(request)
    except InvalidTerminalConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/api/environment/ttyd/check", response_model=RuntimeCheckResponse)
def check_ttyd(request: RuntimeCheckRequest, service: TerminalServiceDep) -> RuntimeCheckResponse:
    return service.check_ttyd(request.path)


@router.get("/api/environments", response_model=EnvironmentListResponse)
def list_environments(service: TerminalServiceDep) -> EnvironmentListResponse:
    try:
        return service.list_environments()
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/api/environment/windows-cygwin/settings", response_model=WindowsCygwinSettings)
def get_windows_cygwin_settings(service: TerminalServiceDep) -> WindowsCygwinSettings:
    try:
        return service.get_windows_cygwin_settings()
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.put("/api/environment/windows-cygwin/settings", response_model=WindowsCygwinSettings)
def update_windows_cygwin_settings(
    request: WindowsCygwinSettings, service: TerminalServiceDep
) -> WindowsCygwinSettings:
    try:
        return service.update_windows_cygwin_settings(request)
    except InvalidTerminalConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/api/environment/windows-cygwin/check", response_model=WindowsCygwinCheckResponse)
def check_windows_cygwin(
    request: WindowsCygwinCheckRequest, service: TerminalServiceDep
) -> WindowsCygwinCheckResponse:
    return service.check_windows_cygwin(request.bash_path)


@router.get("/api/environment/windows-wsl/settings", response_model=WindowsWslSettings)
def get_windows_wsl_settings(service: TerminalServiceDep) -> WindowsWslSettings:
    try:
        return service.get_windows_wsl_settings()
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.put("/api/environment/windows-wsl/settings", response_model=WindowsWslSettings)
def update_windows_wsl_settings(request: WindowsWslSettings, service: TerminalServiceDep) -> WindowsWslSettings:
    try:
        return service.update_windows_wsl_settings(request)
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/api/environment/windows-wsl/check", response_model=WindowsWslCheckResponse)
def check_windows_wsl(service: TerminalServiceDep) -> WindowsWslCheckResponse:
    return service.check_windows_wsl()


@router.post("/api/environment/linux/check", response_model=LinuxCheckResponse)
def check_linux(service: TerminalServiceDep) -> LinuxCheckResponse:
    return service.check_linux()


@router.post("/api/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(request: CreateSessionRequest, service: SessionServiceDep) -> SessionResponse:
    try:
        return service.create(request)
    except (
        UnknownRuntimeError,
        InvalidTerminalCommandError,
        InvalidTerminalConfigError,
        WorkspaceNotFoundError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ShortcutNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shortcut not found") from exc
    except NoAvailablePortError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except SessionRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/api/sessions", response_model=list[SessionResponse])
def list_sessions(service: SessionServiceDep) -> list[SessionResponse]:
    try:
        return service.list_sessions()
    except SessionRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/api/session-tree", response_model=SessionTreeResponse)
def list_session_tree(service: SessionServiceDep) -> SessionTreeResponse:
    try:
        return service.list_tree()
    except SessionRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/api/sessions/close-all", response_model=CloseAllSessionsResponse)
def close_all_sessions(service: SessionServiceDep) -> CloseAllSessionsResponse:
    try:
        return service.close_all()
    except SessionRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.delete("/api/session-workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session_workspace(workspace_id: str, service: SessionServiceDep) -> Response:
    try:
        service.delete_workspace(workspace_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session workspace not found") from exc
    except SessionRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, service: SessionServiceDep) -> SessionResponse:
    try:
        return service.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc
    except SessionRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/api/sessions/{session_id}/start", response_model=SessionResponse)
def start_session(session_id: str, service: SessionServiceDep) -> SessionResponse:
    try:
        return service.start(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc
    except NoAvailablePortError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except SessionRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/api/sessions/{session_id}/stop", response_model=SessionResponse)
def stop_session(session_id: str, service: SessionServiceDep) -> SessionResponse:
    try:
        return service.stop(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc
    except SessionRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.delete("/api/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, service: SessionServiceDep) -> Response:
    try:
        service.delete(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc
    except SessionRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _default_frontend_dir() -> Path:
    return Path(__file__).parent / "static"


def _resolve_frontend_dir(frontend_dir: Path | None) -> Path | None:
    static_dir = frontend_dir or _default_frontend_dir()
    index_file = static_dir / "index.html"
    if index_file.is_file():
        return static_dir
    return None


def create_app(*, serve_frontend: bool = True, frontend_dir: Path | None = None) -> FastAPI:
    settings = load_settings()
    configure_logging(settings)

    app = FastAPI(title="TermBridge")
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(router)

    static_dir = _resolve_frontend_dir(frontend_dir) if serve_frontend else None
    if static_dir is not None:

        @app.get("/{path:path}", include_in_schema=False)
        def serve_frontend_app(path: str) -> FileResponse:
            if path == "health" or path.startswith("api/"):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

            requested_file = (static_dir / path).resolve()
            if requested_file.is_file() and requested_file.is_relative_to(static_dir.resolve()):
                return FileResponse(requested_file)
            return FileResponse(static_dir / "index.html")

    return app
