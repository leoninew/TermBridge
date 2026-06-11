# Changelog

All notable changes to TermBridge will be documented in this file.

This project currently follows a pre-release changelog format. Versioning and release channels may change before the first stable release.

## [0.1.3] - 2026-06-11

### Added

- Open-source readiness documentation.
- MIT license.
- README sections for architecture, session model, security boundary, runtime providers, configuration, Docker, build, and development checks.
- Contributing and security policy documents.

### Changed

- Default Claude Code and Codex shortcuts now use plain `claude` and `codex` commands instead of permission- or sandbox-bypassing example flags.
- Public-facing documentation examples were generalized to avoid local usernames, machine paths, and private workflow names.

### Security

- Documented that TermBridge is intended for local/trusted environments and does not currently include auth, HTTPS, multi-user isolation, or command sandboxing.
