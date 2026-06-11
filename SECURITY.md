# Security Policy

## Supported versions

TermBridge is pre-release software. Security fixes are currently made on the active development branch until a stable release policy is published.

## Security boundary

TermBridge is intended for local or otherwise trusted environments.

It currently does **not** provide:

- Authentication
- Authorization
- HTTPS setup
- Multi-user isolation
- Hosted deployment hardening
- Sandbox isolation for commands launched through shortcuts

A TermBridge shortcut is a local command execution entrypoint. Anyone who can access the TermBridge UI or API may be able to start local commands through configured runtime providers. Do not expose TermBridge directly to the public internet or an untrusted network without adding your own access controls, TLS termination, and isolation.

Prefer binding the server to `127.0.0.1` for local use.

## Reporting a vulnerability

If you find a vulnerability, please avoid public disclosure until maintainers have had time to investigate.

Preferred reporting path once the repository is public:

1. Use GitHub Security Advisories if enabled for the repository.
2. If advisories are not enabled, open a minimal issue that says you have a security report to share without including exploit details.

A dedicated public security contact has not been configured yet. Add one before a wider public launch.

## What to include

Please include:

- Affected version or commit
- Operating system and runtime provider, if relevant
- Steps to reproduce
- Impact assessment
- Suggested fix, if known

## Non-goals for vulnerability reports

Please do not use the public project to test destructive behavior, denial of service, credential theft, or access to systems you do not own or have permission to test.
