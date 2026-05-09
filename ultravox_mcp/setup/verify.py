#!/usr/bin/env python3
"""
ultravox-mcp-verify — verify that the configured API key works.

Tries GET /account first. If that endpoint returns 404/405 (not all
Ultravox tiers expose it), falls back to GET /calls?pageSize=1.
"""

import sys
from ultravox_mcp.client import UltravoxClient


def verify() -> bool:
    """
    Returns True if the API key is valid, False otherwise.
    Prints a human-readable status line.
    """
    try:
        client = UltravoxClient()
    except RuntimeError as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        return False

    # Try /account first
    try:
        data = client.get_account()
        display = str(data)[:80]
        if isinstance(data, dict):
            display = data.get("email") or data.get("id") or display
        print(f"  OK — account: {display}")
        return True
    except RuntimeError as exc:
        msg = str(exc)
        # 404/405 means the endpoint may not exist for this tier — try fallback
        if "404" in msg or "405" in msg or "400" in msg:
            pass
        else:
            print(f"  ERROR: {msg}", file=sys.stderr)
            return False

    # Fallback: list_calls
    try:
        data = client.list_calls(page_size=1)
        count = "?"
        if isinstance(data, dict):
            count = data.get("total") or data.get("count") or count
        print(f"  OK — API key valid (calls endpoint reachable, total={count})")
        return True
    except RuntimeError as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        return False


def main() -> None:
    print("Verifying Ultravox API key...")
    ok = verify()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
