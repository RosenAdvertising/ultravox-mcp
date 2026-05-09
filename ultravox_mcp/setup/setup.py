#!/usr/bin/env python3
"""
ultravox-mcp-setup — interactive setup wizard.

Prompts for the Ultravox API key, saves it to ~/.ultravox-mcp/.env,
then runs a verification check against the API.
"""

import os
import sys
from pathlib import Path


CONFIG_DIR = Path.home() / ".ultravox-mcp"
ENV_FILE = CONFIG_DIR / ".env"


def _save_api_key(api_key: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text(f"ULTRAVOX_API_KEY={api_key}\n")
    ENV_FILE.chmod(0o600)
    print(f"API key saved to {ENV_FILE}")


def main() -> None:
    print("=" * 60)
    print("ultravox-mcp setup")
    print("=" * 60)
    print()
    print("Find your API key at: app.ultravox.ai → Account → API Keys")
    print()

    # Check for existing key
    existing = None
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("ULTRAVOX_API_KEY="):
                existing = line.split("=", 1)[1].strip()
                break

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

    _save_api_key(api_key)

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
