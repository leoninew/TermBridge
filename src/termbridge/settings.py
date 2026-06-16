from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_state_dir() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    if (project_root / "pyproject.toml").is_file():
        return Path(".termbridge")
    return Path.home() / ".termbridge"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TERMBRIDGE_", env_file=".env", extra="ignore")

    ttyd_executable: str = "ttyd"
    api_host: str = Field(default="localhost", min_length=1)
    api_port: int = Field(default=9008, ge=1, le=65535)
    host: str = "127.0.0.1"
    port_start: int = 19001
    port_end: int = 19999
    state_dir: Path = Field(default_factory=default_state_dir)
    public_base_url: str | None = None
    serve_web: bool = True
    web_dir: Path | None = None
    logging_level: str = "INFO"
    uvicorn_access_log: bool = False
    body_log_limit: int = Field(default=4096, ge=0)
    terminal_proxy_timeout_seconds: float = Field(default=10, gt=0)
    process_shutdown_timeout_seconds: float = Field(default=5, gt=0)
    tmux_command_timeout_seconds: float = 10
    cygwin_detection_timeout_seconds: float = Field(default=10, gt=0)
    wsl_detection_timeout_seconds: float = Field(default=20, gt=0)
    ttyd_log_mode: Literal["none", "console", "file"] = "none"
    ttyd_interface: str = "127.0.0.1"
    ttyd_writable: bool = True
    ttyd_credential_mode: Literal["basic", "none"] = "basic"
    ttyd_credential_username: str = "termbridge"
    ttyd_credential_password: str = ""

    @field_validator("web_dir", mode="before")
    @classmethod
    def empty_web_dir_is_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def sessions_file(self) -> Path:
        return self.state_dir / "sessions.json"

    @property
    def terminals_file(self) -> Path:
        return self.state_dir / "terminals.json"

    @property
    def shortcuts_file(self) -> Path:
        return self.state_dir / "shortcuts.json"


@lru_cache
def load_settings() -> Settings:
    return Settings()
