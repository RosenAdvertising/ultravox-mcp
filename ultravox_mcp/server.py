#!/usr/bin/env python3
"""
ultravox-mcp — FastMCP server for the Ultravox voice AI REST API.

SCOPE NOTE: This server covers the Ultravox REST layer only.
  - create_call returns a joinUrl.
  - Joining a call (real-time audio/WebSocket) is handled by the
    Ultravox client SDK and is out of scope for this MCP server.
"""

from mcp.server.fastmcp import FastMCP

from .client import UltravoxClient

mcp = FastMCP(
    "ultravox-mcp",
    instructions=(
        "MCP server for Ultravox voice AI — REST layer only. "
        "Use create_call to provision a call; the response includes a joinUrl "
        "that you or the end-user must connect to via the Ultravox WebSocket/SDK. "
        "Real-time audio streaming is outside this MCP's scope."
    ),
)


def _client() -> UltravoxClient:
    """Instantiate a client, raising a clear error if auth is missing."""
    return UltravoxClient()


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


@mcp.tool()
def get_account() -> dict:
    """Return account details for the authenticated Ultravox user."""
    return _client().get_account()


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


@mcp.tool()
def list_calls(page_size: int = 25, cursor: str = "") -> dict:
    """
    List Ultravox calls.

    page_size: Number of results per page (default 25).
    cursor: Pagination cursor from a previous response. Leave blank for the first page.
    """
    return _client().list_calls(page_size=page_size, cursor=cursor)


@mcp.tool()
def get_call(call_id: str) -> dict:
    """Get details for a single Ultravox call by its ID."""
    return _client().get_call(call_id)


@mcp.tool()
def create_call(
    system_prompt: str,
    voice: str = "terrence",
    temperature: float = 0.7,
    first_speaker: str = "FIRST_SPEAKER_AGENT",
    max_duration: str = "600s",
) -> dict:
    """
    Create a new Ultravox call. Returns a joinUrl — use your WebSocket/SDK client
    to join. The MCP handles REST only; real-time audio is out of scope.

    system_prompt: Instructions for the AI agent in this call.
    voice: Voice ID to use (default: terrence). See list_voices for options.
    temperature: Sampling temperature 0.0–1.0 (default 0.7).
    first_speaker: Who speaks first — FIRST_SPEAKER_AGENT or FIRST_SPEAKER_USER.
    max_duration: Maximum call duration, e.g. "600s" (default: 600s / 10 min).
    """
    return _client().create_call(
        system_prompt=system_prompt,
        voice=voice,
        temperature=temperature,
        first_speaker=first_speaker,
        max_duration=max_duration,
    )


@mcp.tool()
def delete_call(call_id: str) -> dict:
    """Delete an Ultravox call by its ID."""
    return _client().delete_call(call_id)


@mcp.tool()
def list_call_messages(call_id: str, page_size: int = 50) -> dict:
    """
    Retrieve the message transcript for a completed or active Ultravox call.

    call_id: The call ID to fetch messages for.
    page_size: Number of messages per page (default 50).
    """
    return _client().list_call_messages(call_id=call_id, page_size=page_size)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tools(page_size: int = 25) -> dict:
    """List all Ultravox tools configured for this account."""
    return _client().list_tools(page_size=page_size)


@mcp.tool()
def get_tool(tool_id: str) -> dict:
    """Get details for a single Ultravox tool by its ID."""
    return _client().get_tool(tool_id)


@mcp.tool()
def create_tool(
    name: str,
    description: str,
    parameters_schema: dict,
    http_config: dict,
) -> dict:
    """
    Create a new Ultravox tool.

    name: Short identifier for the tool.
    description: What the tool does (shown to the AI agent).
    parameters_schema: JSON Schema object describing the tool's input parameters.
    http_config: HTTP backend config object.
    """
    return _client().create_tool(
        name=name,
        description=description,
        parameters_schema=parameters_schema,
        http_config=http_config,
    )


@mcp.tool()
def delete_tool(tool_id: str) -> dict:
    """Delete an Ultravox tool by its ID."""
    return _client().delete_tool(tool_id)


# ---------------------------------------------------------------------------
# Voices
# ---------------------------------------------------------------------------


@mcp.tool()
def list_voices(page_size: int = 25) -> dict:
    """List available Ultravox voices."""
    return _client().list_voices(page_size=page_size)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    mcp.run()


if __name__ == "__main__":
    main()
