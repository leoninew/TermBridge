from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

SHORTCUT_HOSTS = ("windows_cygwin", "windows_wsl", "linux")


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate shortcuts from terminals.json to shortcuts.json")
    parser.add_argument("--terminals-file", type=Path, default=Path(".termbridge") / "terminals.json")
    parser.add_argument("--shortcuts-file", type=Path, default=Path(".termbridge") / "shortcuts.json")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing shortcuts.json")
    args = parser.parse_args()

    if not args.terminals_file.is_file():
        raise SystemExit(f"terminals.json not found: {args.terminals_file}")
    if args.shortcuts_file.exists() and not args.force:
        raise SystemExit(f"shortcuts.json already exists: {args.shortcuts_file}. Use --force to overwrite.")

    terminals = _read_json_object(args.terminals_file, "terminals.json")
    shortcuts = terminals.get("shortcuts", [])
    if not isinstance(shortcuts, list):
        raise SystemExit("terminals.json shortcuts must be a JSON array")

    state: dict[str, dict[str, dict[str, str | None]]] = {host: {} for host in SHORTCUT_HOSTS}
    for index, shortcut in enumerate(shortcuts, start=1):
        if not isinstance(shortcut, dict):
            raise SystemExit(f"shortcut #{index} must be a JSON object")
        host = shortcut.get("host")
        name = shortcut.get("name")
        command = shortcut.get("command")
        if host not in SHORTCUT_HOSTS:
            raise SystemExit(f"shortcut #{index} has unsupported host: {host}")
        if not isinstance(name, str) or not name.strip():
            raise SystemExit(f"shortcut #{index} has empty name")
        if not isinstance(command, str) or not command.strip():
            raise SystemExit(f"shortcut #{index} has empty command")
        name = name.strip()
        if name in state[host]:
            raise SystemExit(f"duplicate shortcut name in {host}: {name}")
        shortcut_id = shortcut.get("id")
        if not isinstance(shortcut_id, str) or not shortcut_id.strip():
            shortcut_id = f"shortcut_{uuid4().hex}"
        description = shortcut.get("description")
        if description is not None and not isinstance(description, str):
            raise SystemExit(f"shortcut #{index} description must be a string or null")
        state[host][name] = {
            "id": shortcut_id.strip(),
            "command": command.strip(),
            "description": description,
        }

    args.shortcuts_file.parent.mkdir(parents=True, exist_ok=True)
    args.shortcuts_file.write_text(
        json.dumps({"shortcuts": state}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Migrated {len(shortcuts)} shortcuts to {args.shortcuts_file}")
    return 0


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} contains invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemExit(f"{label} must be a JSON object")
    return raw


if __name__ == "__main__":
    raise SystemExit(main())
