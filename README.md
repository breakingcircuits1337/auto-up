# InfraInit

Provision and verify any repo on your target of choice — **local PC**, **Proxmox**, **Azure**, **Render**, or **GCP** — powered by Azure Foundry **GPT-5.5**.

```bash
pip install infrainit
InfraInit setup https://github.com/user/my-app
```

---

## Architecture

```
User: InfraInit setup <repo-url>

      ┌──────────────────────────────┐
      │  CLI (Click)                 │
      │  - pick target interactively │
      │  - or --target flag          │
      └──────┬───────────────────────┘
             │
      ┌──────▼───────────────────────┐
      │  Planner                     │
      │  - calls GPT-5.5 (Azure     │
      │    Foundry) with repo URL   │
      │  - returns structured JSON  │
      │    plan: language, stack,   │
      │    port, build_steps,       │
      │    run_command, verify      │
      └──────┬───────────────────────┘
             │
      ┌──────▼───────────────────────┐
      │  Executor                   │
      │  - provider.provision()     │
      │  - git clone repo           │
      │  - run build steps          │
      │  - provider.verify()        │
      │  - save state to disk       │
      └──────┬───────────────────────┘
             │
      ┌──────▼───────────────────────┐
      │  Provider (one per target)  │
      │  Local    → Docker Compose  │
      │  Proxmox  → VE API + LXC    │
      │  Azure    → Azure CLI + ARM │
      │  Render   → Render API      │
      │  GCP      → gcloud CLI      │
      └─────────────────────────────┘
```

Every provider implements a uniform ABC:

```python
class Provider:
    def provision(self, plan: dict) -> ProvisionResult: ...
    def verify(self, result: ProvisionResult) -> bool: ...
    def destroy(self, result: ProvisionResult) -> None: ...
```

The CLI, planner, executor, and verifier never care which target was chosen — the provider abstracts all infra differences.

---

## Walkthrough

```
$ InfraInit setup https://github.com/user/flask-app

Select target:
  1) Local PC (Docker)
  2) Proxmox server
  3) Azure
  4) Render.com
  5) Google Cloud
  Target: 2

  Proxmox node [pve1]:
  VM ID (or 'auto') [auto]:
  RAM (GB) [2]: 4
  Disk (GB) [20]: 40

GPT-5.5 analyzing repo...
Detected: python — Flask, PostgreSQL

Provisioning Proxmox VM... done
Cloning repo... done
Installing deps... done
Running app... done

✅ App running at http://192.168.1.50:5000
```

Subsequent commands:

```
$ InfraInit status flask-app
flask-app
  Provider: proxmox
  Repo:     https://github.com/user/flask-app
  Endpoint: http://192.168.1.50:5000
  Created:  2026-06-19T10:30:00

$ InfraInit destroy flask-app
'flask-app' destroyed
```

---

## Installation

### Prerequisites by target

| Target     | Requires                                 |
|------------|------------------------------------------|
| Any        | Python 3.10+, pip                        |
| Local      | Docker                                   |
| Proxmox    | Proxmox VE host, API token, SSH key      |
| Azure      | Azure CLI (`az`), logged in              |
| Render     | Render API key (dashboard → API tokens)  |
| GCP        | gcloud CLI, logged in                    |

### Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install infrainit
```

### Dev install (from source)

```bash
git clone https://github.com/your-org/infrainit
cd infrainit
python3 -m venv venv && source venv/bin/activate
pip install -e .
```

---

## Environment variables

| Variable                    | Required for | Description                          |
|-----------------------------|--------------|--------------------------------------|
| `AZURE_FOUNDRY_ENDPOINT`    | All targets  | GPT-5.5 endpoint URL                 |
| `AZURE_FOUNDRY_API_KEY`     | All targets  | GPT-5.5 API key                      |
| `AZURE_FOUNDRY_DEPLOYMENT`  | All targets  | GPT-5.5 deployment name              |
| `PROXMOX_HOST`              | Proxmox      | Proxmox VE hostname/IP               |
| `PROXMOX_TOKEN_ID`          | Proxmox      | API token ID (e.g. `root@pam!token`) |
| `PROXMOX_TOKEN_SECRET`      | Proxmox      | API token secret                     |
| `PROXMOX_SSH_PUBKEY`        | Proxmox      | Public SSH key for VM access         |
| `AZURE_SUBSCRIPTION_ID`     | Azure        | Azure subscription ID                |
| `RENDER_API_KEY`            | Render       | Render API token                     |
| `GCP_PROJECT_ID`            | GCP          | GCP project ID                       |

> **Use `--fallback` to skip Azure Foundry and run with Ollama locally** — no API key needed.

---

## CLI reference

```
InfraInit setup <repo>
  Provision a repo on your chosen target.
  Options:
    --target [local|proxmox|azure|render|gcp]   Skip interactive picker
    --fallback                                    Use Ollama instead of GPT-5.5

InfraInit status <name>
  Show saved state from ~/.infrainit/state.json.

InfraInit destroy <name>
  Tear down infrastructure and remove saved state.
```

---

## Project structure

```
infrainit/
├── pyproject.toml           Package metadata, entry point = InfraInit
├── src/infrainit/
│   ├── __main__.py          python -m infrainit
│   ├── cli/main.py          Click commands: setup, status, destroy
│   ├── core/
│   │   ├── planner.py       GPT-5.5 prompt + response → JSON plan
│   │   ├── executor.py      Clones repo, runs build steps, calls provider
│   │   └── verifier.py      HTTP health check, process check
│   ├── providers/
│   │   ├── __init__.py      Provider ABC + ProvisionResult dataclass
│   │   ├── local/provider.py    Docker Compose
│   │   ├── proxmox/provider.py  Proxmox VE REST API
│   │   ├── azure/provider.py    Azure CLI
│   │   ├── render/provider.py   Render API
│   │   └── gcp/provider.py      gcloud CLI
│   ├── llm/
│   │   ├── client.py        Azure Foundry GPT-5.5 HTTP client
│   │   ├── prompts.py       System + user prompt templates
│   │   └── fallback.py      Ollama (codellama) fallback
│   └── config/config.py     State file I/O, env var helpers
├── tests/
└── README.md
```

---

## State management

State is stored in `~/.infrainit/state.json`:

```json
{
  "my-app": {
    "provider": "local",
    "repo": "https://github.com/user/my-app",
    "endpoint": "http://localhost:8080",
    "created_at": "2026-06-19T10:30:00"
  }
}
```

This is what `status` reads and `destroy` removes.

---

## Adding a new provider

1. Create `src/infrainit/providers/<name>/provider.py`
2. Implement `Provider` ABC — `provision()`, `verify()`, `destroy()`
3. Set `name` class attribute
4. Register in `cli/main.py` — add import and add to `PROVIDERS` dict + `_pick_target` label

```python
from infrainit.providers import Provider, ProvisionResult

class MyProvider(Provider):
    name = "mycloud"

    def provision(self, plan: dict) -> ProvisionResult:
        ...

    def verify(self, result: ProvisionResult) -> bool:
        ...

    def destroy(self, result: ProvisionResult) -> None:
        ...
```

That's it — the planner, executor, and CLI work with any provider automatically.

---

## Stack detection (GPT-5.5 plan output)

When given a repo URL, GPT-5.5 returns a JSON plan like:

```json
{
  "repo": "https://github.com/user/flask-app",
  "language": "python",
  "stack": ["flask", "postgresql"],
  "port": 5000,
  "build_steps": ["pip install -r requirements.txt"],
  "run_command": "gunicorn app:app",
  "verify": {
    "type": "http",
    "port": 5000,
    "path": "/health"
  },
  "env": {"DATABASE_URL": "postgresql://..."}
}
```

The executor uses this to clone, install, run, and verify. The provider uses `port`, `stack`, and `constraints` to size infrastructure correctly.

---

## License

MIT
