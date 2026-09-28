
import json
import re
import os
import urllib.request

from pathlib import Path
from typing import Optional
from providers.base import BaseProvider 

class OllamaProvider(BaseProvider):

    def __init__(self, config: object):
        """Initializes a new independent instance of the LLMConnector."""
        
        self.api_url = config.get("api_url", "127.0.0.1:5000").rstrip("/")
        self.model = config.get("model", "")
        
    def request(self, prompt: str) -> str:
        """Sends HTTP POST request to NPC-Forge API /api/chat endpoint."""
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.7, "repeat_penalty": 1.2}
        }

        binary_data = json.dumps(data).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(binary_data))
        }
        
        req = urllib.request.Request(
            self.api_url, data=binary_data, headers=headers, method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data.get("message", {}).get("content", "")
        except Exception as e:
            print(f"NPC-Forge OllamaClient error: {e}")
            return False

    def craft_intent(
        self, 
        user_query: str, 
        dataset_dir: str, 
        dataset_file: str = "dataset_generated_by_user.json"
    ) -> Optional[dict]:
        """
        Framework-agnostic tool: Asks the LLM for a script, detects the language, 
        formats it into a safe NDF container, and appends it to the target dataset.
        """
        # 1. Prompt Engineering 
        prompt = (
            f"Provide a complete, reusable script or code block for the following request: '{user_query}'\n\n"
            "YOUR RESPONSE MUST FOLLOW THIS EXACT LAYOUT:\n"
            "Provide a short, precise text description explaining the logic.\n"
            "Put the complete functional code inside a standard Markdown code fence explicitly stating the language "
            "(e.g., ```python, ```bash, ```go, ```javascript).\n\n"
            "CONSTRAINTS:\n"
            "- Do not output any JSON markdown formatting."
        )
        
        raw_response = self.request(prompt)
        if not raw_response: return None

        # 2. Parse Response and Detect Code Fence Language Type
        # Captures the language tag name into group(1) and the raw source code content into group(2)
        codefence_pattern = re.compile(r'```(\w+)?\s*(.*?)\s*```', re.DOTALL | re.IGNORECASE)
        match = codefence_pattern.search(raw_response)
        if not match:
            return None
            
        detected_lang = (match.group(1) or "txt").lower().strip()
        extracted_code = match.group(2).strip()
        explanation_clean = codefence_pattern.sub("", raw_response).strip()
        explanation_clean = re.sub(r'\n{3,}', '\n\n', explanation_clean)
        
        # Standard fallback tags for native system fields
        static_explanation = "Generated code ready to be executed."
        static_goal = "Automated execution framework block."

        # 3. Dynamic Shell Command Orchestration
        shell_languages = {"bash", "sh", "zsh", "shell", "command"}
        
        if detected_lang in shell_languages:
            # If it is a native shell command, execute it directly without any cat wrapper
            command_shell = extracted_code
        else:
            # Map common tag identifiers to valid shell filename extension paths
            extension_map = {
                "python": "py", "javascript": "js", "typescript": "ts", 
                "golang": "go", "ruby": "rb", "markdown": "md"
            }
            file_ext = extension_map.get(detected_lang, detected_lang)
            
            # Safe raw string builder block to eliminate runtime backslash SyntaxWarnings completely        
            command_shell = (
                f"TMP_FILE=$(mktemp /tmp/termy_script_XXXXXX.{file_ext}) &&\n"
                "cat << 'EOF' > \"$TMP_FILE\"\n\n"
                f"{extracted_code}\n\n"
                "EOF\n"
                "termy_set_context 'active_file' \"$TMP_FILE\" &&\n"
                "termy_set_context 'active_content' \"$(cat \"$TMP_FILE\")\""
            )
        
        
        # 4. Build NDF Payload Object Structure
        ndf_object = {
            "category": "user_generated", 
            "input": [user_query],
            "output": f"<||completion||>\n\n{explanation_clean if explanation_clean else static_explanation}",
            "tools": [
                {
                    "name": "run_in_terminal",
                    "arguments": {
                        "command": command_shell,
                        "explanation": static_explanation,
                        "goal": static_goal, 
                        "mode": "sync"
                    }
                }
            ],
            "permission": "ask"
        }
        
        # 5. Append Record securely to Disk
        dataset_path = Path(dataset_dir) / dataset_file
        os.makedirs(dataset_path.parent, exist_ok=True)
        
        existing_data = []
        if dataset_path.exists():
            try:
                with open(dataset_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
            except Exception:
                existing_data = []
                
        existing_data.append(ndf_object)
        with open(dataset_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
            
        return ndf_object

