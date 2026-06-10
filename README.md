# TermBridge

TermBridge is a browser-based terminal session workspace built on ttyd and tmux.

It helps you manage terminal sessions when too many local terminal windows and tmux sessions become hard to track. Create named sessions, launch reusable shortcuts, open terminals in the browser, and return to running work without hunting through windows.

## What it does

- Manage terminal sessions from a browser UI
- Create sessions from reusable shortcuts
- Attach browser terminals to ttyd-backed sessions
- Restore tmux-backed sessions after refreshing or reopening the app
- Configure and check local runtime dependencies such as ttyd, Cygwin, tmux, Windows, and WSL
- Use one workspace view instead of juggling many terminal windows

## Current scope

TermBridge is currently focused on local and trusted environments.

It does not yet provide authentication, authorization, multi-user isolation, HTTPS setup, or hosted deployment hardening. Do not expose it directly to an untrusted network without adding those controls yourself.

## Architecture

```text
Browser UI
  -> FastAPI session manager
  -> ttyd process per browser terminal
  -> tmux / shell / CLI runtime
```

The backend manages session records, shortcut configuration, environment checks, port allocation, and ttyd process lifecycle. The frontend provides the workspace UI and embeds ttyd terminals.

ttyd remains an external runtime dependency; TermBridge is the management layer around it.

## Requirements

- Python 3.11+
- uv
- Node.js and Yarn
- ttyd
- tmux for tmux-backed persistence
- Cygwin when using Cygwin/tmux shortcuts on Windows

## Development setup

Install dependencies:

```bash
make prepare
```

Start the backend API:

```bash
make backend
```

The backend runs on `127.0.0.1:9008` by default.

Start the frontend dev server:

```bash
make frontend
```

The frontend runs on `0.0.0.0:9007` and proxies `/api` and `/health` to the backend.

## CLI

After installing the Python package, run the API server with:

```bash
termbridge --host 127.0.0.1 --port 9008
```

During development, you can also run:

```bash
uv run python -m termbridge.main --host 127.0.0.1 --port 9008 --reload
```

## Configuration

TermBridge reads settings from environment variables with the `TERMBRIDGE_` prefix and from `.env`.

Examples:

```bash
TERMBRIDGE_LOGGING_LEVEL=DEBUG
TERMBRIDGE_PORT_START=9001
TERMBRIDGE_PORT_END=9999
TERMBRIDGE_STATE_DIR=.termbridge
```

The default state directory is `.termbridge/`.

State files include:

- `.termbridge/sessions.json`
- `.termbridge/terminals.json`

If you used an earlier internal build that wrote `.cc-ttyd/`, copy the files manually to `.termbridge/` before starting TermBridge.

## Build

Build the frontend:

```bash
yarn --cwd frontend build
```

Build the Python package:

```bash
uv build
```

## Verification

Backend checks:

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Frontend checks:

```bash
yarn --cwd frontend lint
yarn --cwd frontend typecheck
yarn --cwd frontend build
```

## Project status

TermBridge is pre-release software being prepared for open source. APIs, storage format, and configuration names may still change before the first stable release.
