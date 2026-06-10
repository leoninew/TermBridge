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

## Runtime environments

TermBridge models terminal runtimes as readiness-based tmux-backed providers:

| Runtime host | Support | Notes |
| --- | --- | --- |
| Windows/Cygwin | Supported when ready | Uses Windows-native ttyd plus Cygwin bash and tmux. |
| Windows/WSL | Supported when ready | Uses Windows-native ttyd and enters the default WSL environment with `wsl --cd ... sh -lc ...`. |
| Linux | Readiness-based | Available on Linux hosts when shell and tmux checks pass. |

All runtime hosts start as `not_ready`. Use the environment page to check dependencies or save required paths; a successful full check marks that runtime `ready` and persists the result in `terminals.json`. If no runtime is ready, the session page guides you to the environment page instead of offering a unusable create flow.

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

The frontend runs on `127.0.0.1:9007` and proxies `/api` and `/health` to the backend.

## CLI

After installing the Python package, run the server with:

```bash
termbridge --host 127.0.0.1 --port 9008
```

The installed server serves packaged frontend assets when they are available. For API-only development or debugging, run:

```bash
termbridge --host 127.0.0.1 --port 9008 --no-frontend
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
TERMBRIDGE_PORT_START=19001
TERMBRIDGE_PORT_END=19999
TERMBRIDGE_STATE_DIR=.termbridge
TERMBRIDGE_TMUX_COMMAND_TIMEOUT_SECONDS=10
```

The default state directory is `.termbridge/` when running from a source checkout, and `~/.termbridge/` when running from an installed package.

State files include:

- `sessions.json`
- `terminals.json`

Set `TERMBRIDGE_STATE_DIR` to use a project-local or custom state directory. The state directory is created automatically when TermBridge first writes state.

## Build

Build the frontend:

```bash
yarn --cwd frontend build
```

Build the Python package with frontend assets included:

```bash
make wheel
```

`make wheel` builds the frontend, syncs `frontend/dist` to `src/termbridge/static`, and runs `uv build`. `src/termbridge/static` is generated build output and is ignored by git.

## Docker

Build the image:

```bash
docker build -t termbridge:local .
```

For domestic mirrors in China, use:

```bash
docker build -f Dockerfile.cn -t termbridge:local .
```

Run the container:

```bash
docker run --rm -p 9008:9008 termbridge:local
```

The container starts `python -m termbridge.main --host 0.0.0.0 --port 9008` and serves the built frontend from the backend. Runtime tools such as `ttyd`, `tmux`, Cygwin, WSL, or Linux shell environments still need to be available for terminal sessions to work.

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
