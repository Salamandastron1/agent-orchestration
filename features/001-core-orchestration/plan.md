# Implementation Plan: Core Agent Orchestration

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Coordinator (VS Code Copilot / Claude Code / any client)    │
│  - Reads task definitions                                   │
│  - Dispatches agents via A2A SendTask                       │
│  - Polls task state (working/input-required/completed)      │
│  - Validates results, redispatches on failure               │
├─────────────────────────────────────────────────────────────┤
│ A2A Task Server (Python, runs locally)                      │
│  - Accepts tasks via JSON-RPC                               │
│  - Spawns copilot CLI (or any agent) as subprocess          │
│  - Updates task state as agent progresses                   │
│  - Exposes GET /tasks/{id} for status polling               │
├─────────────────────────────────────────────────────────────┤
│ Secret Store (Python CLI + library)                         │
│  - get/set/list/delete secrets by name                      │
│  - macOS: Keychain via `security` CLI                       │
│  - Agents call: `secret-store get amazon`                   │
│  - LP vault is one source; Keychain is the single store     │
├─────────────────────────────────────────────────────────────┤
│ Browser Fleet (K8s via azbox)                               │
│  - corpbrowser-0 (30920), -1 (30921), -2 (30923)           │
│  - PVC-persisted sessions                                   │
│  - MCP tools route via CDP_PORT env var                     │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Python 3.11+** — all components
- **A2A SDK** (`a2a-sdk`) — task lifecycle, agent cards
- **MCP** — tool routing (existing infrastructure)
- **macOS Keychain** (`security` CLI) — secret encryption
- **K8s / azbox** — browser fleet (existing)
- **pytest** — testing
- **Spec Kit** — development process

## Components

### 1. Secret Store (`src/agent_orchestration/secrets.py`)
Consolidates all credential access behind one interface.

**Backends:**
- **Keychain** (primary): `security find-generic-password -s "agent-orchestration" -a "{name}" -w`
- **LP Vault** (import): one-time extraction from LP → stored in Keychain

**CLI:** `python -m agent_orchestration.secrets get amazon`
**Library:** `from agent_orchestration.secrets import get_secret, set_secret`

**Migration path:**
1. Import existing LP vault creds → Keychain entries
2. `lp_vault.py` becomes an optional import source, not the runtime store
3. Agents call `secret-store get {name}` or read from Keychain directly

### 2. A2A Task Server (`src/agent_orchestration/server.py`)
Local HTTP server exposing A2A-compatible endpoints.

**Endpoints:**
- `POST /tasks/send` — submit a new task
- `GET /tasks/{id}` — get task status + artifacts
- `POST /tasks/{id}/cancel` — cancel a running task

**Task states** (A2A standard):
- `submitted` → `working` → `completed` | `failed` | `input-required` | `canceled`

**Agent spawning:**
- On task submit: start `copilot -p "{prompt}" --model claude-sonnet-4 --no-ask-user --allow-all-tools`
- Set `CDP_PORT` for browser isolation
- Monitor stdout for progress markers
- Write artifacts to task result on completion

### 3. Coordinator (`src/agent_orchestration/coordinator.py`)
Client that submits tasks and monitors progress.

**Workflow:**
1. Read task definitions (JSON or Python)
2. Ensure browser fleet is up (`azbox up --stack agent-browsers`)
3. Submit tasks to A2A server
4. Poll task states every 2 seconds
5. On `input-required`: prompt user (VS Code notification or terminal)
6. On `completed`: validate result, accept or redispatch
7. Collect all results, report summary

### 4. Agent Cards (`agent-cards/`)
JSON manifests describing each agent's capabilities in A2A format.

```json
{
  "name": "shopping-agent",
  "description": "Navigates e-commerce sites, builds carts, reads order history",
  "url": "http://localhost:8420",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "skills": [
    {"name": "amazon-orders", "description": "Search Amazon order history"},
    {"name": "costco-cart", "description": "Build Costco Same-Day cart"},
    {"name": "chase-transactions", "description": "Scan Chase bank transactions"}
  ]
}
```

## Directory Structure

```
agent-orchestration/
├── .specify/                    # Spec Kit memory + templates
├── .github/                     # Spec Kit agents + prompts
├── features/
│   └── 001-core-orchestration/
│       ├── spec.md
│       ├── plan.md              # (this file)
│       └── tasks.md
├── src/
│   └── agent_orchestration/
│       ├── __init__.py
│       ├── secrets.py           # Consolidated secret store
│       ├── server.py            # A2A task server
│       ├── coordinator.py       # Task dispatch + monitoring
│       ├── browser_fleet.py     # K8s browser lifecycle
│       └── agent_runner.py      # Subprocess agent execution
├── agent-cards/
│   └── shopping-agent.json
├── tests/
│   ├── test_secrets.py
│   ├── test_server.py
│   ├── test_coordinator.py
│   └── test_integration.py
├── pyproject.toml
└── README.md
```

## Migration from llm-config

| llm-config file | → agent-orchestration | Change |
|----------------|----------------------|--------|
| `copilot-tools/bin/agent-orchestrate.py` | `src/agent_orchestration/coordinator.py` | Rewrite with A2A client |
| `copilot-tools/lib/lp_vault.py` | Import source for `secrets.py` | LP → Keychain migration |
| `azbox/stacks/agent-browsers.yaml` | Referenced by `browser_fleet.py` | No change, stay in llm-config |
| `mcp-servers/browser-cdp/cdp_client.py` | CDP_PORT env routing stays | No change |
| `~/.copilot/mcp-config.json` | Stays as-is | No change |
| `~/.copilot/instructions.md` | Updated to reference new tools | Add secret-store commands |

## What We DON'T Build
- Custom inter-agent messaging (A2A handles it)
- Custom memory layer (existing Keychain + SQLite sufficient for now; Mem0 is a future option)
- Framework abstractions (no CrewAI/AutoGen dependency — we use the protocol directly)
