from pathlib import Path

from termbridge.settings import Settings, default_state_dir


def test_default_state_dir_uses_project_directory_for_source_checkout() -> None:
    assert default_state_dir() == Path(".termbridge")


def test_ttyd_security_settings_defaults() -> None:
    settings = Settings()

    assert settings.ttyd_interface == "127.0.0.1"
    assert settings.ttyd_credential_mode == "basic"
    assert settings.ttyd_credential_username == "termbridge"
    assert settings.ttyd_credential_password == ""


def test_environment_detection_timeout_settings_default_to_twenty_seconds() -> None:
    settings = Settings()

    assert settings.cygwin_detection_timeout_seconds == 10
    assert settings.wsl_detection_timeout_seconds == 20
