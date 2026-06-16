import argparse
from pathlib import Path
from typing import Any

import uvicorn

from termbridge.api import create_app
from termbridge.logging import logging_config
from termbridge.settings import load_settings

app = create_app(load_settings())


def main() -> None:
    settings = load_settings()

    parser = argparse.ArgumentParser(description="Run the TermBridge server")
    parser.add_argument("--host", default=settings.api_host)
    parser.add_argument("--port", type=int, default=settings.api_port)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--web-dir", type=Path)
    parser.add_argument("--no-web", action="store_true")
    args = parser.parse_args()

    server_app: Any = "termbridge.main:app"
    if args.web_dir is not None or args.no_web:
        server_app = create_app(settings, serve_web=not args.no_web, web_dir=args.web_dir)

    uvicorn.run(
        server_app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=["src"] if args.reload else None,
        log_config=logging_config(settings),
    )


if __name__ == "__main__":
    main()
