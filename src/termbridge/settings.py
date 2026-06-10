from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_state_dir() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    if (project_root / "pyproject.toml").is_file():
        return Path(".termbridge")
    return Path.home() / ".termbridge"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TERMBRIDGE_", env_file=".env", extra="ignore")

    ttyd_executable: str = "ttyd"
    host: str = "127.0.0.1"
    port_start: int = 19001
    port_end: int = 19999
    state_dir: Path = Field(default_factory=default_state_dir)
    public_base_url: str | None = None
    logging_level: str = "INFO"
    tmux_command_timeout_seconds: float = 10

    @property
    def sessions_file(self) -> Path:
        return self.state_dir / "sessions.json"

    @property
    def terminals_file(self) -> Path:
        return self.state_dir / "terminals.json"


@lru_cache
def load_settings() -> Settings:
    return Settings()
