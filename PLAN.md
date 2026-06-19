# InfraInit — Project Plan

## Overview

A CLI tool that bootstraps a complete development environment on any target (local PC, Proxmox, Azure, Render, GCP) using an Azure Foundry-hosted GPT-5.5 model as its reasoning and orchestration engine. The user picks a target; the tool provisions infra, clones repos, installs dependencies, and verifies everything works.

## Core Architecture

```
User runs: InfraInit setup <repo-url>

       ┌─────────────────────────────┐
       │  Step 1: Choose target       │
       │  1) Local PC                 │
       │  2) Proxmox server           │
       │  3) Cloud (Azure/Render/GCP) │
       └──────────┬──────────────────┘
                  │
       ┌──────────▼──────────────────┐
       │  Step 2: GPT-5.5 (brain)    │
       │  - Reads repo (lang, stack) │
       │  - Generates provision plan │
       │  - Returns structured JSON  │
       └──────────┬──────────────────┘
                  │
       ┌──────────▼──────────────────┐
       │  Step 3: Executor runs plan  │
       │  - Provision infra          │
       │  - Clone + install          │
       │  - Verify (smoke tests)     │
       │  - Print URL/status         │
       └─────────────────────────────┘
```

GPT-5.5 (Azure Foundry) is the brain — it analyzes the repo, understands the stack, and outputs a structured provisioning plan. The executor is a dumb runner that follows the plan.

## User Experience

```
$ InfraInit setup https://github.com/user/my-app

Select target:
  1) Local PC (Docker)
  2) Proxmox server
  3) Cloud (Azure / Render / GCP)

> 2

Enter Proxmox node: pve1
VM ID (or auto): auto
RAM (GB) [2]: 4
Disk (GB) [20]: 40

GPT-5.5 analyzing repo... (Python/Flask, PostgreSQL)
Provisioning Proxmox VM... done
Cloning repo... done
Installing deps... done
Running app... done

✅ App running at http://192.168.1.50:5000
```

## GPT-5.5 Integration (Azure Foundry)

- Model: `gpt-5.5` deployed on Azure Foundry
- System prompt: expert infra engineer
- Input: repo URL + target type + user constraints
- Output: structured JSON (`{provider, resources, steps, verify}`)
- Fallback: Ollama (codellama) if Azure unreachable

## Project Structure

```
src/infrainit/
├── __init__.py
├── __main__.py            # python -m infrainit
├── cli/
│   ├── __init__.py
│   └── main.py            # InfraInit CLI entry point
├── core/
│   ├── __init__.py
│   ├── planner.py         # Calls GPT-5.5, parses plan
│   ├── executor.py        # Walks plan steps, handles errors
│   └── verifier.py        # Post-provision smoke tests
├── providers/
│   ├── __init__.py        # Provider ABC
│   ├── local/
│   │   ├── __init__.py
│   │   └── provider.py
│   ├── proxmox/
│   │   ├── __init__.py
│   │   └── provider.py
│   ├── azure/
│   │   ├── __init__.py
│   │   └── provider.py
│   ├── render/
│   │   ├── __init__.py
│   │   └── provider.py
│   └── gcp/
│       ├── __init__.py
│       └── provider.py
├── llm/
│   ├── __init__.py
│   ├── client.py          # Azure Foundry HTTP client
│   ├── prompts.py         # Prompt templates
│   └── fallback.py        # Ollama
├── config/
│   ├── __init__.py
│   └── config.py          # Secret management + state
├── pyproject.toml
├── tests/
└── README.md
```

## Provider Interface (uniform across all targets)

Every provider implements three methods:

```python
class Provider:
    def provision(self, plan: dict) -> ProvisionResult: ...
    def verify(self, result: ProvisionResult) -> bool: ...
    def destroy(self, result: ProvisionResult) -> None: ...
```

The CLI doesn't care which provider is chosen. It calls `provision()`, then `verify()`, reports the result.

## Verification Per Target

| Target   | Verify checks                                     |
|----------|--------------------------------------------------|
| Local    | Process alive, `curl localhost:<port>`           |
| Proxmox  | Ping + SSH + `curl <vm-ip>:<port>`               |
| Azure    | `az vm show` status, public IP reachable         |
| Render   | Render API health endpoint                       |
| GCP      | `gcloud compute instances describe`, LB health   |

## Build Approach: Pick One, Build One

Each provider is **independently buildable and shippable**. Build order is the user's choice, not a phased roadmap.

| Provider  | Dependencies                    | Complexity | Build time |
|-----------|---------------------------------|------------|------------|
| Local     | Docker, Python                  | Low        | 1 day      |
| Render    | Render API key                  | Low        | 1 day      |
| Azure     | Azure CLI, subscription         | Medium     | 2 days     |
| GCP       | gcloud CLI, project             | Medium     | 2 days     |
| Proxmox   | Proxmox VE API access           | Medium     | 2 days     |

The **CLI skeleton + GPT-5.5 client** is built once (shared). Then any provider can be built and shipped independently.

## State Management

Simple local JSON file at `~/.infrainit/state.json`:

```json
{
  "my-app": {
    "provider": "proxmox",
    "repo": "https://github.com/user/my-app",
    "result": { "ip": "192.168.1.50", "port": 5000 },
    "created_at": "2026-06-17T12:00:00Z"
  }
}
```

Commands:

```
InfraInit setup <repo>     # Full setup (pick target → GPT-5.5 → provision → verify)
InfraInit status <name>    # Show saved state, re-verify
InfraInit update <name>    # git pull + reinstall + re-verify
InfraInit destroy <name>   # Tear down + remove state
```

## Key Design Decisions

| Decision       | Choice        | Rationale                                    |
|---------------|---------------|----------------------------------------------|
| Language      | Python        | Broadest cloud SDK coverage, fast to build   |
| Provider interface | 3-method ABC | Uniform contract, easy to add new targets   |
| Secrets       | keyring + env | Never stored in files                        |
| LLM fallback  | Ollama        | Works offline, no API key needed            |
| Delivery      | pip install   | `pip install InfraInit && InfraInit setup`   |
| Config format | YAML          | Readable, editable by user                   |
| CLI entry     | `InfraInit`   | Capital-I name as global command             |

## Risks

| Risk                     | Mitigation                                     |
|--------------------------|------------------------------------------------|
| GPT-5.5 API cost         | Cache plans, fallback to Ollama for re-runs    |
| Proxmox host unreachable | Check connectivity before starting provision   |
| Cloud bill overrun       | Enforce budget constraints in GPT-5.5 prompt   |
| Provider API drift       | Pin SDK versions, integration tests per target |
