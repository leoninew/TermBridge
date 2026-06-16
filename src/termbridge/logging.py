import logging.config
from typing import Any

from termbridge.settings import Settings

LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FORMAT = "%(asctime)s [%(levelname).5s] %(name)s:%(lineno)d %(message)s"


def logging_config(settings: Settings) -> dict[str, Any]:
    access_log_config: dict[str, Any]
    if settings.uvicorn_access_log:
        access_log_config = {
            "handlers": ["console"],
            "level": settings.logging_level,
            "propagate": False,
        }
    else:
        access_log_config = {
            "handlers": [],
            "level": "CRITICAL",
            "propagate": False,
        }

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": LOG_FORMAT,
                "datefmt": LOG_DATE_FORMAT,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": settings.logging_level,
        },
        "loggers": {
            "termbridge": {
                "handlers": ["console"],
                "level": settings.logging_level,
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": settings.logging_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": settings.logging_level,
                "propagate": False,
            },
            "uvicorn.access": access_log_config,
        },
    }


def configure_logging(settings: Settings) -> None:
    logging.config.dictConfig(logging_config(settings))
