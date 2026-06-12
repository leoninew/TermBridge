import asyncio
import base64
import logging
from pathlib import Path
from typing import Any

import httpx
import websockets
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from websockets.typing import Origin, Subprotocol

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
logger = logging.getLogger(__name__)

STATUS_ERROR_CODES = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
}
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
}


def _error_code(status_code: int) -> str:
    return STATUS_ERROR_CODES.get(status_code, "request_failed")


def _error_message(detail: Any, fallback: str) -> str:
    if isinstance(detail, str) and detail:
        return detail
    return fallback


def _error_response(status_code: int, code: str, error: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code, "error": error})


def _basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


def _target_headers(credential: Any | None) -> dict[str, str]:
    if credential is None:
        return {}
    return {"Authorization": _basic_auth_header(credential.username, credential.password)}


def _proxy_headers(headers: httpx.Headers) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() not in HOP_BY_HOP_HEADERS}


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return await unhandled_exception_handler(request, exc)
    code = _error_code(exc.status_code)
    error = _error_message(exc.detail, "Request failed")
    return _error_response(exc.status_code, code, error)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return await unhandled_exception_handler(request, exc)
    return _error_response(status.HTTP_422_UNPROCESSABLE_CONTENT, "validation_error", "Validation error")


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled request error path=%s", request.url.path)
    return _error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "Internal server error")


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
    except InvalidTerminalConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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


@router.get("/terminal/{session_id}", include_in_schema=False)
def redirect_terminal_root(session_id: str) -> RedirectResponse:
    return RedirectResponse(url=f"/terminal/{session_id}/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/terminal/{session_id}/{path:path}", include_in_schema=False)
async def proxy_terminal_http(session_id: str, path: str, request: Request, service: SessionServiceDep) -> Response:
    try:
        target = service.terminal_proxy_target(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from exc
    except InvalidTerminalConfigError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    target_path = path or ""
    target_url = f"{target.base_url.rstrip('/')}/{target_path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"
    headers = _target_headers(target.credential)
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        try:
            upstream = await client.request(request.method, target_url, headers=headers, content=await request.body())
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Terminal proxy request failed") from exc
    return Response(content=upstream.content, status_code=upstream.status_code, headers=_proxy_headers(upstream.headers))


@router.websocket("/terminal/{session_id}/ws")
async def proxy_terminal_websocket(session_id: str, websocket: WebSocket, service: SessionServiceDep) -> None:
    try:
        target = service.terminal_proxy_target(session_id)
    except (SessionNotFoundError, InvalidTerminalConfigError):
        await websocket.close(code=1008)
        return
    target_url = target.base_url.replace("http://", "ws://", 1).replace("https://", "wss://", 1).rstrip("/")
    query = websocket.url.query
    if query:
        target_url = f"{target_url}/ws?{query}"
    else:
        target_url = f"{target_url}/ws"
    requested_subprotocols = [
        item.strip()
        for item in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if item.strip()
    ]
    subprotocol = Subprotocol("tty") if "tty" in requested_subprotocols else None
    accepted = False
    try:
        async with websockets.connect(
            target_url,
            additional_headers=_target_headers(target.credential),
            origin=Origin(target.base_url),
            subprotocols=[subprotocol] if subprotocol else None,
            proxy=None,
        ) as upstream:
            await websocket.accept(subprotocol=subprotocol)
            accepted = True
            logger.info(
                "Terminal websocket proxy connected session_id=%s target=%s subprotocol=%s",
                session_id,
                target_url,
                subprotocol,
            )
            client_message_count = 0
            upstream_message_count = 0

            async def client_to_upstream() -> None:
                nonlocal client_message_count
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        logger.info(
                            "Terminal websocket client disconnected session_id=%s code=%s client_messages=%s upstream_messages=%s",
                            session_id,
                            message.get("code"),
                            client_message_count,
                            upstream_message_count,
                        )
                        await upstream.close()
                        return
                    if message.get("bytes") is not None:
                        client_message_count += 1
                        logger.debug(
                            "Terminal websocket client bytes session_id=%s length=%s count=%s",
                            session_id,
                            len(message["bytes"]),
                            client_message_count,
                        )
                        await upstream.send(message["bytes"])
                    elif message.get("text") is not None:
                        client_message_count += 1
                        logger.debug(
                            "Terminal websocket client text session_id=%s length=%s count=%s",
                            session_id,
                            len(message["text"]),
                            client_message_count,
                        )
                        await upstream.send(message["text"])

            async def upstream_to_client() -> None:
                nonlocal upstream_message_count
                try:
                    async for message in upstream:
                        upstream_message_count += 1
                        if isinstance(message, bytes):
                            logger.debug(
                                "Terminal websocket upstream bytes session_id=%s length=%s count=%s",
                                session_id,
                                len(message),
                                upstream_message_count,
                            )
                            await websocket.send_bytes(message)
                        else:
                            logger.debug(
                                "Terminal websocket upstream text session_id=%s length=%s count=%s",
                                session_id,
                                len(message),
                                upstream_message_count,
                            )
                            await websocket.send_text(message)
                except websockets.ConnectionClosed as exc:
                    logger.info(
                        "Terminal websocket upstream disconnected session_id=%s code=%s reason=%s detail=%s client_messages=%s upstream_messages=%s",
                        session_id,
                        upstream.close_code,
                        upstream.close_reason,
                        exc,
                        client_message_count,
                        upstream_message_count,
                    )
                    await websocket.close(code=1000)
                    return
                logger.info(
                    "Terminal websocket upstream closed session_id=%s code=%s reason=%s client_messages=%s upstream_messages=%s",
                    session_id,
                    upstream.close_code,
                    upstream.close_reason,
                    client_message_count,
                    upstream_message_count,
                )
                await websocket.close(code=1000)

            done, pending = await asyncio.wait(
                {asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
            logger.info(
                "Terminal websocket proxy finished session_id=%s client_messages=%s upstream_messages=%s",
                session_id,
                client_message_count,
                upstream_message_count,
            )
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("Terminal websocket proxy failed session_id=%s", session_id)
        if accepted:
            await websocket.close(code=1011)
        else:
            await websocket.close(code=1008)


def _default_web_dir() -> Path:
    return Path(__file__).parent / "static"


def _resolve_web_dir(web_dir: Path | None) -> Path | None:
    static_dir = web_dir or _default_web_dir()
    index_file = static_dir / "index.html"
    if index_file.is_file():
        return static_dir
    return None


def create_app(*, serve_web: bool = True, web_dir: Path | None = None) -> FastAPI:
    settings = load_settings()
    configure_logging(settings)

    app = FastAPI(title="TermBridge")
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(router)

    static_dir = _resolve_web_dir(web_dir) if serve_web else None
    if static_dir is not None:

        @app.get("/{path:path}", include_in_schema=False)
        def serve_web_app(path: str) -> FileResponse:
            if path == "health" or path.startswith("api/"):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

            requested_file = (static_dir / path).resolve()
            if requested_file.is_file() and requested_file.is_relative_to(static_dir.resolve()):
                return FileResponse(requested_file)
            return FileResponse(static_dir / "index.html")

    return app
