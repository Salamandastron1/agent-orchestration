# Agent Orchestration

Standards-based multi-agent orchestration with [A2A protocol](https://github.com/a2aproject/A2A), isolated K8s browsers, and consolidated Keychain secrets.

## What This Does

Dispatches parallel LLM agents (Copilot CLI, Claude Code, or any A2A-compatible client), each with:
- **Its own isolated browser** (K8s Chromium pod via azbox)
- **Shared secrets** from macOS Keychain (no credentials in prompts or temp files)
- **Blocker detection** (MFA/captcha → escalation to coordinator)
- **Supervisor validation** (coordinator verifies results before accepting)
- **A2A task lifecycle** (submitted → working → input-required → completed/failed)

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Store a secret
python -m agent_orchestration.secrets set amazon '{"user":"me@example.com","pass":"xxx"}'

# Check browser fleet
python -m agent_orchestration.browser_fleet status

# Run 3 parallel agents with browsers
python -m agent_orchestration.coordinator run --browsers \
  -t "Search Amazon order history for Vitamin C" \
  -t "Build Costco cart: bread, peanut butter, vinegar" \
  -t "Scan Chase transactions for recurring charges"
```

## Architecture

```
Coordinator (dispatch + monitor + validate)
    │
    ├── Agent 0 ──→ K8s Browser (port 30920) ──→ Amazon
    ├── Agent 1 ──→ K8s Browser (port 30921) ──→ Costco
    └── Agent 2 ──→ K8s Browser (port 30923) ──→ Chase
    
Secret Store (macOS Keychain)
    └── get/set/list/delete + LP vault import
```

## Components

| Component | File | Purpose |
|-----------|------|---------|
| **Secret Store** | `src/agent_orchestration/secrets.py` | Keychain-backed credential management |
| **Agent Runner** | `src/agent_orchestration/agent_runner.py` | Subprocess agent execution with CDP port isolation |
| **Browser Fleet** | `src/agent_orchestration/browser_fleet.py` | K8s browser lifecycle via azbox |
| **Coordinator** | `src/agent_orchestration/coordinator.py` | Parallel dispatch + monitoring + escalation |
| **A2A Server** | `src/agent_orchestration/server.py` | A2A protocol task server (AgentExecutor) |

## Standards

- **A2A** (Agent2Agent Protocol) — task lifecycle and inter-agent communication
- **MCP** (Model Context Protocol) — tool routing to browsers and M365
- **macOS Keychain** — secret encryption at rest

## Tests

```bash
pytest  # 46 tests
```

## Scaffolded With

[GitHub Spec Kit](https://github.com/github/spec-kit) v0.3.2 — spec-driven development
