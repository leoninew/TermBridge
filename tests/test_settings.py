from pathlib import Path

from termbridge.settings import default_state_dir


def test_default_state_dir_uses_project_directory_for_source_checkout() -> None:
    assert default_state_dir() == Path(".termbridge")
