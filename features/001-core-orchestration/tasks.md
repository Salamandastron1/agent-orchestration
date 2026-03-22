# Tasks: Core Agent Orchestration

## Task 1: Secret Store
**Branch:** `feat/secret-store`

Create `src/agent_orchestration/secrets.py`:
- `get_secret(name: str) -> str` — reads from macOS Keychain (`security find-generic-password -s "agent-orch" -a "{name}" -w`)
- `set_secret(name: str, value: str)` — writes to Keychain (`security add-generic-password -s "agent-orch" -a "{name}" -w "{value}" -U`)
- `list_secrets() -> list[str]` — lists all agent-orch entries
- `delete_secret(name: str)` — removes entry
- `import_from_lp(tile_name: str)` — uses `lp_vault.py` to extract from LP vault → stores in Keychain
- CLI: `python -m agent_orchestration.secrets get|set|list|delete|import-lp`

**Tests** (`tests/test_secrets.py`):
- get/set round-trip
- list returns stored names
- delete removes entry
- import_from_lp populates Keychain (mock LP vault)
- get nonexistent returns clean error

**Done when:** `python -m agent_orchestration.secrets set test-key test-value && python -m agent_orchestration.secrets get test-key` returns `test-value`

---

## Task 2: Agent Runner
**Branch:** `feat/agent-runner`

Create `src/agent_orchestration/agent_runner.py`:
- `run_agent(prompt, cdp_port=None, model="claude-sonnet-4", timeout=300) -> AgentResult`
- Spawns `copilot` CLI as subprocess with `CDP_PORT`, `GH_TOKEN`, `COPILOT_AGENT_NONINTERACTIVE=1`
- Parses stdout for progress markers: lines starting with `[STATUS]` update task state
- Returns structured `AgentResult(success, output, elapsed, usage)`
- Agent prompt preamble: includes browser port + secret-store instructions

**Tests** (`tests/test_agent_runner.py`):
- Subprocess called with correct env vars
- CDP_PORT injected when provided
- Timeout produces clean failure
- Progress markers extracted from output

**Done when:** Unit tests pass, manual test against live copilot CLI succeeds

---

## Task 3: Browser Fleet Manager
**Branch:** `feat/browser-fleet`

Create `src/agent_orchestration/browser_fleet.py`:
- `ensure_fleet(count=3) -> list[int]` — runs `azbox up --stack agent-browsers`, returns ports
- `fleet_status() -> dict` — health check each port, returns {port: healthy/unhealthy}
- `get_port(agent_index: int) -> int` — returns port for agent i (from AGENT_BROWSER_PORTS constant)
- Reuses existing azbox infrastructure (no new K8s manifests)

**Tests** (`tests/test_browser_fleet.py`):
- Port mapping is correct (30920, 30921, 30923)
- ensure_fleet is idempotent (safe to call twice)
- fleet_status returns health for each port

**Done when:** `python -m agent_orchestration.browser_fleet status` shows 3 healthy browsers

---

## Task 4: A2A Task Server
**Branch:** `feat/a2a-server`

Create `src/agent_orchestration/server.py`:
- Lightweight HTTP server using `a2a-sdk`
- Endpoints: `POST /tasks/send`, `GET /tasks/{id}`, `POST /tasks/{id}/cancel`
- Task states: submitted → working → completed | failed | input-required
- Spawns agent via `agent_runner.run_agent()` in background thread
- Stores task state in memory (dict, not DB — tasks are ephemeral)
- Agents signal `input-required` by writing `[BLOCKED] reason` to stdout

**Tests** (`tests/test_server.py`):
- Submit task returns task ID
- Get task returns current state
- Cancel stops running agent
- Blocked agent transitions to input-required state
- Completed agent has artifacts in result

**Done when:** `curl localhost:8420/tasks/send -d '{"prompt":"list tabs"}'` returns task ID, polling shows completion

---

## Task 5: Coordinator
**Branch:** `feat/coordinator`

Create `src/agent_orchestration/coordinator.py`:
- `dispatch(tasks: list[dict], browsers=True) -> list[TaskResult]`
- Ensures browser fleet
- Submits tasks to A2A server
- Polls every 2 seconds
- On `input-required`: prints to stderr, waits for user input
- On `completed`: returns result
- On `failed`: logs error, includes in results
- Supervisor validation: optional callback `validate(result) -> bool`

**Tests** (`tests/test_coordinator.py`):
- Dispatch submits N tasks
- Polling detects completion
- Input-required triggers escalation callback
- Failed tasks included in results
- Validator can reject and redispatch

**Done when:** Full flow works: dispatch 3 tasks → monitor → collect results

---

## Task 6: Integration Test
**Branch:** `feat/integration-test`

Create `tests/test_integration.py`:
- Starts A2A server
- Dispatches 3 agents with `--browsers`
- Each navigates to a different site on its own K8s browser
- Verifies all 3 complete with correct data
- Verifies browsers are isolated (no cross-contamination)
- Verifies secret-store access works from within agent

**Done when:** `pytest tests/test_integration.py` passes with 3 live K8s browsers

---

## Task 7: Migrate agent-orchestrate.py
**Branch:** `feat/migrate-orchestrate`

Update `llm-config/copilot-tools/bin/agent-orchestrate.py`:
- Import and delegate to `agent_orchestration` library
- Keep CLI interface identical (backward compatible)
- `--browsers` flag uses `browser_fleet.ensure_fleet()`
- Task dispatch uses coordinator instead of raw ThreadPoolExecutor

**Done when:** Existing `agent-orchestrate.py run --browsers -t "task"` works using new library

---

## Task 8: Package + Push
**Branch:** `feat/packaging`

- Create `pyproject.toml` with deps: `a2a-sdk`, `requests`
- Add `README.md` with quickstart
- `pip install -e .` works
- Create GitHub repo `Salamandastron1/agent-orchestration`
- Push initial code
- Update `llm-config` instructions to reference new repo

**Done when:** `pip install -e ~/working/agent-orchestration` imports cleanly, all tests pass
