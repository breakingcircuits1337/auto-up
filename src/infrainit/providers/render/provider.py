import httpx
from infrainit.providers import Provider, ProvisionResult
from infrainit.config.config import require_env


class RenderProvider(Provider):
    name = "render"

    def __init__(self):
        self.api_key = require_env("RENDER_API_KEY")
        self._http = httpx.Client(
            base_url="https://api.render.com/v1",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )

    def provision(self, plan: dict) -> ProvisionResult:
        repo = plan.get("repo", "")
        port = plan.get("port", 80)
        name = repo.split("/")[-1].replace(".git", "")
        region = plan.get("constraints", {}).get("region", "oregon")
        language = plan.get("language", "python")

        runtime = self._runtime(language)
        body = {
            "type": "web_service",
            "name": name,
            "repo": repo,
            "plan": "free",
            "region": region,
            "runtime": runtime,
            "buildFilter": {"paths": [], "ignorePaths": []},
            "serviceDetails": {
                "env": runtime,
                "buildCommand": plan.get("build_steps", [None])[0] if plan.get("build_steps") else "",
                "startCommand": plan.get("run_command", ""),
                "healthCheckPath": plan.get("verify", {}).get("path", "/"),
            },
        }

        resp = self._http.post("/services", json=body)
        resp.raise_for_status()
        data = resp.json()

        service_id = data.get("id", data.get("service", {}).get("id", "unknown"))
        service_url = data.get("service", {}).get("serviceDetails", {}).get("url", f"https://{name}.onrender.com")

        return ProvisionResult(
            name=name,
            provider=self.name,
            endpoint=service_url,
            metadata={"service_id": service_id},
        )

    def verify(self, result: ProvisionResult) -> bool:
        try:
            r = httpx.get(result.endpoint, timeout=30)
            return r.is_success
        except Exception:
            return False

    def destroy(self, result: ProvisionResult) -> None:
        sid = result.metadata.get("service_id")
        if sid and sid != "unknown":
            self._http.delete(f"/services/{sid}")

    @staticmethod
    def _runtime(language: str) -> str:
        mapping = {
            "python": "python",
            "node": "node",
            "go": "go",
            "rust": "rust",
            "ruby": "ruby",
            "java": "java",
            "php": "php",
            "elixir": "elixir",
        }
        return mapping.get(language.lower(), "python")
