import subprocess
import httpx
from infrainit.providers import ProvisionResult


def verify_http(endpoint: str, path: str = "/") -> bool:
    try:
        r = httpx.get(f"{endpoint}{path}", timeout=10)
        return r.is_success
    except Exception:
        return False


def verify_process(name: str) -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-f", name], capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def verify_result(result: ProvisionResult, plan: dict) -> bool:
    verify_cfg = plan.get("verify", {})
    vtype = verify_cfg.get("type", "http")

    if vtype == "http" and result.endpoint:
        path = verify_cfg.get("path", "/")
        return verify_http(result.endpoint, path)

    if vtype == "process":
        name = verify_cfg.get("command", result.name)
        return verify_process(name)

    return False
