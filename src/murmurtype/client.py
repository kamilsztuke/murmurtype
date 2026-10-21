# SPDX-License-Identifier: GPL-3.0-or-later

import socket

from murmurtype.paths import socket_path


class DaemonUnavailable(Exception):
    pass


def request(command: str) -> str:
    """Send one command to the daemon and return its response."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5)
            client.connect(str(socket_path()))
            client.sendall(command.encode("utf-8"))
            return client.recv(4096).decode("utf-8")
    except (FileNotFoundError, ConnectionRefusedError) as error:
        raise DaemonUnavailable(str(error)) from error
