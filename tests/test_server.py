"""Tests for the A2A task server."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agent_orchestration.server import (
    CopilotAgentExecutor,
    create_task_store,
    create_agent_card,
)
from agent_orchestration.agent_runner import AgentResult


class TestAgentCard:
    """Test agent card generation."""

    def test_has_required_fields(self):
        card = create_agent_card()
        assert "name" in card
        assert "url" in card
        assert "skills" in card
        assert "capabilities" in card

    def test_has_skills(self):
        card = create_agent_card()
        assert len(card["skills"]) >= 1
        assert all("name" in s for s in card["skills"])

    def test_url_is_localhost(self):
        card = create_agent_card()
        assert "localhost" in card["url"]


class TestTaskStore:
    """Test task store creation."""

    def test_creates_successfully(self):
        store = create_task_store()
        assert store is not None


class TestCopilotAgentExecutor:
    """Test the executor that wraps copilot CLI agents."""

    def test_is_agent_executor(self):
        from a2a.server.agent_execution import AgentExecutor
        executor = CopilotAgentExecutor()
        assert isinstance(executor, AgentExecutor)

    def test_has_execute_and_cancel(self):
        executor = CopilotAgentExecutor()
        assert hasattr(executor, "execute")
        assert hasattr(executor, "cancel")
