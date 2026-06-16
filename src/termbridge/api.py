import asyncio
import base64
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import websockets
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from websockets.typing import Origin, Subprotocol

from termbridge.di import SessionServiceDep, SettingsDep, TerminalServiceDep, WorkspaceBrowserServiceDep
from termbridge.exceptions import (
    InvalidTerminalCommandError,
    InvalidTerminalConfigError,
    NoAvailablePortError,
    SessionNotFoundError,
    SessionRepositoryError,
    SessionTerminalUnavailableError,
    SessionWorkspaceNotFoundError,
    ShortcutInUseError,
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
    ReorderSessionsRequest,
    ReorderWorkspacesRequest,
    RuntimeCheckRequest,
    RuntimeCheckResponse,
    SessionResponse,
    SessionTreeResponse,
    ShortcutHost,
    ShortcutListResponse,
    ShortcutResponse,
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
from termbridge.settings import Settings, load_settings
from termbridge.ttyd import normalize_ttyd_client_query

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


@dataclass(frozen=True)
class DomainErrorMapping:
    status_code: int
    code: str
    message: str | Callable[[Exception], str]


DOMAIN_ERROR_MAPPINGS: tuple[tuple[type[Exception], DomainErrorMapping], ...] = (
    (WorkspacePathNotFoundError, DomainErrorMapping(status.HTTP_404_NOT_FOUND, "not_found", str)),
    (WorkspacePathNotDirectoryError, DomainErrorMapping(status.HTTP_400_BAD_REQUEST, "bad_request", str)),
    (WorkspaceNotFoundError, DomainErrorMapping(status.HTTP_400_BAD_REQUEST, "bad_request", str)),
    (WorkspaceBrowserError, DomainErrorMapping(status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", str)),
    (ShortcutInUseError, DomainErrorMapping(status.HTTP_409_CONFLICT, "conflict", str)),
    (ShortcutNotFoundError, DomainErrorMapping(status.HTTP_404_NOT_FOUND, "not_found", "Shortcut not found")),
    (
        SessionWorkspaceNotFoundError,
        DomainErrorMapping(status.HTTP_404_NOT_FOUND, "not_found", "Session workspace not found"),
    ),
    (SessionNotFoundError, DomainErrorMapping(status.HTTP_404_NOT_FOUND, "not_found", "Session not found")),
    (SessionTerminalUnavailableError, DomainErrorMapping(status.HTTP_409_CONFLICT, "conflict", str)),
    (NoAvailablePortError, DomainErrorMapping(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", str)),
    (UnknownRuntimeError, DomainErrorMapping(status.HTTP_400_BAD_REQUEST, "bad_request", str)),
    (InvalidTerminalCommandError, DomainErrorMapping(status.HTTP_400_BAD_REQUEST, "bad_request", str)),
    (InvalidTerminalConfigError, DomainErrorMapping(status.HTTP_400_BAD_REQUEST, "bad_request", str)),
    (ShortcutRepositoryError, DomainErrorMapping(status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", str)),
    (SessionRepositoryError, DomainErrorMapping(status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", str)),
)


def _error_code(status_code: int) -> str:
    return STATUS_ERROR_CODES.get(status_code, "request_failed")


def _error_message(detail: Any, fallback: str) -> str:
    if isinstance(detail, str) and detail:
        return detail
    return fallback


def _error_response(status_code: int, code: str, error: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code, "error": error})


def _domain_error_mapping(exc: Exception) -> DomainErrorMapping | None:
    for error_type, mapping in DOMAIN_ERROR_MAPPINGS:
        if isinstance(exc, error_type):
            return mapping
    return None


def _domain_error_message(exc: Exception, mapping: DomainErrorMapping) -> str:
    if isinstance(mapping.message, str):
        return mapping.message
    return mapping.message(exc)


async def domain_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    mapping = _domain_error_mapping(exc)
    if mapping is None:
        return await unhandled_exception_handler(request, exc)
    return _error_response(mapping.status_code, mapping.code, _domain_error_message(exc, mapping))


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
    return service.list_roots()


@router.get("/api/workspaces/tree", response_model=WorkspaceTreeResponse)
def list_workspace_tree(
    service: WorkspaceBrowserServiceDep,
    path: str = Query(min_length=1),
    show_hidden: bool = False,
) -> WorkspaceTreeResponse:
    return service.list_children(Path(path), show_hidden=show_hidden)


@router.get("/api/shortcuts", response_model=ShortcutListResponse)
def list_shortcuts(service: TerminalServiceDep) -> ShortcutListResponse:
    return service.list_shortcuts()


@router.post("/api/shortcuts", response_model=ShortcutResponse, status_code=status.HTTP_201_CREATED)
def create_shortcut(request: CreateShortcutRequest, service: TerminalServiceDep) -> ShortcutResponse:
    return service.create_shortcut(request)


@router.put("/api/shortcuts/{shortcut_id}", response_model=ShortcutResponse)
def update_shortcut(shortcut_id: str, request: UpdateShortcutRequest, service: TerminalServiceDep) -> ShortcutResponse:
    return service.update_shortcut(shortcut_id, request)


@router.delete("/api/shortcuts/{shortcut_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shortcut(shortcut_id: str, service: TerminalServiceDep) -> Response:
    service.delete_shortcut(shortcut_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/terminal-settings", response_model=TerminalSettings)
def get_terminal_settings(service: TerminalServiceDep) -> TerminalSettings:
    return service.get_settings()


@router.put("/api/terminal-settings", response_model=TerminalSettings)
def update_terminal_settings(request: UpdateTerminalSettingsRequest, service: TerminalServiceDep) -> TerminalSettings:
    return service.update_settings(request)


@router.post("/api/environment/ttyd/check", response_model=RuntimeCheckResponse)
def check_ttyd(request: RuntimeCheckRequest, service: TerminalServiceDep) -> RuntimeCheckResponse:
    return service.check_ttyd(request.path)


@router.get("/api/environments", response_model=EnvironmentListResponse)
def list_environments(service: TerminalServiceDep) -> EnvironmentListResponse:
    return service.list_environments()


@router.get("/api/environment/windows-cygwin/settings", response_model=WindowsCygwinSettings)
def get_windows_cygwin_settings(service: TerminalServiceDep) -> WindowsCygwinSettings:
    return service.get_windows_cygwin_settings()


@router.put("/api/environment/windows-cygwin/settings", response_model=WindowsCygwinSettings)
def update_windows_cygwin_settings(
    request: WindowsCygwinSettings, service: TerminalServiceDep
) -> WindowsCygwinSettings:
    return service.update_windows_cygwin_settings(request)


@router.post("/api/environment/windows-cygwin/check", response_model=WindowsCygwinCheckResponse)
def check_windows_cygwin(request: WindowsCygwinCheckRequest, service: TerminalServiceDep) -> WindowsCygwinCheckResponse:
    return service.check_windows_cygwin(request.bash_path)


@router.get("/api/environment/windows-wsl/settings", response_model=WindowsWslSettings)
def get_windows_wsl_settings(service: TerminalServiceDep) -> WindowsWslSettings:
    return service.get_windows_wsl_settings()


@router.put("/api/environment/windows-wsl/settings", response_model=WindowsWslSettings)
def update_windows_wsl_settings(request: WindowsWslSettings, service: TerminalServiceDep) -> WindowsWslSettings:
    return service.update_windows_wsl_settings(request)


@router.post("/api/environment/windows-wsl/check", response_model=WindowsWslCheckResponse)
def check_windows_wsl(service: TerminalServiceDep) -> WindowsWslCheckResponse:
    return service.check_windows_wsl()


@router.post("/api/environment/linux/check", response_model=LinuxCheckResponse)
def check_linux(service: TerminalServiceDep) -> LinuxCheckResponse:
    return service.check_linux()


@router.post("/api/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(request: CreateSessionRequest, service: SessionServiceDep) -> SessionResponse:
    return service.create(request)


@router.get("/api/sessions", response_model=list[SessionResponse])
def list_sessions(service: SessionServiceDep) -> list[SessionResponse]:
    return service.list_sessions()


@router.get("/api/session-tree", response_model=SessionTreeResponse)
def list_session_tree(service: SessionServiceDep) -> SessionTreeResponse:
    return service.list_tree()


@router.put("/api/session-tree/environments/{host}/workspaces/order", response_model=SessionTreeResponse)
def reorder_session_workspaces(
    host: ShortcutHost, request: ReorderWorkspacesRequest, service: SessionServiceDep
) -> SessionTreeResponse:
    return service.reorder_workspaces(host, request)


@router.put("/api/session-workspaces/{workspace_id}/sessions/order", response_model=SessionTreeResponse)
def reorder_workspace_sessions(
    workspace_id: str, request: ReorderSessionsRequest, service: SessionServiceDep
) -> SessionTreeResponse:
    return service.reorder_sessions(workspace_id, request)


@router.post("/api/sessions/close-all", response_model=CloseAllSessionsResponse)
def close_all_sessions(service: SessionServiceDep) -> CloseAllSessionsResponse:
    return service.close_all()


@router.delete("/api/session-workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session_workspace(workspace_id: str, service: SessionServiceDep) -> Response:
    service.delete_workspace(workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, service: SessionServiceDep) -> SessionResponse:
    return service.get(session_id)


@router.post("/api/sessions/{session_id}/start", response_model=SessionResponse)
def start_session(session_id: str, service: SessionServiceDep) -> SessionResponse:
    return service.start(session_id)


@router.post("/api/sessions/{session_id}/stop", response_model=SessionResponse)
def stop_session(session_id: str, service: SessionServiceDep) -> SessionResponse:
    return service.stop(session_id)


@router.delete("/api/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, service: SessionServiceDep) -> Response:
    service.delete(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/terminal/{session_id}", include_in_schema=False)
def redirect_terminal_root(session_id: str) -> RedirectResponse:
    return RedirectResponse(url=f"/terminal/{session_id}/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/terminal/{session_id}/{path:path}", include_in_schema=False)
async def proxy_terminal_http(
    session_id: str, path: str, request: Request, service: SessionServiceDep, settings: SettingsDep
) -> Response:
    target = service.terminal_proxy_target(session_id)
    target_path = path or ""
    target_url = f"{target.base_url.rstrip('/')}/{target_path}"
    original_query = request.url.query
    normalized_query = normalize_ttyd_client_query(original_query)
    if normalized_query != original_query:
        redirect_url = f"/terminal/{session_id}/{target_path}"
        if normalized_query:
            redirect_url = f"{redirect_url}?{normalized_query}"
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    if normalized_query:
        target_url = f"{target_url}?{normalized_query}"
    headers = _target_headers(target.credential)
    async with httpx.AsyncClient(timeout=settings.terminal_proxy_timeout_seconds, follow_redirects=False) as client:
        try:
            upstream = await client.request(request.method, target_url, headers=headers, content=await request.body())
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="Terminal proxy request failed"
            ) from exc
    return Response(
        content=upstream.content, status_code=upstream.status_code, headers=_proxy_headers(upstream.headers)
    )


@router.websocket("/terminal/{session_id}/ws")
async def proxy_terminal_websocket(session_id: str, websocket: WebSocket, service: SessionServiceDep) -> None:
    try:
        target = service.terminal_proxy_target(session_id)
    except (SessionNotFoundError, InvalidTerminalConfigError):
        await websocket.close(code=1008)
        return
    target_url = target.base_url.replace("http://", "ws://", 1).replace("https://", "wss://", 1).rstrip("/")
    query = normalize_ttyd_client_query(websocket.url.query)
    if query:
        target_url = f"{target_url}/ws?{query}"
    else:
        target_url = f"{target_url}/ws"
    requested_subprotocols = [
        item.strip() for item in websocket.headers.get("sec-websocket-protocol", "").split(",") if item.strip()
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


def create_app(settings: Settings, *, serve_web: bool | None = None, web_dir: Path | None = None) -> FastAPI:
    configure_logging(settings)
    serve_web = settings.serve_web if serve_web is None else serve_web
    web_dir = settings.web_dir if web_dir is None else web_dir

    app = FastAPI(title="TermBridge")
    app.dependency_overrides[load_settings] = lambda: settings
    for error_type, _mapping in DOMAIN_ERROR_MAPPINGS:
        app.add_exception_handler(error_type, domain_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(RequestLoggingMiddleware, settings=settings)
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
