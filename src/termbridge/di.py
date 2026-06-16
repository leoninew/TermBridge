from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from termbridge.ports import PortAllocator
from termbridge.process import ProcessAdapter, TtydProcessAdapter
from termbridge.repositories import FileSessionRepository, FileShortcutRepository, FileTerminalRepository
from termbridge.runtime import RuntimeRegistry
from termbridge.services import SessionService, TerminalService, WorkspaceBrowserService
from termbridge.settings import Settings, load_settings

SettingsDep = Annotated[Settings, Depends(load_settings)]


def get_process_adapter(settings: SettingsDep) -> ProcessAdapter:
    return TtydProcessAdapter(settings)


@lru_cache
def get_runtime_registry() -> RuntimeRegistry:
    return RuntimeRegistry()


def get_session_repository(settings: SettingsDep) -> FileSessionRepository:
    return FileSessionRepository(settings.sessions_file)


def get_terminal_repository(settings: SettingsDep) -> FileTerminalRepository:
    return FileTerminalRepository(settings.terminals_file)


def get_shortcut_repository(settings: SettingsDep) -> FileShortcutRepository:
    return FileShortcutRepository(settings.shortcuts_file)


def get_terminal_service(
    settings: SettingsDep,
    repository: Annotated[FileTerminalRepository, Depends(get_terminal_repository)],
    shortcut_repository: Annotated[FileShortcutRepository, Depends(get_shortcut_repository)],
    session_repository: Annotated[FileSessionRepository, Depends(get_session_repository)],
) -> TerminalService:
    return TerminalService(repository, shortcut_repository, session_repository, settings=settings)


def get_port_allocator(settings: SettingsDep) -> PortAllocator:
    return PortAllocator(settings.host, settings.port_start, settings.port_end)


def get_session_service(
    settings: SettingsDep,
    repository: Annotated[FileSessionRepository, Depends(get_session_repository)],
    runtime_registry: Annotated[RuntimeRegistry, Depends(get_runtime_registry)],
    port_allocator: Annotated[PortAllocator, Depends(get_port_allocator)],
    process_adapter: Annotated[ProcessAdapter, Depends(get_process_adapter)],
    terminal_service: Annotated[TerminalService, Depends(get_terminal_service)],
) -> SessionService:
    return SessionService(settings, repository, runtime_registry, port_allocator, process_adapter, terminal_service)


@lru_cache
def get_workspace_browser_service() -> WorkspaceBrowserService:
    return WorkspaceBrowserService()


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
TerminalServiceDep = Annotated[TerminalService, Depends(get_terminal_service)]
WorkspaceBrowserServiceDep = Annotated[WorkspaceBrowserService, Depends(get_workspace_browser_service)]
