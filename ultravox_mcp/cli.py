"""Credential-free help for the setup and verification console scripts."""

import sys


def _help(command: str, description: str) -> bool:
    if not any(arg in {"--help", "-h"} for arg in sys.argv[1:]):
        return False
    print(f"Usage: {command} [-h | --help]\n\n{description}\n")
    print("Options:\n  -h, --help  Show this help message and exit.")
    return True


def setup_main() -> None:
    """Show help before loading the interactive setup implementation."""
    if _help(
        "ultravox-mcp-setup", "Configure credentials interactively for ultravox-mcp."
    ):
        return
    from ultravox_mcp.setup.setup import main

    main()


def verify_main() -> None:
    """Show help before loading configuration or contacting the vendor."""
    if _help("ultravox-mcp-verify", "Verify the configured ultravox-mcp connection."):
        return
    from ultravox_mcp.setup.verify import main

    main()
