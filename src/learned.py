"""
Saves answers of the LLM fallback as NDF entries, so TERMy can answer
the same prompt by itself the next time.
"""
import json
from pathlib import Path


def build_entry(query: str, command: str, explanation: str) -> dict:
    return {
        "category": "learned",
        "input": [query.strip().lower()],
        "tools": [{
            "name": "run_in_terminal",
            "arguments": {
                "command": command,
                "explanation": explanation or "Command written by the LLM fallback.",
                "goal": "Learned from the LLM fallback",
                "mode": "sync",
            },
        }],
        "permission": "ask",
    }

def save_entry(path, query: str, command: str, explanation: str) -> dict:
    """Adds the entry, or replaces the entry with the same prompt."""
    path = Path(path).expanduser()
    entries = []
    if path.exists():
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            entries = []
    entry = build_entry(query, command, explanation)
    entries = [e for e in entries if e.get("input") != entry["input"]] + [entry]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    return entry
