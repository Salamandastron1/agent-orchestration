"""Coordinator — dispatches parallel agents and monitors task lifecycle.

This is the main entry point for running multi-agent tasks. It:
1. Ensures the browser fleet is deployed
2. Spawns agents in parallel (one per task)
3. Monitors for blockers (input-required state)
4. Collects and validates results
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from agent_orchestration.agent_runner import run_agent, AgentResult
from agent_orchestration.browser_fleet import ensure_fleet, get_port, fleet_status


@dataclass
class TaskDefinition:
    """A task to be dispatched to an agent."""
    prompt: str
    id: str = ""
    timeout: int = 300
    model: str = "claude-sonnet-4"


@dataclass
class OrchestrationResult:
    """Result of a full orchestration run."""
    results: list[AgentResult]
    total_time: float
    succeeded: int
    failed: int
    blocked: int

    @property
    def all_succeeded(self) -> bool:
        return self.failed == 0 and self.blocked == 0


def dispatch(
    tasks: list[TaskDefinition | dict | str],
    browsers: bool = True,
    max_agents: int = 3,
    validate: Callable[[AgentResult], bool] | None = None,
    on_blocked: Callable[[AgentResult], None] | None = None,
) -> OrchestrationResult:
    """Dispatch multiple tasks in parallel with optional browser fleet.
    
    Args:
        tasks: List of task definitions (str, dict, or TaskDefinition)
        browsers: Deploy K8s browser fleet and assign ports
        max_agents: Maximum concurrent agents
        validate: Optional callback to validate results (return False to flag as failed)
        on_blocked: Optional callback when an agent is blocked (e.g., MFA)
    """
    # Normalize task definitions
    normalized: list[TaskDefinition] = []
    for i, task in enumerate(tasks):
        if isinstance(task, str):
            normalized.append(TaskDefinition(prompt=task, id=f"task-{i+1}"))
        elif isinstance(task, dict):
            normalized.append(TaskDefinition(
                prompt=task["prompt"],
                id=task.get("id", f"task-{i+1}"),
                timeout=task.get("timeout", 300),
                model=task.get("model", "claude-sonnet-4"),
            ))
        else:
            if not task.id:
                task.id = f"task-{i+1}"
            normalized.append(task)

    # Deploy browser fleet if requested
    if browsers:
        print("Deploying agent browser fleet...")
        ports = ensure_fleet(count=min(len(normalized), max_agents))
        status = fleet_status()
        for port, health in status.items():
            print(f"  Port {port}: {health}")
    
    print(f"\nDispatching {len(normalized)} tasks across {min(len(normalized), max_agents)} agents...")
    start = time.time()

    results: list[AgentResult] = []

    with ThreadPoolExecutor(max_workers=max_agents) as executor:
        futures = {}
        for i, task in enumerate(normalized):
            cdp_port = get_port(i) if browsers else None
            future = executor.submit(
                run_agent,
                task_id=task.id,
                prompt=task.prompt,
                cdp_port=cdp_port,
                model=task.model,
                timeout=task.timeout,
            )
            futures[future] = task
            print(f"  [{task.id}] Started (port {cdp_port}): {task.prompt[:60]}...")

        print()
        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
                
                # Handle blocker
                if result.blocked:
                    print(f"  [{task.id}] BLOCKED: {result.block_reason}")
                    if on_blocked:
                        on_blocked(result)
                
                # Validate if callback provided
                elif result.success and validate:
                    if not validate(result):
                        result.success = False
                        print(f"  [{task.id}] REJECTED by validator")
                    else:
                        print(f"  [{task.id}] OK ({result.elapsed_seconds}s)")
                elif result.success:
                    print(f"  [{task.id}] OK ({result.elapsed_seconds}s)")
                else:
                    print(f"  [{task.id}] FAIL ({result.elapsed_seconds}s)")

                results.append(result)
            except Exception as e:
                print(f"  [{task.id}] ERROR: {e}")
                results.append(AgentResult(
                    task_id=task.id, success=False, output=str(e),
                    elapsed_seconds=0, exit_code=-1,
                ))

    total_time = round(time.time() - start, 1)
    succeeded = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success and not r.blocked)
    blocked = sum(1 for r in results if r.blocked)

    print(f"\n=== Complete: {succeeded} OK, {failed} failed, {blocked} blocked, {total_time}s total ===")

    return OrchestrationResult(
        results=results,
        total_time=total_time,
        succeeded=succeeded,
        failed=failed,
        blocked=blocked,
    )


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Agent orchestration coordinator")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run tasks")
    run_p.add_argument("--task", "-t", action="append", help="Task prompt")
    run_p.add_argument("--browsers", "-b", action="store_true", help="Deploy browser fleet")
    run_p.add_argument("--max-agents", "-n", type=int, default=3)
    run_p.add_argument("--model", "-m", default="claude-sonnet-4")
    run_p.add_argument("--output", "-o", help="Write results to JSON file")
    run_p.add_argument("--tasks-file", help="JSON file with task definitions")

    sub.add_parser("status", help="Check browser fleet status")

    args = parser.parse_args()

    if args.command == "run":
        tasks = []
        if args.tasks_file:
            with open(args.tasks_file) as f:
                data = json.load(f)
            tasks = data if isinstance(data, list) else data.get("tasks", [])
        elif args.task:
            tasks = [{"prompt": t, "model": args.model} for t in args.task]
        else:
            parser.error("Provide --task or --tasks-file")

        result = dispatch(tasks, browsers=args.browsers, max_agents=args.max_agents)

        if args.output:
            with open(args.output, "w") as f:
                json.dump(
                    [{"task_id": r.task_id, "success": r.success, "output": r.output,
                      "elapsed": r.elapsed_seconds, "blocked": r.blocked} for r in result.results],
                    f, indent=2,
                )
            print(f"Results → {args.output}")

        sys.exit(0 if result.all_succeeded else 1)

    elif args.command == "status":
        status = fleet_status()
        for port, health in status.items():
            print(f"  Port {port}: {health}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
