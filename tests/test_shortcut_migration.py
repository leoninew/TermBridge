import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_shortcuts_to_shortcuts_json.py"


def test_migrate_shortcuts_generates_shortcuts_json(tmp_path: Path) -> None:
    terminals_file = tmp_path / "terminals.json"
    shortcuts_file = tmp_path / "shortcuts.json"
    terminals_file.write_text(
        json.dumps(
            {
                "shortcuts": [
                    {
                        "id": "cygwin-bash",
                        "name": "bash",
                        "command": "bash",
                        "host": "windows_cygwin",
                        "description": "Start bash",
                    },
                    {
                        "id": "wsl-bash",
                        "name": "bash",
                        "command": "bash",
                        "host": "windows_wsl",
                        "description": None,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--terminals-file",
            str(terminals_file),
            "--shortcuts-file",
            str(shortcuts_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Migrated 2 shortcuts" in result.stdout
    assert json.loads(shortcuts_file.read_text(encoding="utf-8")) == {
        "shortcuts": {
            "windows_cygwin": {
                "bash": {
                    "id": "cygwin-bash",
                    "command": "bash",
                    "description": "Start bash",
                }
            },
            "windows_wsl": {
                "bash": {
                    "id": "wsl-bash",
                    "command": "bash",
                    "description": None,
                }
            },
            "linux": {},
        }
    }


def test_migrate_shortcuts_rejects_duplicate_names_in_same_host(tmp_path: Path) -> None:
    terminals_file = tmp_path / "terminals.json"
    shortcuts_file = tmp_path / "shortcuts.json"
    terminals_file.write_text(
        json.dumps(
            {
                "shortcuts": [
                    {"id": "one", "name": "bash", "command": "bash", "host": "windows_cygwin"},
                    {"id": "two", "name": "bash", "command": "bash -l", "host": "windows_cygwin"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--terminals-file",
            str(terminals_file),
            "--shortcuts-file",
            str(shortcuts_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "duplicate shortcut name" in result.stderr
    assert not shortcuts_file.exists()


def test_migrate_shortcuts_refuses_existing_output_without_force(tmp_path: Path) -> None:
    terminals_file = tmp_path / "terminals.json"
    shortcuts_file = tmp_path / "shortcuts.json"
    terminals_file.write_text(json.dumps({"shortcuts": []}), encoding="utf-8")
    shortcuts_file.write_text(json.dumps({"shortcuts": {}}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--terminals-file",
            str(terminals_file),
            "--shortcuts-file",
            str(shortcuts_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "already exists" in result.stderr
