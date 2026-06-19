import subprocess
import tempfile
from pathlib import Path
from infrainit.providers import Provider, ProvisionResult


class LocalProvider(Provider):
    name = "local"

    def provision(self, plan: dict) -> ProvisionResult:
        port = plan.get("port", 8080)
        run_cmd = plan.get("run_command", "docker compose up -d")
        compose = self._generate_compose(plan)

        project_dir = Path(tempfile.mkdtemp(prefix="infrainit-"))
        compose_file = project_dir / "docker-compose.yml"
        compose_file.write_text(compose)

        subprocess.run(
            run_cmd, shell=True, cwd=str(project_dir), check=True, timeout=300
        )

        return ProvisionResult(
            name=plan.get("repo", "app").split("/")[-1].replace(".git", ""),
            provider=self.name,
            endpoint=f"http://localhost:{port}",
            metadata={"project_dir": str(project_dir)},
        )

    def verify(self, result: ProvisionResult) -> bool:
        try:
            r = subprocess.run(
                ["curl", "-sf", result.endpoint],
                capture_output=True, timeout=10,
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
            Path(project_dir).rmdir()

    def _generate_compose(self, plan: dict) -> str:
        port = plan.get("port", 8080)
        language = plan.get("language", "unknown")
        services = {"app": {"build": ".", "ports": [f"{port}:{port}"]}}

        for dep in plan.get("stack", []):
            dep_lower = dep.lower()
            if "postgres" in dep_lower or "postgresql" in dep_lower:
                services["db"] = {"image": "postgres:16", "environment": {"POSTGRES_PASSWORD": "infrainit"}, "ports": ["5432:5432"]}
            elif "redis" in dep_lower:
                services["redis"] = {"image": "redis:7", "ports": ["6379:6379"]}
            elif "mysql" in dep_lower or "mariadb" in dep_lower:
                services["db"] = {"image": "mariadb:11", "environment": {"MYSQL_ROOT_PASSWORD": "infrainit"}, "ports": ["3306:3306"]}
            elif "mongo" in dep_lower:
                services["mongo"] = {"image": "mongo:7", "ports": ["27017:27017"]}

        import yaml
        return yaml.dump({"version": "3.8", "services": services}, default_flow_style=False)
