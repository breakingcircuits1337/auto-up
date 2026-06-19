from infrainit.llm.client import AzureFoundryClient
from infrainit.llm.fallback import OllamaFallback
from infrainit.llm.prompts import SYSTEM_PROMPT, user_prompt


class Planner:
    def __init__(self, use_fallback: bool = False):
        self._llm = OllamaFallback() if use_fallback else AzureFoundryClient()

    def plan(self, repo_url: str, target: str, constraints: dict | None = None) -> dict:
        prompt = user_prompt(repo_url, target, constraints)
        return self._llm.generate_plan(SYSTEM_PROMPT, prompt)
