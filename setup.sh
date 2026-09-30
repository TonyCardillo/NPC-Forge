#!/bin/bash

# NPC-Forge User-Space Installer
# Usage:
#   ./install.sh            production copy
#   ./install.sh --dev      symlink sources (edit-in-place)
#   ./install.sh --uninstall

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Standard XDG Directory 

FORGE_DIR="$HOME/.local/share/npc-forge"
BIN_DIR="$HOME/.local/bin"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# uninstall if requested
if [ "${1:-}" == "--uninstall" ]; then
    echo -e "${RED}🧹 Removing NPC-Forge Framework...${NC}"

    # Stops the on-demand server if it is running
    pkill -f "server.py --unix $FORGE_DIR/run/server.sock" 2>/dev/null || true

    # Removes npc-forge binary
    rm -f "$BIN_DIR/npc-forge"
    
    # Removes the framework directory
    rm -rf "$FORGE_DIR"
    
    hash -r
    echo -e "${GREEN}✅ NPC-Forge completely cleaned up from user space${NC}\n"
    exit 0
fi

echo -e "\n${GREEN}NPC-FORGE User Installation${NC}\n"

if [ "$EUID" -eq 0 ]; then
  echo -e "${RED}⛔ Error: Do NOT run this script as root/sudo.${NC}\n"
  echo -e "${YELLOW}This installer is designed to run in user space${NC}\n"
  exit 1
fi

DEV_MODE=0
if [ "${1:-}" == "--dev" ]; then
    DEV_MODE=1
    echo -e "${YELLOW}🔧 Dev mode — symlinking from $SOURCE_DIR${NC}\n"
fi

echo -e "${GREEN}🙋 Installing for user: $(whoami)${NC}\n"

# Check for Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}⛔ Error: Python 3 is not installed or not in PATH.${NC}\n"
    exit 1
fi

# The engine uses Python 3.10 syntax; macOS ships Python 3.9 in /usr/bin
if ! python3 -c "import sys; sys.exit(sys.version_info < (3, 10))"; then
    echo -e "${RED}⛔ Error: Python 3.10 or newer is required, found $(python3 --version).${NC}\n"
    echo -e "${YELLOW}Install it with: brew install python${NC}\n"
    exit 1
fi

# Check for Python venv module
if ! python3 -c "import venv" &> /dev/null; then
    echo -e "${RED}⛔ Error: Python 'venv' module is not installed.${NC}\n"
    echo -e "${YELLOW}On Ubuntu/Debian, install it by running: sudo apt install python3-venv${NC}\n"
    exit 1
fi

echo -e "${BLUE} Copying sources to $FORGE_DIR...${NC}"
mkdir -p "$FORGE_DIR"
mkdir -p "$BIN_DIR"

# Always start from a clean slate: drop any previously installed sources
# (symlinks or real files/dirs) but never touch generated runtime state.
find "$FORGE_DIR" -mindepth 1 -maxdepth 1 \
    ! -name venv ! -name npc_forge.log ! -name logs ! -name '*.egg-info' \
    -exec rm -rf {} +

if [ "$DEV_MODE" -eq 1 ]; then
    # Symlink each top-level entry of src/ (and npcs/) so the whole subtree
    # (including js/, html/, npcs/*) is live-editable without per-file loops.
    if [ -d "$SOURCE_DIR/src" ]; then
        for entry in "$SOURCE_DIR"/src/*; do
            ln -sfn "$entry" "$FORGE_DIR/$(basename "$entry")"
        done
    else
        for entry in "$SOURCE_DIR"/*.py; do
            [ -f "$entry" ] && ln -sf "$entry" "$FORGE_DIR/$(basename "$entry")"
        done
    fi
    [ -f "$SOURCE_DIR/pyproject.toml" ] && ln -sf "$SOURCE_DIR/pyproject.toml" "$FORGE_DIR/pyproject.toml"
    [ -d "$SOURCE_DIR/npcs" ] && ln -sfn "$SOURCE_DIR/npcs" "$FORGE_DIR/npcs"
    [ -d "$SOURCE_DIR/tests" ] && ln -sfn "$SOURCE_DIR/tests" "$FORGE_DIR/tests"
else
    # Mirror the source tree exactly (adds, updates, AND removes stale files),
    # excluding VCS metadata. Requires rsync; falls back to a plain recursive
    # copy (without stale-file removal) if rsync is unavailable.
    if command -v rsync >/dev/null 2>&1; then
        if [ -d "$SOURCE_DIR/src" ]; then
            rsync -a --delete --exclude='.git' "$SOURCE_DIR/src/" "$FORGE_DIR/"
        else
            rsync -a --delete --exclude='.git' --include='*.py' --exclude='*' "$SOURCE_DIR/" "$FORGE_DIR/"
        fi
        [ -d "$SOURCE_DIR/npcs" ] && rsync -a --delete --exclude='.git' "$SOURCE_DIR/npcs/" "$FORGE_DIR/npcs/"
    else
        echo -e "${YELLOW}⚠ rsync not found, falling back to cp (stale files won't be pruned)${NC}"
        if [ -d "$SOURCE_DIR/src" ]; then
            cp -r "$SOURCE_DIR"/src/. "$FORGE_DIR/"
        else
            cp -r "$SOURCE_DIR"/*.py "$FORGE_DIR/"
        fi
        [ -d "$SOURCE_DIR/npcs" ] && cp -r "$SOURCE_DIR/npcs" "$FORGE_DIR/npcs"
    fi
    [ -d "$SOURCE_DIR/tests" ] && cp -r "$SOURCE_DIR/tests" "$FORGE_DIR/tests"
    [ -f "$SOURCE_DIR/pyproject.toml" ] && cp "$SOURCE_DIR/pyproject.toml" "$FORGE_DIR/"
    [ -f "$SOURCE_DIR/README.md" ] && cp "$SOURCE_DIR/README.md" "$FORGE_DIR/"
fi

echo -e "${BLUE} Configuring virtual environment...${NC}"
if [ ! -d "$FORGE_DIR/venv" ]; then
    python3 -m venv "$FORGE_DIR/venv"
    "$FORGE_DIR/venv/bin/pip" install --upgrade pip -q
fi

cd "$FORGE_DIR"
if [ "$DEV_MODE" -eq 1 ]; then
    # Editable mode installation
    "$FORGE_DIR/venv/bin/pip" install -e . -q
else
    # Standard installation
    "$FORGE_DIR/venv/bin/pip" install . -q
fi

echo -e "${BLUE} Setting up npc-forge terminal command...${NC}"
cat << EOF > "$BIN_DIR/npc-forge"
#!$FORGE_DIR/venv/bin/python3
import sys
sys.path.insert(0, "$FORGE_DIR")
from cli import main
if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x "$BIN_DIR/npc-forge"

# $PATH automatic configuration

echo -e "${BLUE} Verifying environment \$PATH...${NC}"
hash -r

PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
RC_FILE=""
case "$(basename "$SHELL")" in
    zsh) RC_FILE="$HOME/.zshrc" ;;
    bash) RC_FILE="$HOME/.bash_profile" ;;
esac

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    if [ -z "$RC_FILE" ]; then
        echo -e "${YELLOW}⚙ Add $BIN_DIR to your \$PATH (fish: fish_add_path $BIN_DIR)${NC}"
    elif ! grep -qF "$PATH_LINE" "$RC_FILE" 2>/dev/null; then
        echo -e "${YELLOW}⚙ Adding $BIN_DIR to your \$PATH in $RC_FILE...${NC}"
        printf '\n# NPC-Forge user binaries path\n%s\n' "$PATH_LINE" >> "$RC_FILE"
    fi
    echo -e "${YELLOW}Open a new terminal to use the npc-forge command.${NC}"
fi

echo -e "\n${GREEN}✅ npc-forge installed successfully in user space${NC}\n"
echo -e "The server starts on demand when you use an NPC, and stops when idle."
echo -e "To start it now, run: ${YELLOW}npc-forge serve${NC}\n"
