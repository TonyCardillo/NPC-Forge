"""
Starts the NPC-Forge server on demand, on a private Unix socket, so local
clients such as TERMy get a warm engine without an always-on service.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

from providers.unix_socket import UnixSocketProvider

DEFAULT_IDLE_SECONDS = 600


def socket_path() -> Path:
    return Path.home() / ".local" / "share" / "npc-forge" / "run" / "server.sock"


def idle_seconds() -> int:
    return int(os.environ.get("NPC_FORGE_IDLE_SECONDS", DEFAULT_IDLE_SECONDS))


def is_server_live(path) -> bool:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(path))
        return True
    except OSError:
        return False


def prepare_socket_folder(path) -> None:
    """Creates the socket folder, readable only by the current user."""
    folder = Path(path).parent
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)


def start_server(npc_name: str, path=None) -> None:
    """Starts the server in the background, detached, and preloads one NPC."""
    server = find_spec("server").origin
    args = ["--unix", str(path or socket_path()), "--idle-seconds", str(idle_seconds())]
    subprocess.Popen(  # noqa: S603
        [sys.executable, server, *args, "--preload", npc_name],
        cwd=str(Path(server).parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def ask(npc_name: str, query: str, local, start: bool = True) -> dict:
    """Answers with the running server, or locally while starting the server."""
    result = UnixSocketProvider(socket_path()).request(npc_name, query)
    if result is not None:
        return result
    if start:
        start_server(npc_name)
    return local.request(npc_name, query)
