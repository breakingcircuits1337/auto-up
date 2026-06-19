import json
from httpx import Client as HTTPClient, HTTPStatusError
from infrainit.config.config import require_env


class AzureFoundryClient:
    def __init__(self):
        self.endpoint = require_env("AZURE_FOUNDRY_ENDPOINT")
        self.api_key = require_env("AZURE_FOUNDRY_API_KEY")
        self.deployment = require_env("AZURE_FOUNDRY_DEPLOYMENT")
        self._http = HTTPClient(
            base_url=self.endpoint.rstrip("/"),
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=120,
        )

    def generate(self, system: str, user: str) -> str:
        body = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 2000,
            "temperature": 0.1,
        }
        resp = self._http.post(
            f"/openai/deployments/{self.deployment}/chat/completions",
            params={"api-version": "2024-10-21"},
            json=body,
        )
        try:
            resp.raise_for_status()
        except HTTPStatusError as e:
            raise RuntimeError(f"GPT-5.5 API error {e.response.status_code}: {e.response.text}") from e
        return resp.json()["choices"][0]["message"]["content"]

    def generate_plan(self, system: str, user: str) -> dict:
        raw = self.generate(system, user)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"GPT-5.5 returned invalid JSON: {e}\nRaw: {raw}") from e
