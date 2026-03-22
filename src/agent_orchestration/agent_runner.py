"""Agent runner — spawns LLM agent as subprocess with isolated browser."""

import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


DEFAULT_MODEL = "claude-sonnet-4"


@dataclass
class AgentResult:
    """Result from an agent execution."""
    task_id: str
    success: bool
    output: str
    elapsed_seconds: float
    exit_code: int = 0
    usage: dict = field(default_factory=dict)
    blocked: bool = False
    block_reason: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


def _find_copilot() -> str | None:
    """Locate the copilot CLI binary."""
    import shutil
    path = shutil.which("copilot")
    if path:
        return path
    # Check common locations
    for candidate in [
        os.path.expanduser("~/.local/bin/copilot"),
        "/usr/local/bin/copilot",
    ]:
        if os.path.isfile(candidate):
            return candidate
    return None


def run_agent(
    task_id: str,
    prompt: str,
    cdp_port: int | None = None,
    model: str = DEFAULT_MODEL,
    timeout: int = 300,
    workdir: str | None = None,
) -> AgentResult:
    """Execute a single agent task via copilot CLI.
    
    Args:
        task_id: Unique identifier for this task
        prompt: The task prompt
        cdp_port: CDP port for browser isolation (None = no browser)
        model: LLM model to use
        timeout: Max execution time in seconds
        workdir: Working directory for the agent
    """
    copilot_bin = _find_copilot()
    if not copilot_bin:
        return AgentResult(
            task_id=task_id, success=False, output="copilot CLI not found",
            elapsed_seconds=0, exit_code=-1,
        )

    # Prepend browser instructions if port assigned
    if cdp_port:
        prompt = (
            f"You have a dedicated browser on CDP port {cdp_port}. "
            f"Use the browser-cdp MCP tools (cdp_navigate, cdp_fill, cdp_click_button, etc.) "
            f"to interact with it. Do NOT use port 9222 (coordinator's browser).\n\n"
            f"If you encounter MFA, captcha, or any blocker you cannot resolve, "
            f"output a line starting with [BLOCKED] followed by the reason.\n\n"
        ) + prompt

    cmd = [copilot_bin, "-p", prompt, "--model", model, "--no-ask-user", "--allow-all-tools"]

    env = os.environ.copy()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        # Try gh CLI
        try:
            result = subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                token = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    if token:
        env["GH_TOKEN"] = token
    env["COPILOT_AGENT_NONINTERACTIVE"] = "1"
    if cdp_port:
        env["CDP_PORT"] = str(cdp_port)

    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=workdir or os.getcwd(), env=env,
        )
        elapsed = time.time() - start
        output = result.stdout + result.stderr

        # Check for blocker signals
        blocked = False
        block_reason = ""
        for line in output.split("\n"):
            if line.strip().startswith("[BLOCKED]"):
                blocked = True
                block_reason = line.strip()[len("[BLOCKED]"):].strip()
                break

        has_error = (
            result.returncode != 0
            or output.strip().startswith("Error:")
            or "is not available" in output
        )

        return AgentResult(
            task_id=task_id,
            success=not has_error and not blocked,
            output=output,
            elapsed_seconds=round(elapsed, 1),
            exit_code=result.returncode,
            blocked=blocked,
            block_reason=block_reason,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return AgentResult(
            task_id=task_id, success=False,
            output=f"Timeout after {timeout}s",
            elapsed_seconds=round(elapsed, 1), exit_code=-1,
        )
