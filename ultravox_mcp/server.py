"""
ultravox-mcp — MCP server for the Ultravox voice AI REST API.

SCOPE NOTE: This server covers the Ultravox REST layer only.
  - create_call returns a joinUrl.
  - Joining a call (real-time audio/WebSocket) is handled by the
    Ultravox client SDK and is out of scope for this MCP server.
"""

import json
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .client import UltravoxClient

PageSize = Annotated[int, Field(ge=1, le=200)]

mcp = MCPServer(
    "ultravox-mcp",
    version="0.1.0",
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
def get_account() -> dict[str, Any]:
    """Return account details for the authenticated Ultravox user."""
    return _client().get_account()


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


@mcp.tool()
def list_calls(page_size: PageSize = 25, cursor: str = "") -> dict[str, Any]:
    """
    List Ultravox calls.

    page_size: Number of results to return (1-200, default 25).
    cursor: Pagination cursor from a previous response. Leave blank for the first page.
    """
    return _client().list_calls(page_size=page_size, cursor=cursor)


@mcp.tool()
def get_call(call_id: str) -> dict[str, Any]:
    """Get details for a single Ultravox call by its ID."""
    return _client().get_call(call_id)


@mcp.tool()
def create_call(
    system_prompt: str,
    voice: str = "terrence",
    temperature: float = 0.7,
    first_speaker: str = "FIRST_SPEAKER_AGENT",
    max_duration: str = "600s",
) -> dict[str, Any]:
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
def delete_call(call_id: str) -> dict[str, Any]:
    """Delete an Ultravox call by its ID."""
    return _client().delete_call(call_id)


@mcp.tool()
def list_call_messages(call_id: str, page_size: PageSize = 50) -> dict[str, Any]:
    """
    Retrieve the message transcript for a completed or active Ultravox call.

    call_id: The call ID to fetch messages for.
    page_size: Number of messages to return (1-200, default 50).
    """
    return _client().list_call_messages(call_id=call_id, page_size=page_size)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tools(page_size: PageSize = 25) -> dict[str, Any]:
    """List all Ultravox tools configured for this account."""
    return _client().list_tools(page_size=page_size)


@mcp.tool()
def get_tool(tool_id: str) -> dict[str, Any]:
    """Get details for a single Ultravox tool by its ID."""
    return _client().get_tool(tool_id)


@mcp.tool()
def create_tool(
    name: str,
    description: str,
    parameters_schema: dict[str, Any],
    http_config: dict[str, Any],
) -> dict[str, Any]:
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
def delete_tool(tool_id: str) -> dict[str, Any]:
    """Delete an Ultravox tool by its ID."""
    return _client().delete_tool(tool_id)


# ---------------------------------------------------------------------------
# Voices
# ---------------------------------------------------------------------------


@mcp.tool()
def list_voices(page_size: PageSize = 25) -> dict[str, Any]:
    """List available Ultravox voices."""
    return _client().list_voices(page_size=page_size)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("ultravox://voices", mime_type="application/json")
def voices_resource() -> str:
    """Available Ultravox voices — read-only reference data for call provisioning."""
    return json.dumps(_client().list_voices(page_size=100), indent=2)


@mcp.resource("ultravox://tools", mime_type="application/json")
def tools_resource() -> str:
    """All Ultravox tools configured for this account — read-only reference data."""
    return json.dumps(_client().list_tools(page_size=100), indent=2)


@mcp.resource("ultravox://security-notes", mime_type="text/markdown")
def security_notes_resource() -> str:
    """Security posture and injection-risk guidance for the Ultravox MCP server."""
    return """# Ultravox MCP — Security Notes

## Scope boundary

This MCP server covers the Ultravox REST layer only. `create_call` provisions a call
and returns a `joinUrl` — real-time audio streaming via WebSocket/SDK is handled
outside this server. The security considerations below apply to the REST provisioning
layer and to the call data (transcripts/messages) this server can retrieve.

## System prompt injection surface

The `system_prompt` field passed to `create_call` becomes the live instruction set for
a voice AI agent that speaks directly to real callers (law-firm intake, after-hours
answering). Any third-party or caller-supplied content injected into `system_prompt`
is an **injection surface** — an adversary who can influence the prompt controls the
agent's behaviour on live calls.

Mitigations:
- Treat all caller-supplied input as untrusted; never echo it into `system_prompt`
  without sanitisation.
- Treat `system_prompt` changes as code deploys — review before executing.
- Restrict which MCP clients or agents can call `create_call`.

## Tool definitions as an injection surface

Tools registered via `create_tool` include a `description` field shown to the AI agent.
Malicious descriptions could manipulate agent behaviour. Only create tools from
controlled, internal sources — never from user-supplied text without review.

## PII and call transcripts

Legal intake calls may carry protected personal information. Messages retrieved via
`list_call_messages` should be:
- Stored only in systems that meet the firm's data-retention policy.
- Not forwarded to general-purpose logging pipelines without redaction.
- Treated as potentially attorney-client privileged.

## API key scope

`ULTRAVOX_API_KEY` grants full account access. Store it in the OS keyring or a
secrets manager — never in source code, `.env` files committed to version control,
or plain-text logs.

## joinUrl lifecycle

The `joinUrl` returned by `create_call` is a one-time credential. Do not log it,
embed it in URLs, or share it beyond the intended SDK client. Treat it with the same
care as a short-lived auth token.
"""


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt()
def provision_intake_call(firm_name: str = "[Law Firm Name]") -> str:
    """Guide to provision an Ultravox call for law-firm off-hours intake using create_call."""
    return f"""You are provisioning an Ultravox voice call for after-hours legal intake at {firm_name}.
This server covers the REST layer only — after create_call returns a joinUrl, the
WebSocket/SDK client must connect separately.

Steps:

1. **Choose a voice** — call list_voices and pick a voice appropriate for professional
   legal intake (clear, calm, US-English preferred unless the firm serves another market).
   Note the voice ID for use in create_call.

2. **Define the intake prompt** — the system_prompt should include:
   - Firm name and after-hours context ("Our office is closed...")
   - Instructions to collect: caller's full name, callback number, type of legal matter,
     urgency level (emergency / routine), and preferred callback time
   - A closing statement confirming a callback within one business day
   - Escalation instruction for emergencies (e.g. domestic violence, custody crisis)
   Security: do not include internal escalation contact details, pricing, or
   confidential firm procedures in the prompt — this text reaches callers.

3. **Provision the call** — call create_call with:
   - system_prompt: the intake prompt drafted above
   - voice: the voice ID chosen in step 1
   - first_speaker: FIRST_SPEAKER_AGENT (agent greets first)
   - max_duration: "900s" (15 min — sufficient for intake, prevents runaway calls)
   - temperature: 0.4 (lower = more consistent, appropriate for intake)

4. **Return the joinUrl** — hand it to the WebSocket/SDK client or telephony bridge
   that will connect the inbound call. The MCP's role ends here.

5. **After the call** — use list_calls and list_call_messages to retrieve the transcript
   and verify intake fields were captured correctly."""


@mcp.prompt()
def triage_call_transcripts() -> str:
    """Review recent Ultravox call transcripts and classify for legal intake follow-up."""
    return """Review recent Ultravox call transcripts and triage for legal intake follow-up.

1. Call list_calls (page_size=50) to fetch recent calls.
2. For each call, call get_call to check duration and end reason.
3. For calls with duration > 30 seconds, call list_call_messages to read the transcript.
4. Classify each call:
   - HOT LEAD: caller described a legal matter and left name + callback number
   - CALLBACK NEEDED: caller was cut off, unclear outcome, or expressed urgency
   - INFO ONLY: general question, no intake action needed
   - WRONG NUMBER / SPAM: irrelevant

5. Output a triage table ordered by priority (HOT LEAD first):
   call_id | duration | classification | key detail (case type / caller name if given)

6. Flag any call where PII was captured (name + phone number) — those transcripts must
   be handled according to the firm's data-retention policy and should not be forwarded
   to unvetted systems.

7. For HOT LEAD and CALLBACK NEEDED calls, note whether the agent successfully collected
   all required intake fields. If fields are missing, flag the system_prompt for review."""


@mcp.prompt()
def review_tool_inventory() -> str:
    """Audit the Ultravox tool registry and identify unused or outdated tool definitions."""
    return """Audit the Ultravox tool registry for the current account.

1. Call list_tools to enumerate all configured tools.
2. For each tool, call get_tool to retrieve its full definition:
   - name, description, HTTP config, parameters schema
3. For each tool assess:
   - Is the description accurate and free of ambiguous or manipulable language?
     (Tool descriptions are shown to the AI agent — they are an injection surface.)
   - Is the HTTP endpoint still valid and reachable?
   - Is the parameters schema minimal (only required fields exposed)?
4. Classify each tool:
   - ACTIVE / IN USE: tool is wired to an active call flow
   - ORPHANED: tool exists but no active calls reference it
   - NEEDS REVIEW: description is vague, overly broad, or potentially exploitable
5. Recommend: keep / update description / tighten schema / delete.
   For any NEEDS REVIEW tool, draft a revised description that is specific and
   scoped to the exact action the tool performs."""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
