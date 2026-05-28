#!/usr/bin/env python3
"""
Phase 0 data seed for the Ultravox developer account.

Creates 3 law-firm-representative Ultravox tools tagged [SEED].
These give smoke and write tiers a populated account to work against.

Note: Ultravox calls are ephemeral (joined via WebSocket) — they are NOT
seeded here. Seeded entities are tools only, which are persistent.

Prerequisites:
  1. Add Ultravox API key to ~/.ultravox-mcp/.env:
       echo "ULTRAVOX_API_KEY=$(op read 'op://Cowork/ultravox-dev-account/credential')" \
           >> ~/.ultravox-mcp/.env

  2. Run the seed:
       python tests/seed_data.py

Usage:
    python tests/seed_data.py            # create seed tools
    python tests/seed_data.py --reset    # wipe existing seed tools, then re-create
    python tests/seed_data.py --wipe     # wipe only (no re-create)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ultravox_mcp.client import UltravoxClient

SEED_TAG = "[SEED]"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_id(resp: dict, label: str) -> str | None:
    """Extract toolId from an Ultravox create_tool response; print status."""
    tool_id = resp.get("toolId")
    if not tool_id:
        err = resp.get("message") or resp.get("detail") or str(resp)[:200]
        print(f"  ✗  {label} — {err}", file=sys.stderr)
        return None
    print(f"  ✓  {label}  (id={tool_id})")
    return tool_id


def _list_all_tools(client: UltravoxClient) -> list[dict]:
    """Fetch all tools, following next-cursor pagination."""
    tools: list[dict] = []
    # Request a large page to minimize round trips on dev accounts.
    resp = client.list_tools(page_size=100)
    results = resp.get("results")
    if isinstance(results, list):
        tools.extend(results)
    # Follow "next" URL if the account has more than 100 tools.
    next_url = resp.get("next")
    while isinstance(next_url, str) and next_url:
        # Re-use the session directly for the raw next URL.
        raw = client.session.get(next_url)
        data: dict = raw.json() if raw.ok else {}
        batch = data.get("results")
        if isinstance(batch, list):
            tools.extend(batch)
        next_url = data.get("next")
    return tools


# ── Seed ──────────────────────────────────────────────────────────────────────


def seed(client: UltravoxClient) -> list[str]:
    """Create 3 law-firm voice tools tagged [SEED]. Returns list of created IDs."""
    created: list[str] = []
    print("\n── Tools ──────────────────────────────────────────")

    tools_to_create = [
        dict(
            name="seed_check_appointment_availability",
            description=(
                f"{SEED_TAG} Check whether a specific date and time is available "
                "for a client consultation at the law firm. Returns available slots."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format",
                    },
                    "attorney": {
                        "type": "string",
                        "description": "Attorney name or 'any' for first available",
                    },
                },
                "required": ["date"],
            },
            http_config={
                "baseUrlPattern": "https://httpbin.org/post",
                "httpMethod": "POST",
            },
        ),
        dict(
            name="seed_capture_intake_info",
            description=(
                f"{SEED_TAG} Capture client intake information during a voice call. "
                "Stores name, phone number, legal matter type, and urgency level."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "client_name": {
                        "type": "string",
                        "description": "Full name of the prospective client",
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "Best callback number",
                    },
                    "matter_type": {
                        "type": "string",
                        "enum": [
                            "personal_injury",
                            "family_law",
                            "criminal_defense",
                            "immigration",
                            "real_estate",
                            "other",
                        ],
                        "description": "Type of legal matter",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["immediate", "this_week", "flexible"],
                        "description": "How urgently the client needs help",
                    },
                },
                "required": ["client_name", "phone_number", "matter_type"],
            },
            http_config={
                "baseUrlPattern": "https://httpbin.org/post",
                "httpMethod": "POST",
            },
        ),
        dict(
            name="seed_lookup_case_status",
            description=(
                f"{SEED_TAG} Look up the current status of an existing case by "
                "client name or case number. Returns status, next steps, and attorney notes."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "case_number": {
                        "type": "string",
                        "description": "Case reference number (optional if client_name provided)",
                    },
                    "client_last_name": {
                        "type": "string",
                        "description": "Client last name for lookup",
                    },
                },
                "required": [],
            },
            http_config={
                "baseUrlPattern": "https://httpbin.org/get",
                "httpMethod": "GET",
            },
        ),
    ]

    for cfg in tools_to_create:
        try:
            resp = client.create_tool(**cfg)
            tool_id = _extract_id(resp, cfg["name"])
            if tool_id:
                created.append(tool_id)
        except Exception as exc:
            print(f"  ✗  {cfg['name']} — {exc}", file=sys.stderr)

    return created


# ── Wipe ──────────────────────────────────────────────────────────────────────


def wipe(client: UltravoxClient) -> None:
    """Delete all tools whose name or description contains [SEED]."""
    print(f"\nWiping '{SEED_TAG}' seed tools...")
    tools = _list_all_tools(client)
    deleted = 0
    for tool in tools:
        name = tool.get("name") or ""
        description = tool.get("description") or ""
        tool_id = tool.get("toolId") or tool.get("tool_id") or ""
        if SEED_TAG in name or SEED_TAG in description:
            if not tool_id:
                print(f"  ✗  no toolId for tool '{name}' — skipping", file=sys.stderr)
                continue
            try:
                client.delete_tool(tool_id)
                print(f"  deleted tool {tool_id} ({name})")
                deleted += 1
            except Exception as exc:
                print(
                    f"  ✗  failed to delete {tool_id} ({name}): {exc}", file=sys.stderr
                )
    if deleted == 0:
        print("  (no seed tools found)")
    print("Wipe complete.\n")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the Ultravox developer account with representative voice tools."
    )
    parser.add_argument(
        "--reset", action="store_true", help="Wipe seed tools then re-create"
    )
    parser.add_argument(
        "--wipe", action="store_true", help="Wipe seed tools only (no re-create)"
    )
    args = parser.parse_args()

    try:
        client = UltravoxClient()
    except RuntimeError as exc:
        print(f"Auth error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Identity check — confirm which account we're seeding.
    try:
        tools_resp = client.list_tools(page_size=1)
        count_val = tools_resp.get("count")
        results_val = tools_resp.get("results")
        tool_count: int = (
            count_val
            if isinstance(count_val, int)
            else len(results_val)
            if isinstance(results_val, list)
            else 0
        )
        print(f"Authenticated — Ultravox account ({tool_count} existing tool(s))")
    except Exception as exc:
        print(f"Auth check failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.wipe or args.reset:
        wipe(client)
    if not args.wipe:
        created = seed(client)
        print(f"\nSeed complete — {len(created)} tool(s) created.")
        print("\nNext step:")
        print(
            "  SEED_CONFIRMED=1 mcp-test-kit run --tier smoke --config tests/config.py"
        )


if __name__ == "__main__":
    main()
