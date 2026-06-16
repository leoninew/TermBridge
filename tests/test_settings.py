from pathlib import Path

from termbridge.settings import Settings, default_state_dir


def test_default_state_dir_uses_project_directory_for_source_checkout() -> None:
    assert default_state_dir() == Path(".termbridge")


def test_coarse_grained_settings_defaults() -> None:
    settings = Settings()

    assert settings.api_host == "localhost"
    assert settings.api_port == 9008
    assert settings.serve_web is True
    assert settings.web_dir is None
    assert settings.uvicorn_access_log is False
    assert settings.terminal_proxy_timeout_seconds == 10
    assert settings.process_shutdown_timeout_seconds == 5


def test_coarse_grained_settings_use_environment(monkeypatch) -> None:
    monkeypatch.setenv("TERMBRIDGE_API_HOST", "0.0.0.0")
    monkeypatch.setenv("TERMBRIDGE_API_PORT", "9011")
    monkeypatch.setenv("TERMBRIDGE_SERVE_WEB", "false")
    monkeypatch.setenv("TERMBRIDGE_WEB_DIR", "dist")
    monkeypatch.setenv("TERMBRIDGE_UVICORN_ACCESS_LOG", "true")
    monkeypatch.setenv("TERMBRIDGE_TERMINAL_PROXY_TIMEOUT_SECONDS", "15.5")
    monkeypatch.setenv("TERMBRIDGE_PROCESS_SHUTDOWN_TIMEOUT_SECONDS", "2.5")

    settings = Settings()

    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 9011
    assert settings.serve_web is False
    assert settings.web_dir == Path("dist")
    assert settings.uvicorn_access_log is True
    assert settings.terminal_proxy_timeout_seconds == 15.5
    assert settings.process_shutdown_timeout_seconds == 2.5


def test_empty_web_dir_is_none(monkeypatch) -> None:
    monkeypatch.setenv("TERMBRIDGE_WEB_DIR", "")

    settings = Settings()

    assert settings.web_dir is None


def test_ttyd_security_settings_defaults() -> None:
    settings = Settings()

    assert settings.ttyd_interface == "127.0.0.1"
    assert settings.ttyd_writable is True
    assert settings.ttyd_credential_mode == "basic"
    assert settings.ttyd_credential_username == "termbridge"
    assert settings.ttyd_credential_password == ""


def test_environment_detection_timeout_settings_default_to_twenty_seconds() -> None:
    settings = Settings()

    assert settings.cygwin_detection_timeout_seconds == 10
    assert settings.wsl_detection_timeout_seconds == 20
