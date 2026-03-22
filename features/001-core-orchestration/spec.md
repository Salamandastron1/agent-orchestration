# Feature 001: Core Agent Orchestration

## What
A coordinator that dispatches parallel LLM agents, each with an isolated browser and shared secrets access, using the A2A protocol for task lifecycle and MCP for tool access. Replaces the current fire-and-forget `agent-orchestrate.py` with a standards-based system that supports progress monitoring, escalation, and supervisor validation.

## Why
Current system dispatches agents but cannot monitor them, escalate blockers, or validate results. Agents pass credentials via prompts. No inter-agent communication. This limits us to independent tasks with no error recovery.

## User Stories

### 1. Parallel task dispatch with browser isolation
As a coordinator, I dispatch 3 shopping agents. Each gets its own K8s Chromium pod. They log into Amazon, Costco, Chase using sessions persisted in PVCs. No credentials are passed in prompts.

### 2. Progress monitoring
As a coordinator, I can see each agent's current status (navigating, filling form, blocked) in real-time via A2A task state. I don't have to wait for completion to know what's happening.

### 3. Escalation on blocker
An agent hits MFA on Chase. It updates its A2A task to `input-required` with a message describing what it needs. The coordinator detects this within 5 seconds and prompts the user.

### 4. Supervisor validation
After an agent reports "Costco cart built with 5 items", the coordinator inspects the result. If only 3 items were found, it redispatches with a refined prompt for the missing 2.

### 5. Consolidated secret store
All agents access credentials through one interface: `secret-store get amazon` returns the credential from Keychain. Works on macOS (Keychain) and can be extended to other platforms. Replaces LP vault extraction + temp file passing.

### 6. Agent-agnostic execution
The same task definition runs on Copilot CLI, Claude Code, or any A2A-compatible client. The orchestrator doesn't care which LLM backs the agent.

## Out of Scope (this feature)
- D365/MSX MCP tool wrappers (separate feature)
- Mem0 integration for long-term agent memory (separate feature)
- Multi-step dependency graphs (DAG execution) — future feature
- Cross-machine agent dispatch (single machine for now)

## Existing Infrastructure to Consolidate
- `llm-config/copilot-tools/bin/agent-orchestrate.py` → becomes thin wrapper calling this library
- `llm-config/copilot-tools/lib/lp_vault.py` → LP vault extraction becomes one backend for secret-store
- `llm-config/azbox/stacks/agent-browsers.yaml` → stays as-is (K8s browser fleet)
- `~/.copilot/mcp-config.json` → stays as-is (MCP tool routing)
- macOS Keychain (`security` CLI) → becomes the encryption backend for secret-store
