"""Consolidated secret store — macOS Keychain backend.

All agent credentials accessed through one interface.
macOS uses `security` CLI for Keychain operations.
Secrets are stored under service name 'agent-orch' with the secret name as account.
"""

import json
import subprocess
import sys

SERVICE = "agent-orch"


def _run_security(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a macOS `security` CLI command."""
    cmd = ["security"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def get_secret(name: str) -> str | None:
    """Retrieve a secret by name from macOS Keychain.
    
    Returns the secret value, or None if not found.
    """
    result = _run_security(
        "find-generic-password", "-s", SERVICE, "-a", name, "-w",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def set_secret(name: str, value: str) -> None:
    """Store a secret in macOS Keychain. Overwrites if exists."""
    # -U flag = update if exists
    _run_security(
        "add-generic-password", "-s", SERVICE, "-a", name, "-w", value, "-U",
    )


def delete_secret(name: str) -> bool:
    """Delete a secret from Keychain. Returns True if deleted, False if not found."""
    result = _run_security(
        "delete-generic-password", "-s", SERVICE, "-a", name,
        check=False,
    )
    return result.returncode == 0


def list_secrets() -> list[str]:
    """List all secret names stored under the agent-orch service."""
    result = _run_security("dump-keychain", check=False)
    if result.returncode != 0:
        return []
    
    names = []
    in_agent_orch = False
    for line in result.stdout.split("\n"):
        if f'"svce"<blob>="{SERVICE}"' in line:
            in_agent_orch = True
        elif in_agent_orch and '"acct"<blob>=' in line:
            # Extract account name between quotes
            start = line.index('"acct"<blob>="') + len('"acct"<blob>="')
            end = line.index('"', start)
            names.append(line[start:end])
            in_agent_orch = False
        elif line.startswith("keychain:") or line.startswith("class:"):
            in_agent_orch = False
    
    return sorted(set(names))


def import_from_lp(tile_name: str, secret_name: str | None = None) -> str:
    """Import a credential from LastPass vault into Keychain.
    
    Requires LP vault to be open in a browser tab on port 9222.
    Uses lp_vault.py from llm-config for extraction.
    
    Args:
        tile_name: LP tile name (e.g., 'chase', 'fidelity') or tile ID
        secret_name: Name to store under in Keychain (defaults to tile_name)
    """
    import os
    # Try to import lp_vault from llm-config
    lp_vault_path = os.path.expanduser("~/working/llm-config/copilot-tools/lib")
    sys.path.insert(0, lp_vault_path)
    
    try:
        from lp_vault import get_credential_by_name
        creds = get_credential_by_name(tile_name)
        if not creds or "error" in creds:
            raise RuntimeError(f"LP vault extraction failed: {creds}")
        
        store_name = secret_name or tile_name
        # Store as JSON with username + password
        set_secret(store_name, json.dumps(creds))
        return f"Imported {tile_name} → Keychain as '{store_name}'"
    finally:
        sys.path.pop(0)


def main():
    """CLI interface for secret store."""
    import argparse
    parser = argparse.ArgumentParser(description="Agent secret store (macOS Keychain)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List stored secret names")

    get_p = sub.add_parser("get", help="Get a secret by name")
    get_p.add_argument("name")

    set_p = sub.add_parser("set", help="Store a secret")
    set_p.add_argument("name")
    set_p.add_argument("value")

    del_p = sub.add_parser("delete", help="Delete a secret")
    del_p.add_argument("name")

    imp_p = sub.add_parser("import-lp", help="Import from LastPass vault → Keychain")
    imp_p.add_argument("tile_name", help="LP tile name or ID")
    imp_p.add_argument("--as", dest="store_name", help="Store under this name instead")

    args = parser.parse_args()

    if args.command == "list":
        names = list_secrets()
        for n in names:
            print(n)
        if not names:
            print("(no secrets stored)")
    elif args.command == "get":
        val = get_secret(args.name)
        if val is None:
            print(json.dumps({"error": f"Secret '{args.name}' not found"}))
            sys.exit(1)
        print(val)
    elif args.command == "set":
        set_secret(args.name, args.value)
        print(f"Stored '{args.name}'")
    elif args.command == "delete":
        if delete_secret(args.name):
            print(f"Deleted '{args.name}'")
        else:
            print(f"Not found: '{args.name}'")
            sys.exit(1)
    elif args.command == "import-lp":
        result = import_from_lp(args.tile_name, args.store_name)
        print(result)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
