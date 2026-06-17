from pathlib import Path
from unittest.mock import patch

from termbridge.process import TtydProcessAdapter
from termbridge.settings import Settings


class FakePopen:
    def __init__(self, command: list[str], cwd: Path, stdout: object, stderr: object, env: object) -> None:
        self.command = command
        self.cwd = cwd
        self.stdout = stdout
        self.stderr = stderr
        self.env = env
        self.pid = 4242

    def poll(self) -> int | None:
        return None


def test_ttyd_process_adapter_writes_startup_header_to_log_file(tmp_path: Path) -> None:
    adapter = TtydProcessAdapter(Settings())
    log_file = tmp_path / "logs" / "ttyd" / "sess_123.log"
    command = ["ttyd", "--credential", "termbridge:secret", "bash", "-lc", "tmux attach"]

    with patch("termbridge.process.subprocess.Popen", FakePopen):
        handle = adapter.start(command, tmp_path, log_file=log_file)

    content = log_file.read_text(encoding="utf-8")
    assert handle.pid == 4242
    assert "[TermBridge] Starting ttyd process" in content
    assert "session_id=sess_123" in content
    assert f"cwd={tmp_path}" in content
    assert "command=ttyd --credential termbridge:secret bash -lc 'tmux attach'" in content
    assert "pid=<pending>" in content
    assert "[TermBridge] ttyd pid=4242" in content
    assert "--- ttyd stdout/stderr ---" in content
