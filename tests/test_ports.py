import socket

import pytest

from termbridge.exceptions import NoAvailablePortError
from termbridge.ports import PortAllocator


def test_allocator_skips_used_port() -> None:
    allocator = PortAllocator("127.0.0.1", 9101, 9102)

    assert allocator.allocate([9101]) == 9102


def test_allocator_skips_bound_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as bound_sock:
        bound_sock.bind(("127.0.0.1", 0))
        bound_port = bound_sock.getsockname()[1]

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as free_sock:
            free_sock.bind(("127.0.0.1", 0))
            free_port = free_sock.getsockname()[1]

        allocator = PortAllocator("127.0.0.1", min(bound_port, free_port), max(bound_port, free_port))

        assert allocator.allocate([]) == free_port


def test_allocator_raises_when_no_port_available() -> None:
    allocator = PortAllocator("127.0.0.1", 9103, 9103)

    with pytest.raises(NoAvailablePortError):
        allocator.allocate([9103])
