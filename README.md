# ultravox-mcp

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B.svg)](https://opensource.org/licenses/MIT)
[![11 tools](https://img.shields.io/badge/tools-11-22C55E.svg)](https://github.com/RosenAdvertising/ultravox-mcp)
[![MCP](https://img.shields.io/badge/MCP-compatible-7C3AED.svg)](https://modelcontextprotocol.io)
[![Ultravox](https://img.shields.io/badge/Ultravox-Voice%20AI-0EA5E9.svg)](https://ultravox.ai)

MCP server for the [Ultravox](https://ultravox.ai) voice AI platform — REST layer only.

## Scope

This server covers the **Ultravox REST API**:

- Create, list, get, and delete calls
- Fetch call transcripts (messages)
- Manage Ultravox tools (list, get, create, delete)
- List available voices
- Get account details

**Out of scope:** Real-time audio streaming. `create_call` returns a `joinUrl` — you must connect to it using the [Ultravox client SDK](https://docs.ultravox.ai) or a WebSocket client. The MCP server has no role in the live call.

## Installation

```bash
pip install -e /path/to/ultravox-mcp
```

## Setup

```bash
ultravox-mcp-setup
```

Prompts for your API key (find it at `app.ultravox.ai → Account → API Keys`), saves it to `~/.ultravox-mcp/.env`, and verifies the connection.

To verify an existing key without re-running setup:

```bash
ultravox-mcp-verify
```

## Claude Desktop config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ultravox": {
      "command": "ultravox-mcp"
    }
  }
}
```

## Tools (11)

| Tool                 | Description                                              |
| -------------------- | -------------------------------------------------------- |
| `get_account`        | Account details for the authenticated user               |
| `list_calls`         | Paginated list of calls                                  |
| `get_call`           | Single call by ID                                        |
| `create_call`        | Provision a new call — returns `joinUrl`                 |
| `delete_call`        | Delete a call                                            |
| `list_call_messages` | Transcript for a call                                    |
| `list_tools`         | List configured Ultravox tools                           |
| `get_tool`           | Single tool by ID                                        |
| `create_tool`        | Create a new tool (params + HTTP config as JSON strings) |
| `delete_tool`        | Delete a tool                                            |
| `list_voices`        | Available voices                                         |

## Auth

API key is sent as `X-API-Key: {ULTRAVOX_API_KEY}` on every request.

Config is loaded from `~/.ultravox-mcp/.env` at startup, falling back to the `ULTRAVOX_API_KEY` environment variable.

## Call flow

```text
MCP create_call  →  Ultravox REST  →  { callId, joinUrl, ... }
                                              |
                              joinUrl (wss://...) passed to Ultravox SDK
                                              |
                                     live audio session
```

The MCP handles steps 1–3. Everything after the `joinUrl` is your application's responsibility.
