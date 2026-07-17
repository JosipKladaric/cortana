"""
llm_client.py
Simple client for local LLMs (Ollama / LMStudio) with OpenAI-compatible API.
Now with longer timeout and optional streaming placeholder.
"""

import requests
from typing import List, Dict, Optional

class LLMClient:
    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "llama3.2"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._headers = {"Content-Type": "application/json"}
        self.timeout = 180  # seconds, can be changed

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7,
             max_tokens: int = 2048, stream: bool = False) -> Optional[str]:
        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        try:
            response = requests.post(
                endpoint,
                headers=self._headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            print("Error: LLM request timed out.")
            return None
        except requests.exceptions.ConnectionError:
            print(f"Error: Cannot connect to LLM server at {self.base_url}. Is it running?")
            return None
        except Exception as e:
            print(f"LLM request failed: {e}")
            return None

def detect_running_server() -> Optional[str]:
    candidates = [
        ("http://localhost:11434/v1", "ollama"),
        ("http://localhost:1234/v1", "lmstudio"),
    ]
    for url, name in candidates:
        try:
            r = requests.get(f"{url}/models", timeout=5)
            if r.status_code == 200:
                print(f"Detected {name} at {url}")
                return url
        except:
            continue
    return None