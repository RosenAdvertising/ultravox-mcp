# MCP 2026-07-28 migration

This server uses `MCPServer` from the Python MCP SDK and serves the Ultravox
REST tools over stdio. `pyproject.toml` requires `mcp>=2.2,<3`; `uv.lock`
resolves both `mcp` and its `mcp-types` companion to 2.2.0. The installed
SDK's latest protocol revision is guarded at `2026-07-28` by
`tests/spec_check.py`. The [specification notes](SPEC-DELTA-2026-07-28.md)
map the relevant protocol changes to this server.

## Server behavior

- `MCPServer` advertises the `ultravox-mcp` identity and application version
  `0.1.0`. The production entry point calls `mcp.run(transport="stdio")`.
- Eleven tools, three static resources, and prompts retain their REST scope.
  Tools create a per-call REST client; no MCP session or cross-call state was
  added. Returning `dict[str, Any]` gives tool results a structured output
  schema and `structuredContent` alongside text content.
- The four list tools accept page sizes from 1 through 200 and make one vendor
  request per invocation. They pass through the vendor's cursor and order;
  this server does not apply local sorting or fetch later pages automatically.
- Diagnostics record rejection reasons and status metadata without vendor
  response bodies or account fields. The setup verification displays an
  account identifier instead of an email address.

## Protocol coverage

The tests exercise modern `server/discover`, sessionless requests, required
HTTP routing headers, cache metadata, deterministic tool discovery, JSON
schemas, structured tool output, error codes, and legacy negotiation. The
Streamable HTTP app is constructed in process for these tests; production
continues to use stdio. The expected modern wire errors include `-32020` for
header mismatch, `-32022` for unsupported protocol, `-32601` for unknown
methods, and `-32602` for unknown resources. The server does not implement
MCP OAuth, subscriptions publishing, MRTR, or browser transport behavior.

## Reproduce local checks

With the locked environment installed (`uv sync --offline --locked` when the
packages are cached), run from the repository root:

```bash
ULTRAVOX_API_KEY=fixture .venv/bin/python -m pytest -q
.venv/bin/ruff check tests ultravox_mcp
ULTRAVOX_API_KEY=fixture .venv/bin/python tests/spec_check.py --mcp-only
uv lock --check --offline
```

The fixture key is set before imports so the suite does not consult a local
credential store. Tests use fake account data, mocked vendor requests, and an
in-process transport. They do not establish live vendor behavior, deployed
stdio behavior, vendor ordering, or tenant isolation.

## Error behavior

Vendor request failures are classified locally and surfaced as safe MCP tool
errors. Messages omit vendor response text, credentials, and argument values.
Transport failures on reads advise checking connectivity and retrying; on
mutations they explain that completion is uncertain and ask the caller to check
the operation's status before retrying. Setup and verification report actionable
credential or authorization guidance without exposing secret values.
