import click
from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from infrainit.config.config import get_app_state, remove_app_state
from infrainit.core.planner import Planner
from infrainit.core.executor import Executor
from infrainit.providers import Provider, ProvisionResult
from infrainit.providers.local.provider import LocalProvider
from infrainit.providers.proxmox.provider import ProxmoxProvider
from infrainit.providers.azure.provider import AzureProvider
from infrainit.providers.render.provider import RenderProvider
from infrainit.providers.gcp.provider import GCPProvider

console = Console()
ProviderClass = type[LocalProvider] | type[ProxmoxProvider] | type[AzureProvider] | type[RenderProvider] | type[GCPProvider]
PROVIDERS: dict[str, ProviderClass] = {
    "1": LocalProvider,
    "2": ProxmoxProvider,
    "3": AzureProvider,
    "4": RenderProvider,
    "5": GCPProvider,
}
NAME_TO_PROVIDER: dict[str, ProviderClass] = {
    "local": LocalProvider,
    "proxmox": ProxmoxProvider,
    "azure": AzureProvider,
    "render": RenderProvider,
    "gcp": GCPProvider,
}


def _pick_target() -> tuple[str, Provider]:
    console.print("\n[bold]Select target:[/]")
    console.print("  1) Local PC (Docker)")
    console.print("  2) Proxmox server")
    console.print("  3) Azure")
    console.print("  4) Render.com")
    console.print("  5) Google Cloud")
    choice = Prompt.ask("  Target", choices=list(PROVIDERS.keys()), default="1")
    label = {"1": "local", "2": "proxmox", "3": "azure", "4": "render", "5": "gcp"}[choice]
    provider = PROVIDERS[choice]()
    return label, provider


def _gather_constraints(target: str) -> dict:
    constraints = {}
    if target == "proxmox":
        constraints["node"] = Prompt.ask("  Proxmox node", default="pve1")
        constraints["vm_id"] = Prompt.ask("  VM ID (or 'auto')", default="auto")
        constraints["ram_gb"] = str(IntPrompt.ask("  RAM (GB)", default=2))
        constraints["disk_gb"] = str(IntPrompt.ask("  Disk (GB)", default=20))
    elif target == "azure":
        constraints["location"] = Prompt.ask("  Azure region", default="eastus")
        constraints["vm_size"] = Prompt.ask("  VM size", default="Standard_B1s")
    elif target == "gcp":
        constraints["region"] = Prompt.ask("  GCP region", default="us-central1")
        constraints["machine_type"] = Prompt.ask("  Machine type", default="e2-micro")
    return constraints


@click.group()
def cli():
    """InfraInit — provision repos on any target with GPT-5.5"""


@cli.command()
@click.argument("repo")
@click.option("--target", type=click.Choice(["local", "proxmox", "azure", "render", "gcp"]))
@click.option("--fallback", is_flag=True, help="Use Ollama instead of GPT-5.5")
def setup(repo: str, target: str | None, fallback: bool):
    """Provision a repo on your chosen target."""
    if not target:
        target, provider = _pick_target()
    else:
        provider = NAME_TO_PROVIDER[target]()

    constraints = _gather_constraints(target)

    with console.status("[bold]GPT-5.5 analyzing repo..."):
        planner = Planner(use_fallback=fallback)
        plan = planner.plan(repo, target, constraints)
    console.print(f"[green]Detected:[/] {plan.get('language', 'unknown')} — {', '.join(plan.get('stack', []))}")

    executor = Executor(provider)
    result = executor.run(repo, plan)

    if result.metadata.get("verified"):
        console.print(f"\n[bold green] App running at {result.endpoint}[/]")
    else:
        console.print(f"\n[bold yellow] Provisioned but verification incomplete: {result.endpoint}[/]")


@cli.command()
@click.argument("name")
def status(name: str):
    """Show saved state and re-verify."""
    state = get_app_state(name)
    if not state:
        console.print(f"[red]No state found for '{name}'[/]")
        raise SystemExit(1)
    console.print(f"[bold]{name}[/]")
    console.print(f"  Provider: {state['provider']}")
    console.print(f"  Repo:     {state['repo']}")
    console.print(f"  Endpoint: {state.get('endpoint', 'N/A')}")
    console.print(f"  Created:  {state['created_at']}")


@cli.command()
@click.argument("name")
def destroy(name: str):
    """Tear down a provisioned app."""
    state = get_app_state(name)
    if not state:
        console.print(f"[red]No state found for '{name}'[/]")
        raise SystemExit(1)

    provider_cls = NAME_TO_PROVIDER.get(state["provider"])

    if provider_cls:
        provider = provider_cls()
        result = ProvisionResult(name=name, provider=state["provider"], endpoint=state.get("endpoint"))
        provider.destroy(result)

    remove_app_state(name)
    console.print(f"[green]'{name}' destroyed[/]")


if __name__ == "__main__":
    cli()
