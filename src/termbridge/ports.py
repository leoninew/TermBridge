import socket
from collections.abc import Iterable

from termbridge.exceptions import NoAvailablePortError


class PortAllocator:
    def __init__(self, host: str, port_start: int, port_end: int) -> None:
        if port_start > port_end:
            raise ValueError("port_start must be less than or equal to port_end")
        self._host = host
        self._port_start = port_start
        self._port_end = port_end

    def allocate(self, used_ports: Iterable[int]) -> int:
        used = set(used_ports)
        for port in range(self._port_start, self._port_end + 1):
            if port in used:
                continue
            if self._is_available(port):
                return port
        raise NoAvailablePortError("No available port")

    def _is_available(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((self._host, port))
            except OSError:
                return False
        return True
