"""A2A Task Server — local agent orchestration via A2A protocol.

Wraps agent_runner.run_agent() as an A2A AgentExecutor, exposing tasks
via JSON-RPC HTTP endpoints. Uses the official a2a-sdk server components.
"""

import asyncio
import logging
import threading
from typing import AsyncGenerator

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events import InMemoryQueueManager, EventQueue
from a2a.server.tasks import InMemoryTaskStore, TaskManager, TaskUpdater
from a2a.types import (
    Artifact,
    Message,
    Part,
    TaskState,
    TextPart,
)

from agent_orchestration.agent_runner import run_agent, AgentResult
from agent_orchestration.browser_fleet import get_port

logger = logging.getLogger(__name__)


class CopilotAgentExecutor(AgentExecutor):
    """Executes tasks by spawning copilot CLI agents with browser isolation."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Run an agent task asynchronously."""
        updater = context.task_updater
        await updater.start_work()

        # Extract prompt from the request message
        request = context.request
        prompt = ""
        if hasattr(request, "params") and hasattr(request.params, "message"):
            msg = request.params.message
            if msg and msg.parts:
                for part in msg.parts:
                    if hasattr(part, "root") and hasattr(part.root, "text"):
                        prompt += part.root.text
                    elif hasattr(part, "text"):
                        prompt += part.text

        if not prompt:
            await updater.failed()
            return

        # Determine which agent index to use based on task metadata
        task_id = context.task_id or "unknown"
        agent_index = hash(task_id) % 3  # Simple round-robin
        cdp_port = get_port(agent_index)

        # Run the agent in a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result: AgentResult = await loop.run_in_executor(
            None,
            lambda: run_agent(
                task_id=task_id,
                prompt=prompt,
                cdp_port=cdp_port,
            ),
        )

        # Handle blocker detection
        if result.blocked:
            await updater.requires_input()
            await updater.new_agent_message(
                Message(
                    role="agent",
                    parts=[Part(root=TextPart(text=f"BLOCKED: {result.block_reason}"))],
                )
            )
            return

        # Create artifact with the agent's output
        artifact = Artifact(
            name="agent-output",
            parts=[Part(root=TextPart(text=result.output))],
            metadata={
                "elapsed_seconds": result.elapsed_seconds,
                "exit_code": result.exit_code,
                "success": result.success,
                "cdp_port": cdp_port,
            },
        )
        await updater.add_artifact(artifact)

        if result.success:
            await updater.complete()
        else:
            await updater.failed()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a running agent task."""
        updater = context.task_updater
        await updater.cancel()


def create_task_store() -> InMemoryTaskStore:
    """Create an in-memory task store for tracking task state."""
    return InMemoryTaskStore()


def create_agent_card() -> dict:
    """Return the agent card for this orchestration server."""
    return {
        "name": "agent-orchestration",
        "description": "Multi-agent orchestration with isolated K8s browsers",
        "url": "http://localhost:8420",
        "version": "0.1.0",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "skills": [
            {"id": "shopping", "name": "Shopping Agent", "description": "Navigate e-commerce sites, build carts, read order history"},
            {"id": "finance", "name": "Finance Agent", "description": "Scan bank transactions, audit subscriptions"},
            {"id": "general", "name": "General Agent", "description": "Any browser-based or CLI task"},
        ],
    }
