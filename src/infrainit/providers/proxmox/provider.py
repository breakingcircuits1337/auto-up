import subprocess
import time
import httpx
from infrainit.providers import Provider, ProvisionResult
from infrainit.config.config import require_env


class ProxmoxProvider(Provider):
    name = "proxmox"

    def __init__(self):
        self.host = require_env("PROXMOX_HOST")
        self.token_id = require_env("PROXMOX_TOKEN_ID")
        self.token_secret = require_env("PROXMOX_TOKEN_SECRET")
        self._http = httpx.Client(
            base_url=f"https://{self.host}:8006/api2/json",
            verify=False,
            headers={"Authorization": f"PVEAPIToken={self.token_id}={self.token_secret}"},
            timeout=60,
        )

    def provision(self, plan: dict) -> ProvisionResult:
        node = plan.get("constraints", {}).get("node", "pve1")
        vm_id = plan.get("constraints", {}).get("vm_id", "auto")
        ram = plan.get("constraints", {}).get("ram_gb", 2) * 1024
        disk = plan.get("constraints", {}).get("disk_gb", 20)
        image = "ubuntu-24.04-standard_24.04-2_amd64.img"

        if vm_id == "auto":
            vm_id = self._next_id()

        self._http.post(
            f"/nodes/{node}/qemu",
            json={
                "vmid": vm_id,
                "name": f"infrainit-{vm_id}",
                "memory": ram,
                "cores": 2,
                "net0": "virtio,bridge=vmbr0",
                "virtio0": f"{'local-lvm'}:{disk}",
                "ostype": "l26",
                "ide2": f"{'local'}:iso/{image},media=cdrom",
                "ciuser": "infrainit",
                "sshkeys": require_env("PROXMOX_SSH_PUBKEY"),
                "agent": 1,
            },
        )

        self._http.post(f"/nodes/{node}/qemu/{vm_id}/status/start")
        self._wait_for_vm(vm_id, node)
        ip = self._get_vm_ip(vm_id, node)

        return ProvisionResult(
            name=f"vm-{vm_id}",
            provider=self.name,
            endpoint=f"http://{ip}:{plan.get('port', 80)}",
            metadata={"vm_id": vm_id, "node": node, "ip": ip},
        )

    def verify(self, result: ProvisionResult) -> bool:
        try:
            r = httpx.get(result.endpoint, timeout=10)
            return r.is_success
        except Exception:
            return False

    def destroy(self, result: ProvisionResult) -> None:
        vm_id = result.metadata["vm_id"]
        node = result.metadata["node"]
        self._http.post(f"/nodes/{node}/qemu/{vm_id}/status/stop")
        time.sleep(3)
        self._http.delete(f"/nodes/{node}/qemu/{vm_id}")

    def _next_id(self) -> int:
        resp = self._http.get("/cluster/nextid")
        return resp.json()["data"]

    def _wait_for_vm(self, vm_id: int, node: str, timeout: int = 120):
        for _ in range(timeout):
            try:
                resp = self._http.get(f"/nodes/{node}/qemu/{vm_id}/status/current")
                status = resp.json()["data"]["status"]
                if status == "running":
                    return
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError("VM did not reach running state")

    def _get_vm_ip(self, vm_id: int, node: str) -> str:
        for _ in range(30):
            try:
                resp = self._http.get(f"/nodes/{node}/qemu/{vm_id}/agent/network-get-interfaces")
                for iface in resp.json()["data"]["result"]:
                    for addr in iface.get("ip-addresses", []):
                        ip = addr.get("ip-address", "")
                        if ip.startswith("192.168.") or ip.startswith("10."):
                            return ip
            except Exception:
                pass
            time.sleep(2)
        raise RuntimeError("Could not determine VM IP")
