import shutil
import subprocess
from pathlib import Path
import yaml
from infrainit.providers import Provider, ProvisionResult


class LocalProvider(Provider):
    name = "local"

    def provision(self, plan: dict) -> ProvisionResult:
        port = plan.get("port", 8080)
        clone_path = plan.get("clone_path")
        if not clone_path or not Path(clone_path).exists():
            raise RuntimeError("Local provider requires a clone_path in the plan")

        compose = self._generate_compose(plan)
        compose_file = Path(clone_path) / "docker-compose.yml"
        compose_file.write_text(compose)

        run_cmd = plan.get("run_command", "docker compose up -d")
        subprocess.run(
            run_cmd, shell=True, cwd=clone_path, check=True, timeout=300,
        )

        return ProvisionResult(
            name=plan.get("repo", "app").split("/")[-1].replace(".git", ""),
            provider=self.name,
            endpoint=f"http://localhost:{port}",
            metadata={"project_dir": clone_path},
        )

    def verify(self, result: ProvisionResult) -> bool:
        ep = result.endpoint
        if not ep:
            return False
        try:
            r = subprocess.run(
                ["curl", "-sf", ep], capture_output=True, timeout=10,
            )
            return r.returncode == 0
        except Exception:
            return False

    def destroy(self, result: ProvisionResult) -> None:
        project_dir = result.metadata.get("project_dir")
        if project_dir:
            subprocess.run(
                ["docker", "compose", "down", "-v"],
                cwd=project_dir, capture_output=True, timeout=60,
            )
            shutil.rmtree(project_dir, ignore_errors=True)

    def _generate_compose(self, plan: dict) -> str:
        port = plan.get("port", 8080)
        services = {"app": {"build": ".", "ports": [f"{port}:{port}"]}}

        for dep in plan.get("stack", []):
            dep_lower = dep.lower()
            if "postgres" in dep_lower or "postgresql" in dep_lower:
                services["db"] = {"image": "postgres:16", "environment": {"POSTGRES_PASSWORD": "infrainit"}, "ports": ["5432:5432"]}  # type: ignore[dict-item]
            elif "redis" in dep_lower:
                services["redis"] = {"image": "redis:7", "ports": ["6379:6379"]}
            elif "mysql" in dep_lower or "mariadb" in dep_lower:
                services["db"] = {"image": "mariadb:11", "environment": {"MYSQL_ROOT_PASSWORD": "infrainit"}, "ports": ["3306:3306"]}  # type: ignore[dict-item]
            elif "mongo" in dep_lower:
                services["mongo"] = {"image": "mongo:7", "ports": ["27017:27017"]}

        return yaml.dump({"version": "3.8", "services": services}, default_flow_style=False)
