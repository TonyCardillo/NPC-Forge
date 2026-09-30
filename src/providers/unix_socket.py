from __future__ import annotations

import http.client
import json
import socket

from providers.base import BaseProvider


class UnixHTTPConnection(http.client.HTTPConnection):
    """HTTP connection over a Unix domain socket."""

    def __init__(self, socket_path: str, timeout: float):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)

class UnixSocketProvider(BaseProvider):

    def __init__(self, socket_path, timeout: float = 10.0):
        """Initializes a client for the NPC-Forge server on a Unix socket."""
        self.socket_path = str(socket_path)
        self.timeout = timeout

    def request(self, npc_name: str, query: str) -> dict | None:
        """Sends a chat request, or returns None when the server is unreachable."""
        conn = UnixHTTPConnection(self.socket_path, self.timeout)
        try:
            body = json.dumps({"message": query})
            conn.request("POST", f"/api/chat/{npc_name}", body, {"Content-Type": "application/json"})
            response = conn.getresponse()
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, http.client.HTTPException):
            return None
        finally:
            conn.close()
