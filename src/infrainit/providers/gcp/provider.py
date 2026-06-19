import subprocess
import json
import time
from infrainit.providers import Provider, ProvisionResult
from infrainit.config.config import require_env


class GCPProvider(Provider):
    name = "gcp"

    def provision(self, plan: dict) -> ProvisionResult:
        project = require_env("GCP_PROJECT_ID")
        region = plan.get("constraints", {}).get("region", "us-central1")
        machine = plan.get("constraints", {}).get("machine_type", "e2-micro")
        port = plan.get("port", 80)
        name = plan.get("repo", "app").split("/")[-1].replace(".git", "").replace("_", "-").lower()
        zone = f"{region}-a"

        self._gcloud(f"config set project {project}")
        self._gcloud(
            f"compute instances create {name} "
            f"--zone={zone} --machine-type={machine} "
            f"--image-family=ubuntu-2404-lts --image-project=ubuntu-os-cloud "
            f"--tags=http-server,https-server"
        )

        self._gcloud(
            f"compute firewall-rules create allow-{name} "
            f"--allow=tcp:{port} --target-tags=http-server"
        )

        time.sleep(10)
        result = self._gcloud(
            f"compute instances describe {name} --zone={zone} --format=json"
        )
        info = json.loads(result)
        ip = info["networkInterfaces"][0]["accessConfigs"][0]["natIP"]

        return ProvisionResult(
            name=name,
            provider=self.name,
            endpoint=f"http://{ip}:{port}",
            metadata={"instance_name": name, "zone": zone, "public_ip": ip},
        )

    def verify(self, result: ProvisionResult) -> bool:
        try:
            import httpx
            r = httpx.get(result.endpoint, timeout=10)
            return r.is_success
        except Exception:
            return False

    def destroy(self, result: ProvisionResult) -> None:
        name = result.metadata["instance_name"]
        zone = result.metadata["zone"]
        project = require_env("GCP_PROJECT_ID")
        self._gcloud(f"compute instances delete {name} --zone={zone} --quiet")
        self._gcloud(f"compute firewall-rules delete allow-{name} --quiet")

    def _gcloud(self, cmd: str) -> str:
        result = subprocess.run(
            f"gcloud {cmd}", shell=True, capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gcloud error: {result.stderr}")
        return result.stdout
