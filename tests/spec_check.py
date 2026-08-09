"""Small CI guard for the repository's pinned MCP protocol revision."""

from __future__ import annotations

import argparse

from mcp.types.version import LATEST_PROTOCOL_VERSION

EXPECTED_MCP_PROTOCOL_VERSION = "2026-07-28"


def assert_mcp_protocol_version() -> None:
    """Fail when the installed SDK no longer targets the reviewed revision."""
    if LATEST_PROTOCOL_VERSION != EXPECTED_MCP_PROTOCOL_VERSION:
        raise AssertionError(
            "MCP protocol drift: expected "
            f"{EXPECTED_MCP_PROTOCOL_VERSION}, got {LATEST_PROTOCOL_VERSION}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mcp-only",
        action="store_true",
        help="check only the installed MCP protocol revision",
    )
    parser.parse_args()
    assert_mcp_protocol_version()
    print(f"MCP protocol: {EXPECTED_MCP_PROTOCOL_VERSION}")


if __name__ == "__main__":
    main()
