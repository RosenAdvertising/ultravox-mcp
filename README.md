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

Prompts for your API key (find it at `app.ultravox.ai → Account → API Keys`), saves it to your OS keyring (see [Auth](#auth)), and verifies the connection.

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

By default your API key (`ULTRAVOX_API_KEY`) is stored in your operating
system's native secret store via the cross-platform
[`keyring`](https://github.com/jaraco/keyring) library:

| OS      | Backend                                  |
| ------- | ---------------------------------------- |
| macOS   | Keychain                                 |
| Windows | Credential Manager                       |
| Linux   | Secret Service (GNOME Keyring / KWallet) |

The secret is saved under the service name `ultravox-mcp`. Nothing is written to
disk in clear text.

**File fallback.** On a host with no keyring backend (e.g. a headless Linux box
without Secret Service), or if you set `ULTRAVOX_MCP_USE_KEYRING=0`, the key
falls back to a `~/.ultravox-mcp/.env` file with `0600` permissions.

**Read order.** Values resolve in the order OS keyring → process environment →
`.env` file. So a rotated key in the keyring always wins, and a value exported in
your shell overrides the file fallback without touching the keyring.

**Pluggable backend.** `keyring` lets you point at any secret store. For example,
install [`keyrings.cryptfile`](https://pypi.org/project/keyrings.cryptfile/) for
an encrypted file backend, or a cloud backend, then select it with the standard
`PYTHON_KEYRING_BACKEND` environment variable or a `keyringrc.cfg`. See the
[keyring configuration docs](https://github.com/jaraco/keyring#configuring).

## Call flow

```text
MCP create_call  →  Ultravox REST  →  { callId, joinUrl, ... }
                                              |
                              joinUrl (wss://...) passed to Ultravox SDK
                                              |
                                     live audio session
```

The MCP handles steps 1–3. Everything after the `joinUrl` is your application's responsibility.
