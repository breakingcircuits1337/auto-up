import json
import subprocess
import httpx
from infrainit.providers import Provider, ProvisionResult
from infrainit.config.config import require_env


class AzureProvider(Provider):
    name = "azure"

    def provision(self, plan: dict) -> ProvisionResult:
        sub = require_env("AZURE_SUBSCRIPTION_ID")
        location = plan.get("constraints", {}).get("location", "eastus")
        vm_size = plan.get("constraints", {}).get("vm_size", "Standard_B1s")
        name = plan.get("repo", "app").split("/")[-1].replace(".git", "").replace("_", "-").lower()
        rg = f"rg-{name}"
        port = plan.get("port", 80)

        self._az(f"group create --name {rg} --location {location} --subscription {sub}")
        self._az(
            f"vm create --resource-group {rg} --name {name} "
            f"--image Ubuntu2404 --size {vm_size} "
            f"--admin-username infrainit --generate-ssh-keys "
            f"--nsg-rule SSH,{self._nsg_rule(port)} "
            f"--subscription {sub}"
        )

        result = self._az(f"vm show --resource-group {rg} --name {name} --show-details --subscription {sub}")
        info = json.loads(result)
        ip = info.get("publicIps", "unknown")

        return ProvisionResult(
            name=name,
            provider=self.name,
            endpoint=f"http://{ip}:{port}",
            metadata={"resource_group": rg, "public_ip": ip, "port": port},
        )

    def verify(self, result: ProvisionResult) -> bool:
        ep = result.endpoint
        if not ep:
            return False
        try:
            r = httpx.get(ep, timeout=10)
            return r.is_success
        except Exception:
            return False

    def destroy(self, result: ProvisionResult) -> None:
        self._az(f"group delete --name {result.metadata['resource_group']} --yes --no-wait")

    def _az(self, cmd: str) -> str:
        result = subprocess.run(
            f"az {cmd}", shell=True, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Azure CLI error: {result.stderr}")
        return result.stdout

    @staticmethod
    def _nsg_rule(port: int) -> str:
        return "80" if port == 80 else f"{port}"
