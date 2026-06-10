from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Query, Response, status

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
    CreateSessionRequest,
    CreateShortcutRequest,
    CygwinCheckResponse,
    CygwinSettings,
    RuntimeCheckResponse,
    SessionResponse,
    Shortcut,
    ShortcutListResponse,
    TerminalSettings,
    TmuxAvailabilityRequest,
    TmuxAvailabilityResponse,
    UpdateShortcutRequest,
    UpdateTerminalSettingsRequest,
    WindowsCheckResponse,
    WorkspaceRootsResponse,
    WorkspaceTreeResponse,
    WslCheckResponse,
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


@router.post("/api/terminals/tmux/check", response_model=TmuxAvailabilityResponse)
def check_tmux(request: TmuxAvailabilityRequest, service: TerminalServiceDep) -> TmuxAvailabilityResponse:
    return service.check_tmux(request.cygwin_bash_path)


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


@router.get("/api/environment/ttyd/check", response_model=RuntimeCheckResponse)
def check_ttyd(service: TerminalServiceDep, path: str | None = Query(default=None)) -> RuntimeCheckResponse:
    return service.check_ttyd(path)


@router.get("/api/environment/cygwin-settings", response_model=CygwinSettings)
def get_cygwin_settings(service: TerminalServiceDep) -> CygwinSettings:
    try:
        return service.get_cygwin_settings()
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.put("/api/environment/cygwin-settings", response_model=CygwinSettings)
def update_cygwin_settings(request: CygwinSettings, service: TerminalServiceDep) -> CygwinSettings:
    try:
        return service.update_cygwin_settings(request)
    except InvalidTerminalConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ShortcutRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/api/environment/cygwin/check", response_model=CygwinCheckResponse)
def check_cygwin(service: TerminalServiceDep, bash_path: str | None = Query(default=None)) -> CygwinCheckResponse:
    return service.check_cygwin(bash_path)


@router.get("/api/environment/windows/check", response_model=WindowsCheckResponse)
def check_windows(service: TerminalServiceDep) -> WindowsCheckResponse:
    return service.check_windows()


@router.get("/api/environment/wsl/check", response_model=WslCheckResponse)
def check_wsl(service: TerminalServiceDep) -> WslCheckResponse:
    return service.check_wsl()


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


@router.get("/api/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, service: SessionServiceDep) -> SessionResponse:
    try:
        return service.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc
    except SessionRepositoryError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/api/sessions/{session_id}/restart", response_model=SessionResponse)
def restart_session(session_id: str, service: SessionServiceDep) -> SessionResponse:
    try:
        return service.restart(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc
    except NoAvailablePortError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
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


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings)

    app = FastAPI(title="TermBridge")
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(router)
    return app
