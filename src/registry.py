import os
import sys
import threading
from pathlib import Path
import traceback

# Force mapping onto the deployment directory (XDG Standard)
REGISTRY_DIR = Path.home() / ".local" / "share" / "npc-forge"

NPC_REGISTRY = {}
LOAD_LOCK = threading.Lock()

def get_npc_engine(npc_name):
    """Ensures that each NPC Engine is instantiated and baked ONCE on startup."""
    npc_path = REGISTRY_DIR / "npcs" / npc_name
    if not os.path.exists(npc_path):
        return None

    # If the NPC instance does not exist in memory cache, initialize it now.
    # The lock keeps concurrent requests from loading the same NPC twice
    # and from changing the working directory under each other.
    if npc_name not in NPC_REGISTRY:
        with LOAD_LOCK:
            if npc_name not in NPC_REGISTRY:
                return load_npc_engine(npc_name)

    return NPC_REGISTRY[npc_name]

def load_npc_engine(npc_name):
    old_cwd = os.getcwd()
    try:
        os.chdir(str(REGISTRY_DIR))
        
        if str(REGISTRY_DIR) not in sys.path:
            sys.path.insert(0, str(REGISTRY_DIR))

        from FlintNPC import FlintNPC
        
        NPC_REGISTRY[npc_name] = FlintNPC(npc_name)
        os.chdir(old_cwd)

    except Exception as init_error:
        if "old_cwd" in locals(): os.chdir(old_cwd)
        sys.stderr.write(f"NPC-Forge registry failed to initialize NPC '{npc_name}': {str(init_error)}")
        traceback.print_exc()
        return None

    return NPC_REGISTRY[npc_name]
