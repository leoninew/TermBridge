# TermBridge

[中文文档](README.zh-CN.md)

TermBridge is a local browser workspace for managing `tmux`-backed terminal sessions through `ttyd`.

It is built for developers who keep many local shells, agent CLIs, and project workspaces open at the same time. TermBridge lets you create reusable shortcuts, launch them inside a workspace directory, attach to the terminal from a browser, and return to running work through `tmux` instead of hunting through terminal windows.

> [!IMPORTANT]
> TermBridge does **not yet** include user authentication, authorization, HTTPS, multi-user isolation, or hosted deployment hardening. Managed `ttyd` sessions bind to `127.0.0.1` and use local Basic Authentication by default, but this is local hardening rather than a deployment security boundary. If you access TermBridge through a public network, mobile client, tunnel, or reverse proxy, add appropriate access control, TLS, and isolation outside TermBridge. Do not expose an unprotected instance.

## Why TermBridge?

- Manage local terminal workspaces from a browser UI
- Keep terminal state through `tmux` across refreshes and reconnects
- Attach browser terminals through `ttyd`
- Launch reusable shortcuts such as `bash`, `claude`, `codex`, or custom commands
- Use readiness-based runtime providers for Windows/Cygwin, Windows/WSL, and Linux
- Store state locally in JSON files; no database server required

## Architecture

![TermBridge architecture overview](docs/assets/termbridge-architecture-overview.png)

TermBridge groups sessions by runtime environment and workspace path. Internally, each workspace maps to a `tmux` session, and each session entry maps to a managed `tmux` window.

## Supported environments

| Runtime host | Status | Notes |
| --- | --- | --- |
| Windows/Cygwin | Supported when ready | Uses Windows-native `ttyd`, Cygwin bash, and Cygwin `tmux`. |
| Windows/WSL | Supported when ready | Uses Windows-native `ttyd` and enters the default WSL environment with `wsl`. |
| Linux | Not ready yet | Linux host support is still being prepared. |

All runtime hosts start as `not_ready`. Use the environment page to check dependencies or save required paths. If no runtime is ready, TermBridge guides you to environment setup instead of showing an unusable create flow.

## Requirements

Development:

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js and Yarn
- Make

Runtime:

- [`ttyd`](https://github.com/tsl0922/ttyd)
- [`tmux`](https://github.com/tmux/tmux/wiki)
- Cygwin, WSL, or a Linux shell environment

## Quick start from source

Install dependencies:

```bash
make install
```

Start both development servers:

```bash
make run
```

To run them separately, start the fastapi API:

```bash
make dev-backend
```

Then start the web dev server in another terminal:

```bash
make dev-frontend
```

The fastapi runs on `127.0.0.1:9008` by default. The web runs on `127.0.0.1:9007` and proxies `/api` and `/health` to the fastapi.

Open the web in your browser, go to the environment page, and run the checks for the runtime provider you want to use.

## Installed usage

After installing the Python package, run the server with:

```bash
termbridge --host 127.0.0.1 --port 9008
```


## Configuration

TermBridge reads settings from environment variables with the `TERMBRIDGE_` prefix and from `.env`.

See [.env.sample](.env.sample) for the available settings and a local development example.

## Shortcuts

Shortcuts are reusable command entrypoints. Documented examples use plain commands such as `bash`, `claude`, and `codex`.

Review and edit shortcut commands before use. A shortcut command is executed on your local machine inside the selected runtime provider, so treat shortcut configuration as trusted local code execution.

## Docker

Build and run locally:

```bash
docker build -t termbridge:local .
docker run --rm -p 9008:9008 termbridge:local
```


The container serves the built web from the fastapi. Runtime tools such as `ttyd`, `tmux`, Cygwin, WSL, or Linux shell environments still need to be available and correctly configured for terminal sessions to work.

Do not publish this container on an untrusted network without adding authentication, HTTPS, and isolation appropriate for your deployment.

## Development

For checks, packaging commands, pull request guidance, and repository hygiene, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md) for the current security boundary and vulnerability reporting guidance.

## License

TermBridge is released under the [MIT License](LICENSE).
