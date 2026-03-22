"""Browser fleet manager — K8s browser lifecycle via azbox."""

import subprocess
import urllib.request
import json

# Must match azbox/stacks/agent-browsers.yaml and azbox services
AGENT_BROWSER_PORTS = [30920, 30921, 30923]


def ensure_fleet(count: int = 3) -> list[int]:
    """Deploy the agent browser fleet via azbox. Idempotent.
    
    Returns list of CDP ports for the deployed browsers.
    """
    subprocess.run(
        ["azbox", "up", "--stack", "agent-browsers"],
        capture_output=True, text=True, timeout=120,
    )
    return AGENT_BROWSER_PORTS[:count]


def fleet_status() -> dict[int, str]:
    """Check health of each browser in the fleet.
    
    Returns {port: "healthy" | "unhealthy"} for each configured port.
    """
    status = {}
    for port in AGENT_BROWSER_PORTS:
        try:
            resp = urllib.request.urlopen(
                f"http://localhost:{port}/json/version", timeout=5
            )
            data = json.loads(resp.read())
            status[port] = "healthy"
        except Exception:
            status[port] = "unhealthy"
    return status


def get_port(agent_index: int) -> int | None:
    """Get the CDP port for a given agent index.
    
    Returns None if index is out of range.
    """
    if 0 <= agent_index < len(AGENT_BROWSER_PORTS):
        return AGENT_BROWSER_PORTS[agent_index]
    return None


def main():
    """CLI for browser fleet management."""
    import argparse
    parser = argparse.ArgumentParser(description="Agent browser fleet manager")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("up", help="Deploy browser fleet")
    sub.add_parser("status", help="Check fleet health")

    args = parser.parse_args()

    if args.command == "up":
        ports = ensure_fleet()
        print(f"Fleet deployed: ports {ports}")
    elif args.command == "status":
        status = fleet_status()
        for port, health in status.items():
            print(f"  Port {port}: {health}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
