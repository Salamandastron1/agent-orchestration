"""Tests for the coordinator."""

import pytest
from unittest.mock import patch, MagicMock

from agent_orchestration.coordinator import (
    dispatch, TaskDefinition, OrchestrationResult,
)
from agent_orchestration.agent_runner import AgentResult


class TestTaskNormalization:
    """Test that dispatch normalizes various task input formats."""

    @patch("agent_orchestration.coordinator.run_agent")
    @patch("agent_orchestration.coordinator.ensure_fleet", return_value=[30920])
    @patch("agent_orchestration.coordinator.fleet_status", return_value={30920: "healthy"})
    def test_string_tasks(self, mock_status, mock_fleet, mock_run):
        mock_run.return_value = AgentResult(
            task_id="task-1", success=True, output="done", elapsed_seconds=1.0,
        )
        result = dispatch(["do something"], browsers=False, max_agents=1)
        assert result.succeeded == 1

    @patch("agent_orchestration.coordinator.run_agent")
    @patch("agent_orchestration.coordinator.ensure_fleet", return_value=[30920])
    @patch("agent_orchestration.coordinator.fleet_status", return_value={30920: "healthy"})
    def test_dict_tasks(self, mock_status, mock_fleet, mock_run):
        mock_run.return_value = AgentResult(
            task_id="my-task", success=True, output="done", elapsed_seconds=1.0,
        )
        result = dispatch([{"prompt": "do something", "id": "my-task"}], browsers=False, max_agents=1)
        assert result.succeeded == 1

    @patch("agent_orchestration.coordinator.run_agent")
    def test_task_definition_objects(self, mock_run):
        mock_run.return_value = AgentResult(
            task_id="td-1", success=True, output="done", elapsed_seconds=1.0,
        )
        result = dispatch(
            [TaskDefinition(prompt="do something", id="td-1")],
            browsers=False, max_agents=1,
        )
        assert result.succeeded == 1


class TestBrowserPortAssignment:
    """Test that dispatch assigns browser ports correctly."""

    @patch("agent_orchestration.coordinator.run_agent")
    @patch("agent_orchestration.coordinator.ensure_fleet", return_value=[30920, 30921, 30923])
    @patch("agent_orchestration.coordinator.fleet_status", return_value={30920: "healthy", 30921: "healthy", 30923: "healthy"})
    def test_three_tasks_get_three_ports(self, mock_status, mock_fleet, mock_run):
        mock_run.return_value = AgentResult(
            task_id="t", success=True, output="ok", elapsed_seconds=1.0,
        )
        dispatch(["a", "b", "c"], browsers=True, max_agents=3)
        calls = mock_run.call_args_list
        ports = {c.kwargs.get("cdp_port") for c in calls}
        assert ports == {30920, 30921, 30923}

    @patch("agent_orchestration.coordinator.run_agent")
    def test_no_browsers_no_ports(self, mock_run):
        mock_run.return_value = AgentResult(
            task_id="t", success=True, output="ok", elapsed_seconds=1.0,
        )
        dispatch(["a"], browsers=False, max_agents=1)
        calls = mock_run.call_args_list
        assert calls[0].kwargs.get("cdp_port") is None


class TestBlockerEscalation:
    """Test that blocked agents trigger the on_blocked callback."""

    @patch("agent_orchestration.coordinator.run_agent")
    def test_blocked_agent_triggers_callback(self, mock_run):
        mock_run.return_value = AgentResult(
            task_id="t1", success=False, output="[BLOCKED] MFA",
            elapsed_seconds=5.0, blocked=True, block_reason="MFA",
        )
        callback_called = []
        dispatch(
            ["task"], browsers=False, max_agents=1,
            on_blocked=lambda r: callback_called.append(r.block_reason),
        )
        assert "MFA" in callback_called

    @patch("agent_orchestration.coordinator.run_agent")
    def test_blocked_counted_in_result(self, mock_run):
        mock_run.return_value = AgentResult(
            task_id="t1", success=False, output="stuck",
            elapsed_seconds=5.0, blocked=True, block_reason="captcha",
        )
        result = dispatch(["task"], browsers=False, max_agents=1)
        assert result.blocked == 1
        assert result.all_succeeded is False


class TestValidation:
    """Test supervisor validation callback."""

    @patch("agent_orchestration.coordinator.run_agent")
    def test_validator_rejects_result(self, mock_run):
        mock_run.return_value = AgentResult(
            task_id="t1", success=True, output="only 2 items found",
            elapsed_seconds=5.0,
        )
        result = dispatch(
            ["build cart"], browsers=False, max_agents=1,
            validate=lambda r: "5 items" in r.output,  # requires 5 items
        )
        assert result.succeeded == 0
        assert result.failed == 1

    @patch("agent_orchestration.coordinator.run_agent")
    def test_validator_accepts_result(self, mock_run):
        mock_run.return_value = AgentResult(
            task_id="t1", success=True, output="found all 5 items in cart",
            elapsed_seconds=5.0,
        )
        result = dispatch(
            ["build cart"], browsers=False, max_agents=1,
            validate=lambda r: "5 items" in r.output,
        )
        assert result.succeeded == 1


class TestOrchestrationResult:
    """Test result aggregation."""

    @patch("agent_orchestration.coordinator.run_agent")
    def test_mixed_results(self, mock_run):
        call_count = 0
        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return AgentResult(task_id="t1", success=True, output="ok", elapsed_seconds=1.0)
            else:
                return AgentResult(task_id="t2", success=False, output="error", elapsed_seconds=2.0)
        
        mock_run.side_effect = side_effect
        result = dispatch(["a", "b"], browsers=False, max_agents=2)
        assert result.succeeded == 1
        assert result.failed == 1
        assert result.all_succeeded is False
        assert len(result.results) == 2
