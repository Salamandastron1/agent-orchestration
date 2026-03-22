# Agent Orchestration Constitution

## Core Principles

### I. Standards Over Custom Code
Adopt open standards (A2A, MCP) and existing tools before building custom implementations. Every custom component must justify why an existing standard or library doesn't suffice. If a platform (Copilot, Claude, Cursor) ships a native feature that replaces our code, we delete our code.

### II. Agent-Agnostic by Design
All orchestration primitives must work with any LLM agent: GitHub Copilot CLI, Claude Code, OpenAI Codex, Cursor, or a raw Python script. No framework lock-in. Agents interact via protocols (A2A JSON-RPC, MCP stdio, HTTP), not library imports.

### III. Idempotent and Composable
Every operation is safe to retry. Deploying browser fleet when it's already running is a no-op. Starting an agent that already completed returns its cached result. Components compose: browser fleet works without orchestrator, orchestrator works without browsers, secrets work without either.

### IV. Secrets Never Leave Secure Stores
Credentials live in macOS Keychain (or platform equivalent) and browser PVC sessions. Never in env vars, temp files, prompts, logs, or git. The consolidated secret store uses Keychain for encryption at rest and provides a CLI interface for agents to retrieve secrets by name.

### V. Test-Driven with Integration Proof
Unit tests verify wiring. Integration tests prove the system actually works end-to-end. No component ships without both. Tests run in the existing pytest infrastructure. Mock external services, but always have at least one real integration test against live K8s pods.

### VI. Observable Execution
Agents report progress via A2A task state updates. The coordinator can inspect any agent's browser via CDP screenshot at any time. All runs are logged with timing, token usage, and success/failure. Escalation happens within 5 seconds of a blocker being detected.

## [SECTION_2_NAME]
<!-- Example: Additional Constraints, Security Requirements, Performance Standards, etc. -->

[SECTION_2_CONTENT]
<!-- Example: Technology stack requirements, compliance standards, deployment policies, etc. -->

## [SECTION_3_NAME]
<!-- Example: Development Workflow, Review Process, Quality Gates, etc. -->

[SECTION_3_CONTENT]
<!-- Example: Code review requirements, testing gates, deployment approval process, etc. -->

## Governance
<!-- Example: Constitution supersedes all other practices; Amendments require documentation, approval, migration plan -->

[GOVERNANCE_RULES]
<!-- Example: All PRs/reviews must verify compliance; Complexity must be justified; Use [GUIDANCE_FILE] for runtime development guidance -->

**Version**: [CONSTITUTION_VERSION] | **Ratified**: [RATIFICATION_DATE] | **Last Amended**: [LAST_AMENDED_DATE]
<!-- Example: Version: 2.1.1 | Ratified: 2025-06-13 | Last Amended: 2025-07-16 -->
