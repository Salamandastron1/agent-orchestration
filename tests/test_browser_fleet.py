"""Tests for browser fleet manager."""

import pytest
from unittest.mock import patch, MagicMock

from agent_orchestration.browser_fleet import (
    AGENT_BROWSER_PORTS, get_port, fleet_status, ensure_fleet,
)


class TestPortMapping:
    """Test port assignment is correct and stable."""

    def test_three_ports_configured(self):
        assert len(AGENT_BROWSER_PORTS) == 3

    def test_ports_are_unique(self):
        assert len(set(AGENT_BROWSER_PORTS)) == 3

    def test_expected_ports(self):
        assert AGENT_BROWSER_PORTS == [30920, 30921, 30923]

    def test_get_port_valid_indices(self):
        assert get_port(0) == 30920
        assert get_port(1) == 30921
        assert get_port(2) == 30923

    def test_get_port_out_of_range(self):
        assert get_port(3) is None
        assert get_port(-1) is None


class TestFleetStatus:
    """Test health checking."""

    @patch("agent_orchestration.browser_fleet.urllib.request.urlopen")
    def test_all_healthy(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"Browser": "Chrome/146"}'
        mock_urlopen.return_value = mock_resp

        status = fleet_status()
        assert all(v == "healthy" for v in status.values())
        assert len(status) == 3

    @patch("agent_orchestration.browser_fleet.urllib.request.urlopen")
    def test_one_unhealthy(self, mock_urlopen):
        call_count = 0
        def side_effect(url, timeout=5):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ConnectionError("refused")
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"Browser": "Chrome/146"}'
            return mock_resp

        mock_urlopen.side_effect = side_effect
        status = fleet_status()
        unhealthy_count = sum(1 for v in status.values() if v == "unhealthy")
        assert unhealthy_count == 1


class TestEnsureFleet:
    """Test fleet deployment."""

    @patch("subprocess.run")
    def test_calls_azbox_up(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        ports = ensure_fleet()
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "azbox" in cmd
        assert "agent-browsers" in cmd

    @patch("subprocess.run")
    def test_returns_correct_ports(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        ports = ensure_fleet(count=2)
        assert ports == [30920, 30921]
