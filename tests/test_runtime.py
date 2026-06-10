import pytest

from termbridge.exceptions import UnknownRuntimeError
from termbridge.runtime import RuntimeRegistry


def test_runtime_registry_resolves_known_runtime() -> None:
    registry = RuntimeRegistry()

    assert registry.resolve("bash") == ["bash"]
    assert registry.resolve("claude-code") == ["claude"]


def test_runtime_registry_raises_for_unknown_runtime() -> None:
    registry = RuntimeRegistry()

    with pytest.raises(UnknownRuntimeError):
        registry.resolve("unknown")
