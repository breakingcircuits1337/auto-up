import json
from httpx import Client as HTTPClient


OLLAMA_ENDPOINT = "http://localhost:11434"


class OllamaFallback:
    def __init__(self, model: str = "codellama"):
        self.model = model
        self._http = HTTPClient(base_url=OLLAMA_ENDPOINT, timeout=120)

    def generate(self, system: str, user: str) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        resp = self._http.post("/api/chat", json=body)
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def generate_plan(self, system: str, user: str) -> dict:
        raw = self.generate(system, user)
        return json.loads(raw)
