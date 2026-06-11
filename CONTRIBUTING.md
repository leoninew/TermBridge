# Contributing to TermBridge

Thanks for your interest in TermBridge. This project is currently pre-release, so APIs, storage formats, and UI flows may still change.

## Development setup

Install frontend and backend dependencies:

```bash
make install
```

Start the backend:

```bash
make backend
```

Start the frontend dev server in another terminal:

```bash
make frontend
```

The backend defaults to `127.0.0.1:9008`. The frontend defaults to `127.0.0.1:9007` and proxies API requests to the backend.

## Runtime dependencies

To exercise real terminal sessions, install and configure the runtime tools for the environment you want to test:

- `ttyd`
- `tmux`
- Cygwin bash and tmux on Windows/Cygwin
- WSL and WSL tmux on Windows/WSL
- shell and tmux on Linux

If no runtime provider is ready, the app should show environment onboarding instead of an unusable create flow.

## Checks before opening a pull request

Run backend checks:

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Run frontend checks:

```bash
yarn --cwd frontend lint
yarn --cwd frontend typecheck
yarn --cwd frontend build
```

If your change affects packaging, also run:

```bash
make build
```

## Pull request guidelines

- Keep changes focused and explain the user-facing behavior they affect.
- Update `README.md` or docs when behavior, configuration, or setup changes.
- Add or update tests for backend behavior changes.
- Run the relevant checks and include any failures or skipped checks in the PR description.
- Do not commit local state, generated dependency directories, built artifacts, or real `.env` files.

## Sensitive information

Do not commit secrets, credentials, private keys, machine-specific paths, local state files, or personal access tokens. Before publishing or opening a PR, check for local-only artifacts such as:

- `.env`
- `.termbridge/`
- `.venv/`
- `frontend/node_modules/`
- `frontend/dist/`
- `src/termbridge/static/`
- `dist/`
