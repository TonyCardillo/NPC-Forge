"""
LLM fallback through LM Studio. Starts the LM Studio server and loads the
model on demand, like pi-local, and lets LM Studio unload the model again
after an idle time (TTL).
"""
import json
import os
import re
import shutil
import subprocess
import urllib.request

DEFAULT_MODEL = "qwen/qwen3.5-9b"
DEFAULT_URL = "http://127.0.0.1:1234"

PROMPT = (
    "Write one shell command for this request: '{query}'\n\n"
    "The command runs on macOS in /bin/bash 3.2 with BSD tools: no GNU-only flags, "
    "no grep -P, no sed -i without ''. Prefer one line. Do not use sudo unless the request needs it.\n"
    "Reply with one short sentence that explains the command, then the command in a ```bash code fence."
)

CODE_FENCE = re.compile(r"```(?:bash|sh|zsh|shell)?\s*\n(.*?)```", re.DOTALL)
THINKING = re.compile(r"<think>.*?</think>", re.DOTALL)

def find_lms():
    path = shutil.which("lms")
    fallback = os.path.expanduser("~/.lmstudio/bin/lms")
    return path or (fallback if os.path.exists(fallback) else None)

def parse_suggestion(text: str):
    """Returns {"command", "explanation"} from a model answer, or None."""
    text = THINKING.sub("", text or "")
    match = CODE_FENCE.search(text)
    if not match or not match.group(1).strip():
        return None
    explanation = " ".join(CODE_FENCE.sub(" ", text).split())
    return {"command": match.group(1).strip(), "explanation": explanation}

class LmStudioProvider:
    def __init__(self, config: dict, run=subprocess.run, lms=None):
        self.model = config.get("model", DEFAULT_MODEL)
        self.url = config.get("api_url", DEFAULT_URL).rstrip("/")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError(f"api_url must be an http(s) URL: {self.url}")
        self.ttl = int(config.get("ttl_seconds", 600))
        self.run = run
        self.lms = lms or find_lms()

    def lms_call(self, *args):
        return self.run([self.lms, *args], capture_output=True, text=True, timeout=180)  # noqa: S603

    def server_up(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/v1/models", timeout=1):  # noqa: S310
                return True
        except OSError:
            return False

    def ensure_ready(self) -> bool:
        """Starts the server and loads the model if needed. False when LM Studio is missing."""
        if not self.lms:
            return False
        if not self.server_up():
            self.lms_call("server", "start")
        if self.model not in self.lms_call("ps").stdout:
            self.lms_call("load", self.model, "--ttl", str(self.ttl), "-y")
        return True

    def request(self, prompt: str):
        """Asks the model through the LM Studio REST API, with thinking turned off for speed."""
        body = json.dumps({
            "model": self.model,
            "input": prompt,
            "reasoning": "off",
            "temperature": 0.2,
        }).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310 (scheme checked in __init__)
            f"{self.url}/api/v1/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as response:  # noqa: S310
                output = json.loads(response.read())["output"]
        except (OSError, ValueError, KeyError):
            return None
        return "".join(part.get("content", "") for part in output if part.get("type") == "message")

    def suggest(self, query: str):
        return parse_suggestion(self.request(PROMPT.format(query=query.replace("'", ""))))
