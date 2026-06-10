from pathlib import Path


class NoAvailablePortError(RuntimeError):
    pass


class SessionRepositoryError(RuntimeError):
    pass


class SessionNotFoundError(KeyError):
    def __init__(self, session_id: str) -> None:
        super().__init__(session_id)
        self.session_id = session_id


class DuplicateSessionError(ValueError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Duplicate session: {session_id}")
        self.session_id = session_id


class UnknownRuntimeError(ValueError):
    def __init__(self, runtime: str) -> None:
        super().__init__(f"Unknown runtime: {runtime}")
        self.runtime = runtime


class InvalidTerminalCommandError(ValueError):
    def __init__(self) -> None:
        super().__init__("Custom terminal command is required")


class WorkspaceNotFoundError(ValueError):
    def __init__(self, workspace: Path) -> None:
        super().__init__(f"Workspace does not exist or is not a directory: {workspace}")
        self.workspace = workspace


class WorkspacePathNotFoundError(ValueError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"Workspace path does not exist: {path}")
        self.path = path


class WorkspacePathNotDirectoryError(ValueError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"Workspace path is not a directory: {path}")
        self.path = path


class WorkspaceBrowserError(RuntimeError):
    pass


class ShortcutRepositoryError(RuntimeError):
    pass


class ShortcutNotFoundError(KeyError):
    def __init__(self, shortcut_id: str) -> None:
        super().__init__(shortcut_id)
        self.shortcut_id = shortcut_id


class InvalidTerminalConfigError(ValueError):
    pass
