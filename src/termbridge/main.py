import argparse

import uvicorn

from termbridge.api import create_app
from termbridge.logging import logging_config
from termbridge.settings import load_settings

app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TermBridge API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9008)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    uvicorn.run(
        "termbridge.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=["src"] if args.reload else None,
        log_config=logging_config(settings.logging_level),
    )


if __name__ == "__main__":
    main()
