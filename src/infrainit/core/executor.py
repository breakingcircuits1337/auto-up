import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from infrainit.providers import Provider, ProvisionResult
from infrainit.core.verifier import verify_result
from infrainit.config.config import set_app_state


class Executor:
    def __init__(self, provider: Provider):
        self._provider = provider

    def run(self, repo_url: str, plan: dict) -> ProvisionResult:
        with tempfile.TemporaryDirectory() as tmpdir:
            self._clone(repo_url, tmpdir)
            plan["clone_path"] = tmpdir
            self._run_build_steps(plan.get("build_steps", []), tmpdir)
            result = self._provider.provision(plan)

        ok = verify_result(result, plan)
        set_app_state(result.name, {
            "provider": self._provider.name,
            "repo": repo_url,
            "endpoint": result.endpoint,
            "created_at": datetime.now().isoformat(),
        })
        result.metadata["verified"] = ok
        return result

    def _clone(self, repo_url: str, dest: str):
        subprocess.run(
            ["git", "clone", repo_url, dest],
            check=True, capture_output=True, timeout=120,
        )

    def _run_build_steps(self, steps: list[str], cwd: str):
        for step in steps:
            subprocess.run(step, shell=True, cwd=cwd, check=True, timeout=300)
