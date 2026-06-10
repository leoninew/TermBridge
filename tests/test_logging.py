import importlib
import logging
import logging.config
import sys
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from termbridge.api import create_app
from termbridge.logging import LOG_DATE_FORMAT, LOG_FORMAT, logging_config
from termbridge.middleware import RequestLoggingMiddleware
from termbridge.settings import Settings


def test_settings_default_logging_level() -> None:
    settings = Settings()

    assert settings.logging_level == "INFO"


def test_settings_default_session_port_range() -> None:
    settings = Settings()

    assert settings.port_start == 19001
    assert settings.port_end == 19999


def test_settings_default_tmux_command_timeout() -> None:
    settings = Settings()

    assert settings.tmux_command_timeout_seconds == 10


def test_settings_tmux_command_timeout_uses_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERMBRIDGE_TMUX_COMMAND_TIMEOUT_SECONDS", "12.5")

    settings = Settings()

    assert settings.tmux_command_timeout_seconds == 12.5


def test_settings_logging_level_uses_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERMBRIDGE_LOGGING_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.logging_level == "DEBUG"


def test_logging_config_uses_explicit_format_and_root_handler() -> None:
    config = logging_config("DEBUG")

    assert LOG_FORMAT == "%(asctime)s [%(levelname).5s] %(name)s:%(lineno)d %(message)s"
    assert LOG_DATE_FORMAT == "%Y-%m-%d %H:%M:%S"
    assert config["formatters"] == {
        "default": {"format": LOG_FORMAT, "datefmt": LOG_DATE_FORMAT},
    }
    assert config["root"] == {"handlers": ["console"], "level": "DEBUG"}
    assert config["handlers"] == {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    }


def test_create_app_configures_logging_for_uvicorn_cli_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_dict_config(config: dict[str, object]) -> None:
        calls.append(config)

    monkeypatch.setattr(logging.config, "dictConfig", fake_dict_config)

    create_app()

    assert calls
    assert calls[0]["root"] == {"handlers": ["console"], "level": "INFO"}


def test_main_runs_uvicorn_with_project_log_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(logging.config, "dictConfig", lambda _config: None)

    import termbridge.main as main_module

    main_module = importlib.reload(main_module)
    calls = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(sys, "argv", ["termbridge", "--host", "0.0.0.0", "--port", "9010", "--reload"])
    monkeypatch.setattr("termbridge.main.uvicorn.run", fake_run)
    monkeypatch.setattr(main_module, "load_settings", lambda: Settings(logging_level="DEBUG"))

    main_module.main()

    assert calls == [
        (
            ("termbridge.main:app",),
            {
                "host": "0.0.0.0",
                "port": 9010,
                "reload": True,
                "reload_dirs": ["src"],
                "log_config": logging_config("DEBUG"),
            },
        )
    ]


def test_logging_config_takes_over_uvicorn_loggers_and_disables_access() -> None:
    config = logging_config("DEBUG")

    assert config["loggers"]["termbridge"]["level"] == "DEBUG"
    assert config["loggers"]["uvicorn"] == {
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    }
    assert config["loggers"]["uvicorn.error"] == {
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    }
    assert config["loggers"]["uvicorn.access"] == {
        "handlers": [],
        "level": "CRITICAL",
        "propagate": False,
    }


@pytest.fixture
def middleware_logger_for_caplog() -> Iterator[None]:
    loggers = [logging.getLogger("termbridge"), logging.getLogger("termbridge.middleware")]
    original = [(logger, logger.handlers[:], logger.propagate) for logger in loggers]
    for logger in loggers:
        logger.handlers = []
        logger.propagate = True
    try:
        yield
    finally:
        for logger, handlers, propagate in original:
            logger.handlers = handlers
            logger.propagate = propagate


def make_logging_test_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ok")
    def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/echo")
    def echo(payload: dict[str, str]) -> dict[str, dict[str, str]]:
        return {"received": payload}

    @app.get("/missing")
    def missing() -> None:
        raise HTTPException(status_code=404, detail="missing")

    @app.get("/broken")
    def broken() -> None:
        raise RuntimeError("broken")

    return TestClient(app)


def test_request_logging_includes_query_string_and_duration(
    caplog: pytest.LogCaptureFixture, middleware_logger_for_caplog: None
) -> None:
    client = make_logging_test_client()

    with caplog.at_level(logging.INFO, logger="termbridge.middleware"):
        response = client.get("/ok", params={"q": "hello"})

    assert response.status_code == 200
    assert any(
        record.levelno == logging.INFO
        and "Request begin" in record.message
        and "method=GET" in record.message
        and "path=/ok?q=hello" in record.message
        for record in caplog.records
    )
    assert any(
        record.levelno == logging.INFO
        and "Request end" in record.message
        and "method=GET" in record.message
        and "path=/ok?q=hello" in record.message
        and "status=200" in record.message
        and "duration_ms=" in record.message
        for record in caplog.records
    )


def test_request_logging_includes_json_request_and_response_bodies(
    caplog: pytest.LogCaptureFixture, middleware_logger_for_caplog: None
) -> None:
    client = make_logging_test_client()

    with caplog.at_level(logging.INFO, logger="termbridge.middleware"):
        response = client.post("/echo", json={"name": "demo"})

    assert response.status_code == 200
    assert response.json() == {"received": {"name": "demo"}}
    assert any(
        record.levelno == logging.INFO and 'Request body={"name":"demo"}' in record.message
        for record in caplog.records
    )
    assert any(
        record.levelno == logging.INFO and 'Response body={"received":{"name":"demo"}}' in record.message
        for record in caplog.records
    )


def test_request_logging_uses_warning_for_4xx(
    caplog: pytest.LogCaptureFixture, middleware_logger_for_caplog: None
) -> None:
    client = make_logging_test_client()

    with caplog.at_level(logging.WARNING, logger="termbridge.middleware"):
        response = client.get("/missing")

    assert response.status_code == 404
    assert any(record.levelno == logging.WARNING and "status=404" in record.message for record in caplog.records)


def test_request_logging_uses_error_for_unhandled_exception(
    caplog: pytest.LogCaptureFixture, middleware_logger_for_caplog: None
) -> None:
    client = make_logging_test_client()

    with caplog.at_level(logging.ERROR, logger="termbridge.middleware"):
        with pytest.raises(RuntimeError, match="broken"):
            client.get("/broken")

    assert any(
        record.levelno == logging.ERROR
        and "Request failed" in record.message
        and "path=/broken" in record.message
        and record.exc_info is not None
        for record in caplog.records
    )
