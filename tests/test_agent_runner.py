"""Tests for agent runner."""

import os
import pytest
from unittest.mock import patch, MagicMock

from agent_orchestration.agent_runner import run_agent, AgentResult, _find_copilot


class TestAgentResultDefaults:
    """Test AgentResult dataclass."""

    def test_timestamp_auto_populated(self):
        r = AgentResult(task_id="t1", success=True, output="ok", elapsed_seconds=1.0)
        assert r.timestamp != ""
        assert "T" in r.timestamp  # ISO format

    def test_blocked_defaults_false(self):
        r = AgentResult(task_id="t1", success=True, output="ok", elapsed_seconds=1.0)
        assert r.blocked is False
        assert r.block_reason == ""


class TestRunAgentBrowserInjection:
    """Test that browser port is correctly injected."""

    @patch("agent_orchestration.agent_runner._find_copilot", return_value="/usr/bin/copilot")
    @patch("subprocess.run")
    def test_cdp_port_in_prompt(self, mock_run, mock_find):
        mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")
        run_agent("t1", "Search Amazon", cdp_port=30920)
        cmd = mock_run.call_args[0][0]
        prompt = cmd[cmd.index("-p") + 1]
        assert "30920" in prompt
        assert "Search Amazon" in prompt

    @patch("agent_orchestration.agent_runner._find_copilot", return_value="/usr/bin/copilot")
    @patch("subprocess.run")
    def test_cdp_port_in_env(self, mock_run, mock_find):
        mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")
        run_agent("t1", "task", cdp_port=30921)
        env = mock_run.call_args[1]["env"]
        assert env["CDP_PORT"] == "30921"

    @patch("agent_orchestration.agent_runner._find_copilot", return_value="/usr/bin/copilot")
    @patch("subprocess.run")
    def test_no_cdp_port_no_injection(self, mock_run, mock_find):
        mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")
        run_agent("t1", "task", cdp_port=None)
        env = mock_run.call_args[1]["env"]
        assert "CDP_PORT" not in env
        prompt = mock_run.call_args[0][0][mock_run.call_args[0][0].index("-p") + 1]
        assert "dedicated browser" not in prompt


class TestRunAgentBlockerDetection:
    """Test that [BLOCKED] markers are detected."""

    @patch("agent_orchestration.agent_runner._find_copilot", return_value="/usr/bin/copilot")
    @patch("subprocess.run")
    def test_blocked_signal_detected(self, mock_run, mock_find):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="working...\n[BLOCKED] MFA required on Chase\nstuck", stderr=""
        )
        result = run_agent("t1", "task")
        assert result.blocked is True
        assert "MFA" in result.block_reason
        assert result.success is False

    @patch("agent_orchestration.agent_runner._find_copilot", return_value="/usr/bin/copilot")
    @patch("subprocess.run")
    def test_no_blocker_means_success(self, mock_run, mock_find):
        mock_run.return_value = MagicMock(returncode=0, stdout="completed fine", stderr="")
        result = run_agent("t1", "task")
        assert result.blocked is False
        assert result.success is True


class TestRunAgentFailures:
    """Test error handling."""

    def test_copilot_not_found(self):
        with patch("agent_orchestration.agent_runner._find_copilot", return_value=None):
            result = run_agent("t1", "task")
            assert result.success is False
            assert "not found" in result.output

    @patch("agent_orchestration.agent_runner._find_copilot", return_value="/usr/bin/copilot")
    @patch("subprocess.run")
    def test_nonzero_exit_is_failure(self, mock_run, mock_find):
        mock_run.return_value = MagicMock(returncode=1, stdout="error", stderr="crash")
        result = run_agent("t1", "task")
        assert result.success is False

    @patch("agent_orchestration.agent_runner._find_copilot", return_value="/usr/bin/copilot")
    @patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired(cmd="copilot", timeout=10))
    def test_timeout_returns_failure(self, mock_run, mock_find):
        result = run_agent("t1", "task", timeout=10)
        assert result.success is False
        assert "Timeout" in result.output
