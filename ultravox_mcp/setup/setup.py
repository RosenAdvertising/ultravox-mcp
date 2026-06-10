#!/usr/bin/env python3
"""
ultravox-mcp-setup — interactive setup wizard.

Prompts for the Ultravox API key, saves it to the OS keyring (or a
0600 ~/.ultravox-mcp/.env file as a fallback), then runs a verification
check against the API.
"""

import os
import sys

from ultravox_mcp import credentials


def main() -> None:
    print("=" * 60)
    print("ultravox-mcp setup")
    print("=" * 60)
    print()
    print("Find your API key at: app.ultravox.ai → Account → API Keys")
    print()

    # Check for an existing key in the configured store (keyring or .env).
    existing = credentials.get_secret("ULTRAVOX_API_KEY")

    if existing:
        masked = existing[:6] + "..." + existing[-4:] if len(existing) > 10 else "****"
        print(f"Existing API key found: {masked}")
        overwrite = input("Overwrite? [y/N] ").strip().lower()
        if overwrite != "y":
            print("Keeping existing key.")
            _run_verify()
            return

    api_key = input("Paste your Ultravox API key: ").strip()
    if not api_key:
        print("No key entered. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Persist through the pluggable store (OS keyring by default).
    backend = credentials.set_secret("ULTRAVOX_API_KEY", api_key)
    if backend == "keyring":
        print(f"API key saved to the OS keyring ({credentials.storage_backend()}).")
    else:
        print(f"API key saved to {credentials.ENV_FILE} (0600).")

    # Inject into current process env so verify can use it immediately
    os.environ["ULTRAVOX_API_KEY"] = api_key

    _run_verify()


def _run_verify() -> None:
    print()
    print("Verifying API key...")
    from ultravox_mcp.setup.verify import verify

    ok = verify()
    if ok:
        print()
        print("Setup complete. Add this to your Claude Desktop MCP config:")
        print()
        print('  "ultravox": {')
        print('    "command": "ultravox-mcp"')
        print("  }")
        print()
    else:
        print()
        print("Verification failed. Check your API key and try again.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
