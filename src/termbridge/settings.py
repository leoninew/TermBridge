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
    use_wsl: bool = False
    host: str = "127.0.0.1"
    port_start: int = 9001
    port_end: int = 9999
    state_dir: Path = Field(default_factory=default_state_dir)
    public_base_url: str | None = None
    logging_level: str = "INFO"

    @property
    def sessions_file(self) -> Path:
        return self.state_dir / "sessions.json"

    @property
    def terminals_file(self) -> Path:
        return self.state_dir / "terminals.json"


@lru_cache
def load_settings() -> Settings:
    return Settings()
