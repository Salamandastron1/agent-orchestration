"""Tests for the consolidated secret store."""

import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock

from agent_orchestration.secrets import (
    get_secret, set_secret, delete_secret, list_secrets, SERVICE,
)


class TestGetSecret:
    """Test secret retrieval from Keychain."""

    @patch("agent_orchestration.secrets._run_security")
    def test_returns_value_when_found(self, mock_sec):
        mock_sec.return_value = MagicMock(returncode=0, stdout="my-password\n")
        assert get_secret("amazon") == "my-password"

    @patch("agent_orchestration.secrets._run_security")
    def test_returns_none_when_not_found(self, mock_sec):
        mock_sec.return_value = MagicMock(returncode=44, stdout="")
        assert get_secret("nonexistent") is None

    @patch("agent_orchestration.secrets._run_security")
    def test_calls_security_with_correct_args(self, mock_sec):
        mock_sec.return_value = MagicMock(returncode=0, stdout="val")
        get_secret("chase")
        mock_sec.assert_called_once_with(
            "find-generic-password", "-s", SERVICE, "-a", "chase", "-w",
            check=False,
        )


class TestSetSecret:
    """Test secret storage to Keychain."""

    @patch("agent_orchestration.secrets._run_security")
    def test_calls_add_with_update_flag(self, mock_sec):
        set_secret("costco", "pass123")
        mock_sec.assert_called_once_with(
            "add-generic-password", "-s", SERVICE, "-a", "costco", "-w", "pass123", "-U",
        )

    @patch("agent_orchestration.secrets._run_security")
    def test_stores_json_credential(self, mock_sec):
        """Can store structured credentials as JSON."""
        creds = json.dumps({"username": "user@example.com", "password": "secret"})
        set_secret("amazon", creds)
        mock_sec.assert_called_once()
        call_args = mock_sec.call_args[0]
        assert "-w" in call_args
        stored_val = call_args[call_args.index("-w") + 1]
        parsed = json.loads(stored_val)
        assert parsed["username"] == "user@example.com"


class TestDeleteSecret:
    """Test secret deletion from Keychain."""

    @patch("agent_orchestration.secrets._run_security")
    def test_returns_true_when_deleted(self, mock_sec):
        mock_sec.return_value = MagicMock(returncode=0)
        assert delete_secret("old-key") is True

    @patch("agent_orchestration.secrets._run_security")
    def test_returns_false_when_not_found(self, mock_sec):
        mock_sec.return_value = MagicMock(returncode=44)
        assert delete_secret("nonexistent") is False


class TestListSecrets:
    """Test listing all stored secret names."""

    @patch("agent_orchestration.secrets._run_security")
    def test_parses_keychain_dump(self, mock_sec):
        dump_output = '''keychain: "/Users/test/Library/Keychains/login.keychain-db"
class: "genp"
    0x00000007 <blob>="agent-orch"
    "svce"<blob>="agent-orch"
    "acct"<blob>="amazon"
class: "genp"
    0x00000007 <blob>="agent-orch"
    "svce"<blob>="agent-orch"
    "acct"<blob>="chase"
class: "genp"
    0x00000007 <blob>="other-service"
    "svce"<blob>="other-service"
    "acct"<blob>="should-not-appear"
'''
        mock_sec.return_value = MagicMock(returncode=0, stdout=dump_output)
        names = list_secrets()
        assert "amazon" in names
        assert "chase" in names
        assert "should-not-appear" not in names

    @patch("agent_orchestration.secrets._run_security")
    def test_returns_empty_on_failure(self, mock_sec):
        mock_sec.return_value = MagicMock(returncode=1, stdout="")
        assert list_secrets() == []

    @patch("agent_orchestration.secrets._run_security")
    def test_deduplicates_names(self, mock_sec):
        dump_output = '''class: "genp"
    "svce"<blob>="agent-orch"
    "acct"<blob>="amazon"
class: "genp"
    "svce"<blob>="agent-orch"
    "acct"<blob>="amazon"
'''
        mock_sec.return_value = MagicMock(returncode=0, stdout=dump_output)
        names = list_secrets()
        assert names.count("amazon") == 1


class TestRoundTrip:
    """Integration-style tests using real Keychain (marked for manual run)."""

    @pytest.mark.skipif(
        subprocess.run(["security", "help"], capture_output=True).returncode != 0,
        reason="macOS security CLI not available",
    )
    def test_set_get_delete_roundtrip(self):
        """Full round-trip: set → get → delete on real Keychain."""
        test_name = "_agent_orch_test_key_"
        test_value = "test-secret-value-12345"

        try:
            set_secret(test_name, test_value)
            retrieved = get_secret(test_name)
            assert retrieved == test_value
        finally:
            delete_secret(test_name)

        # Verify deletion
        assert get_secret(test_name) is None
