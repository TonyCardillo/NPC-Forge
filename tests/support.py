"""
Shared helpers for tests that run the NPC-Forge server with a fake HOME.
"""
import socket
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def make_home(tmp):
    """Creates a fake HOME whose NPC-Forge data folder links to the repo NPCs."""
    forge = Path(tmp) / ".local" / "share" / "npc-forge"
    forge.mkdir(parents=True)
    (forge / "npcs").symlink_to(ROOT / "npcs")
    return forge


def socket_path(forge):
    return forge / "run" / "server.sock"


def is_live(path):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(path))
        return True
    except OSError:
        return False


def wait_for(predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False
