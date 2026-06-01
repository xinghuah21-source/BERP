import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from deepseek_prompt_builder import parse_deepseek_json


class DeepSeekClient:
    def __init__(self) -> None:
        if not (os.getenv("DEEPSEEK_API_KEY") or "").strip():
            env_path = Path(__file__).resolve().parent / ".env"
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("\"").strip("'")
                    if k and v and k not in os.environ:
                        os.environ[k] = v

        self.api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
        self.api_url = (os.getenv("DEEPSEEK_API_URL") or "https://api.deepseek.com/chat/completions").strip()
        self.model = (os.getenv("DEEPSEEK_MODEL") or "deepseek-chat").strip()
        self.timeout = float((os.getenv("DEEPSEEK_TIMEOUT") or "15").strip())
        self.last_error: Optional[str] = None

    def evaluate(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            self.last_error = "missing_api_key"
            return None

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是资深语文特级教师。输出严格JSON；禁止改写给定分数；禁止编造音频细节。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            if resp.status_code != 200:
                self.last_error = f"http_{resp.status_code}: {resp.text[:300]}"
                return None
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            data = parse_deepseek_json(content)
            self.last_error = None
            return data
        except Exception as e:
            self.last_error = repr(e)
            return None


def validate_used_metrics(deepseek_json: Dict[str, Any], expected: Dict[str, int], tolerance: int = 2) -> bool:
    used = deepseek_json.get("used_metrics")
    if not isinstance(used, dict):
        return False
    for k, v in expected.items():
        try:
            got = int(used.get(k))
        except Exception:
            return False
        if abs(got - int(v)) > tolerance:
            return False
    return True
