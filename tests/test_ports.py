import pytest

from termbridge.exceptions import NoAvailablePortError
from termbridge.ports import PortAllocator


def test_allocator_skips_used_port() -> None:
    allocator = PortAllocator("127.0.0.1", 9101, 9102)

    assert allocator.allocate([9101]) == 9102


def test_allocator_skips_bound_port(monkeypatch: pytest.MonkeyPatch) -> None:
    allocator = PortAllocator("127.0.0.1", 9101, 9102)

    def is_available(port: int) -> bool:
        return port == 9102

    monkeypatch.setattr(allocator, "_is_available", is_available)

    assert allocator.allocate([]) == 9102


def test_allocator_raises_when_no_port_available() -> None:
    allocator = PortAllocator("127.0.0.1", 9103, 9103)

    with pytest.raises(NoAvailablePortError):
        allocator.allocate([9103])
