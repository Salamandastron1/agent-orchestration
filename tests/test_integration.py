"""Integration tests — require live K8s browser fleet.

Run with: pytest tests/test_integration.py -v
Requires: azbox up --stack agent-browsers (3 Chromium pods)
"""

import json
import os
import sys
import pytest

# Import from the running cdp_client to verify real browser connectivity
CDP_CLIENT_DIR = os.path.expanduser("~/working/llm-config/mcp-servers/browser-cdp")

from agent_orchestration.browser_fleet import fleet_status, AGENT_BROWSER_PORTS
from agent_orchestration.secrets import get_secret, set_secret, delete_secret
from agent_orchestration.coordinator import dispatch


def _browsers_available() -> bool:
    """Check if K8s browsers are running."""
    status = fleet_status()
    return all(v == "healthy" for v in status.values())


@pytest.mark.skipif(
    not _browsers_available(),
    reason="K8s browser fleet not running (azbox up --stack agent-browsers)",
)
class TestBrowserIsolation:
    """Verify browsers are isolated — each agent sees its own state."""

    def test_all_three_browsers_respond(self):
        """All 3 CDP endpoints return valid version info."""
        import urllib.request
        for port in AGENT_BROWSER_PORTS:
            resp = urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=5)
            data = json.loads(resp.read())
            assert "Browser" in data

    def test_navigate_different_sites(self):
        """Navigate each browser to a different site, verify no cross-contamination."""
        sys.path.insert(0, CDP_CLIENT_DIR)
        
        sites = [
            (30920, "https://example.com", "Example Domain"),
            (30921, "https://httpbin.org/get", "origin"),
        ]
        
        for port, url, expected_text in sites:
            os.environ["CDP_PORT"] = str(port)
            if "cdp_client" in sys.modules:
                del sys.modules["cdp_client"]
            import cdp_client
            
            tabs = cdp_client.list_tabs()
            assert len(tabs) >= 1, f"No tabs on port {port}"
            
            cdp_client.navigate(tabs[0]["url"], url)
            import time; time.sleep(2)
            
            result = cdp_client.get_text(url)
            text = result.get("value", "") if isinstance(result, dict) else str(result)
            assert expected_text in text, f"Port {port}: expected '{expected_text}' in text, got: {text[:200]}"
        
        # Verify port 30920 still shows Example Domain (not contaminated by 30921)
        os.environ["CDP_PORT"] = "30920"
        if "cdp_client" in sys.modules:
            del sys.modules["cdp_client"]
        import cdp_client as cdp_check
        result = cdp_check.get_text("https://example.com")
        text = result.get("value", "") if isinstance(result, dict) else str(result)
        assert "Example Domain" in text, "Port 30920 was contaminated!"


class TestSecretStoreRoundTrip:
    """Verify secrets can be stored and retrieved via Keychain."""

    def test_credential_round_trip(self):
        """Store a JSON credential, retrieve it, clean up."""
        name = "_integration_test_cred"
        cred = json.dumps({"username": "test@example.com", "password": "integration-test-123"})
        try:
            set_secret(name, cred)
            retrieved = get_secret(name)
            assert retrieved is not None
            parsed = json.loads(retrieved)
            assert parsed["username"] == "test@example.com"
            assert parsed["password"] == "integration-test-123"
        finally:
            delete_secret(name)
        assert get_secret(name) is None
