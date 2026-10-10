# Ultravox MCP server

[![CI](https://github.com/RosenAdvertising/ultravox-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/RosenAdvertising/ultravox-mcp/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B.svg)](LICENSE)
[![MCP 2026-07-28](https://img.shields.io/badge/MCP-2026--07--28-7C3AED.svg)](https://modelcontextprotocol.io)
[![PyPI version](https://img.shields.io/pypi/v/ultravox-mcp.svg)](https://pypi.org/project/ultravox-mcp/)
[![11 tools](https://img.shields.io/badge/tools-11-22C55E.svg)](https://github.com/RosenAdvertising/ultravox-mcp)

Connect Claude and other MCP clients to Ultravox to create calls, read transcripts and manage tools.

Ultravox MCP server is a [Model Context Protocol](https://modelcontextprotocol.io) server for [Ultravox](https://ultravox.ai), the voice AI platform. It registers 11 tools that read and write Ultravox data. It runs over stdio by default, for desktop clients such as Claude Desktop, and offers an opt-in stateless Streamable HTTP mode that implements MCP specification 2026-07-28. Ultravox credentials stay on the machine that runs the server: they come from the setup command and your operating system's keyring, never from the client. It covers the Ultravox REST API only; joining a live call is handled by the Ultravox client SDK.

## Features

- **Calls**: create, list, look up and delete calls. `create_call` returns a `joinUrl` for the live session.
- **Transcripts**: fetch the messages of a call.
- **Tools**: list, look up, create and delete Ultravox tools.
- **Voices and account**: list available voices and read account details.

## Tools

The server registers 11 tools.

| Tool | What it does |
| --- | --- |
| `get_account` | Account details for the authenticated user. |
| `list_calls` | Paginated list of calls (`page_size` up to 200, optional `cursor`). |
| `get_call` | One call by ID. |
| `create_call` | Create a call and return its `joinUrl`. |
| `delete_call` | Delete a call. |
| `list_call_messages` | Transcript (messages) for a call. |
| `list_tools` | List configured Ultravox tools. |
| `get_tool` | One tool by ID. |
| `create_tool` | Create a tool from a name, description, parameters schema and HTTP config (`baseUrlPattern` and `httpMethod`). The destination host must be approved (see [Approved destination URLs](#approved-destination-urls)). |
| `delete_tool` | Delete a tool. |
| `list_voices` | Available voices. |

### Prompts and resources

The server also registers three prompts and three resources.

| Prompt | What it does |
| --- | --- |
| `provision_intake_call` | Guide to provision a call for off-hours legal intake with `create_call` (optional `firm_name`). |
| `triage_call_transcripts` | Reviews recent call transcripts and classifies them for intake follow-up. |
| `review_tool_inventory` | Audits the tool registry for unused or outdated tool definitions. |

| Resource | What it provides |
| --- | --- |
| `ultravox://voices` | Available voices, as JSON reference data. |
| `ultravox://tools` | Configured Ultravox tools, as JSON reference data. |
| `ultravox://security-notes` | Security notes for the server. |

## Requirements

- Python 3.10 or later.
- An Ultravox account with an API key (in Ultravox: **Account → API Keys**).
- An MCP client such as Claude Desktop.

## Installation

Install [uv](https://docs.astral.sh/uv/), then clone the repository and install its locked dependencies:

```bash
git clone https://github.com/RosenAdvertising/ultravox-mcp.git
cd ultravox-mcp
uv sync --locked
```

Releases are also published to PyPI: `pip install ultravox-mcp` installs version 0.2.0, which predates the HTTP mode described below. Install from source to use HTTP mode.

## Configuration

Run the setup command once. It prompts for your API key (in Ultravox: **Account → API Keys**), saves it (see [Credential storage](#credential-storage)) and verifies the connection:

```bash
uv run ultravox-mcp-setup
```

To verify an existing key without re-running setup:

```bash
uv run ultravox-mcp-verify
```

Restart the MCP server after changing the key. Server messages that say to run `ultravox-mcp-setup` mean `uv run ultravox-mcp-setup` from your clone.

The server sends the key as `X-API-Key` on every request. It reads these variables:

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `ULTRAVOX_API_KEY` | Yes (saved by setup) | Keyring, then `~/.ultravox-mcp/.env` | Ultravox API key. |
| `ULTRAVOX_MCP_USE_KEYRING` | No | `1` | Set to `0`, `false`, `no` or `off` to skip the operating system keyring and use the `.env` file. |
| `ULTRAVOX_ALLOWED_DESTINATION_HOSTS` | Only for `create_tool` | unset | Comma-separated approved hosts for `create_tool` destination URLs (see [Approved destination URLs](#approved-destination-urls)). |

### Credential storage

By default your API key (`ULTRAVOX_API_KEY`) is stored in your operating system's native secret store via the cross-platform [`keyring`](https://github.com/jaraco/keyring) library:

| OS | Backend |
| --- | --- |
| macOS | Keychain |
| Windows | Credential Manager |
| Linux | Secret Service (GNOME Keyring / KWallet) |

With an available keyring backend, the secret is saved under the service name `ultravox-mcp` without a clear-text file copy.

**File fallback.** On a host with no keyring backend (for example a headless Linux box without Secret Service), or if you set `ULTRAVOX_MCP_USE_KEYRING=0`, the key falls back to a `~/.ultravox-mcp/.env` file with `0600` permissions. On Windows, the file is stored in the user's profile and protected by Windows' default per-user access rules. On POSIX, files are created with `0600` permissions and writes fail closed if private permissions cannot be established.

**Read order.** A value set in the process environment is used as is. When `ULTRAVOX_API_KEY` is not set, the server reads the OS keyring, then the `~/.ultravox-mcp/.env` file, once at startup. A key exported in your shell therefore overrides the keyring and the file, and the keyring entry written by setup is used only while the variable is unset.

**Pluggable backend.** `keyring` lets you point at any secret store. For example, install [`keyrings.cryptfile`](https://pypi.org/project/keyrings.cryptfile/) for an encrypted file backend, or a cloud backend, then select it with the standard `PYTHON_KEYRING_BACKEND` environment variable or a `keyringrc.cfg`. See the [keyring configuration docs](https://github.com/jaraco/keyring#configuring).

## Usage with Claude Desktop

Add the server to Claude Desktop's configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "ultravox": {
      "command": "uv",
      "args": ["run", "--locked", "--directory", "/absolute/path/to/ultravox-mcp", "ultravox-mcp"]
    }
  }
}
```

Replace `/absolute/path/to/ultravox-mcp` with the path of your clone, then restart Claude Desktop. Any other stdio MCP client uses the same command and arguments.

## HTTP mode

Stdio is the default. Set `ULTRAVOX_MCP_TRANSPORT=streamable-http` to serve the stateless Streamable HTTP transport from MCP specification 2026-07-28 at `/mcp`. Each request stands alone: no initialization handshake and no `Mcp-Session-Id`. Clients on earlier protocol versions are served on the same endpoint.

> **Security: this endpoint has no authentication and no TLS.** Anyone who can reach the port can run every tool, including write and delete tools, with this server's vendor credentials. Keep the default loopback bind (`127.0.0.1`), or put the server behind an authenticating TLS proxy on a private network. `ULTRAVOX_MCP_ALLOWED_HOSTS` and `ULTRAVOX_MCP_ALLOWED_ORIGINS` protect against browser DNS rebinding, not against direct callers. A proxy in front of it needs connection and idle timeouts: a legacy-style `GET /mcp` with `Accept: text/event-stream` holds a stream open until the client disconnects.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ULTRAVOX_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http`. An empty value selects `stdio`. |
| `ULTRAVOX_MCP_HOST` | `127.0.0.1` | Bind address. An empty value selects `127.0.0.1`. `127.0.0.1`, `localhost` and `::1` use the SDK's built-in Host and Origin checks; any other value requires `ULTRAVOX_MCP_ALLOWED_HOSTS`. |
| `PORT` | `8080` | Port; must be an integer. |
| `ULTRAVOX_MCP_ALLOWED_HOSTS` | unset | Comma-separated `Host` header values accepted on a non-loopback bind, such as `mcp.example.com:8080` or `mcp.example.com:*`. |
| `ULTRAVOX_MCP_ALLOWED_ORIGINS` | unset | Comma-separated `Origin` values accepted on a non-loopback bind, such as `https://client.example.com`. Requests without an `Origin` header are accepted. |

Ultravox credentials come from the same configuration as stdio (see [Configuration](#configuration)), never from the request.

```bash
ULTRAVOX_MCP_TRANSPORT=streamable-http PORT=8080 uv run --locked ultravox-mcp
```

Point the MCP client at `http://127.0.0.1:8080/mcp`.

## Error handling

A failed tool call returns an MCP error result (`isError`) with a fixed message. The server never passes an Ultravox response body, a request URL or a credential back to the client.

| Situation | What the tool returns |
| --- | --- |
| Credentials missing | "No Ultravox API key found. Set ULTRAVOX_API_KEY or run: ultravox-mcp-setup, then restart the MCP server." |
| Authorization rejected (HTTP 401) | "Ultravox authorization expired. Re-run ultravox-mcp-setup." |
| Access denied (HTTP 403) | "Ultravox access denied: the connected account lacks permission for this action (or the authorization expired; re-run ultravox-mcp-setup if so)." |
| Not found (HTTP 404) | "Ultravox resource was not found (HTTP 404). Check the supplied identifier." |
| Rate limited (HTTP 429) | After the retries below: "Ultravox rate limit reached (HTTP 429). Retry after N seconds." |
| Any other HTTP error | "Ultravox API error 500: The service could not complete the request." The status varies, and the reason is one of a few fixed sentences (for example "The request was rejected." or "The service is temporarily unavailable."). |
| Success response that is not JSON, or `success: false` | "Ultravox API returned non-JSON (200)" or "Ultravox API reported that the operation failed." |
| Timeout or connection failure on a read | "Ultravox request timed out or the connection failed. Check connectivity and retry." |
| Timeout or connection failure on a write | "Ultravox request timed out or the connection failed; the outcome is unknown. Check whether the operation completed before retrying." |
| Destination host not approved (`create_tool`) | "baseUrlPattern must be a public HTTPS URL with a fixed hostname and no userinfo. Configure ULTRAVOX_ALLOWED_DESTINATION_HOSTS with trusted hosts." |
| Invalid arguments | A message such as "Invalid arguments for list_calls: page_size (expected an integer from 1 to 200)." |
| Unknown tool name | "Unknown tool. Choose a name from tools/list." |
| Anything else | "Error executing tool" followed by the tool name, with no detail. |

Every Ultravox request has a 30-second timeout. On HTTP 429 the server waits for the `Retry-After` interval (10 seconds when the header is missing or not a whole number of seconds) and retries, up to 3 times per request and 60 seconds of total waiting; if the next wait would exceed what is left, the tool returns the rate-limit message at once. The server does not retry timeouts, connection failures or 5xx responses. A failed resource read returns the same classified message, or "Unable to read this Ultravox resource. Try again or check the connection."

At startup the server exits with a message on stderr and a non-zero status when `ULTRAVOX_MCP_TRANSPORT` is neither `stdio` nor `streamable-http`, when `PORT` is not an integer, or when a non-loopback `ULTRAVOX_MCP_HOST` is set without `ULTRAVOX_MCP_ALLOWED_HOSTS`.

## Call flow

```text
MCP create_call  →  Ultravox REST  →  { callId, joinUrl, ... }
                                              |
                              joinUrl (wss://...) passed to Ultravox SDK
                                              |
                                     live audio session
```

The MCP handles steps 1–3. Everything after the `joinUrl` is your application's responsibility.

Real-time audio streaming is out of scope. `create_call` returns a `joinUrl`, and you connect to it with the [Ultravox client SDK](https://docs.ultravox.ai) or a WebSocket client. The MCP server has no role in the live call.

## Approved destination URLs

Set `ULTRAVOX_ALLOWED_DESTINATION_HOSTS` in the server environment, for example
`ULTRAVOX_ALLOWED_DESTINATION_HOSTS=hooks.firm.example,.integrations.firm.example`.
Comma-separated exact hosts allow only that host; a leading dot allows the domain
and its subdomains. Matching ignores case and trailing dots and normalizes IDNA.
An empty or unset list refuses destination URLs before any request. HTTPS, no
userinfo, and public literal addresses remain required. This administrator-owned
list prevents model-supplied destinations from sending data to arbitrary hosts,
including private-address DNS aliases and unapproved redirectors. Approve only
hosts whose DNS and redirects the firm trusts; the vendor executes requests later.
Tools cannot change this setting.

`create_tool` accepts only `baseUrlPattern` and `httpMethod` in `http_config`. The method must be GET, POST, PUT, PATCH, DELETE, HEAD, or OPTIONS. URL templates may vary the path and query but cannot vary the HTTPS scheme or hostname. Headers and other keys in this dictionary are rejected.

## Call join URL is a secret

`create_call` returns `joinUrl` to the user's own client so it can join the call. **`joinUrl` is a one-time secret: treat it like a short-lived token.** Do not share it or put it in logs, analytics, screenshots, or persistent transcripts.

## Testing

The test suite runs offline and needs no Ultravox account: every Ultravox API call is answered by a test double for the `requests` session. It covers list limits and paging, path-identifier validation, destination URL checks, error classification and the retry budget, credential file handling, the setup and verify commands, the stdio server, and the Streamable HTTP transport including the 2026-07-28 wire format, Host and Origin checks and stateless requests.

```bash
uv sync --locked
uv run --locked pytest -q
```

CI runs the suite on every push and pull request to `main`.

## License

MIT. See [LICENSE](LICENSE).
