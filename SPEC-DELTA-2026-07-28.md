# MCP specification notes: 2026-07-28

The Python MCP SDK requirement is `mcp>=2.2,<3`. The lock resolves `mcp` and
`mcp-types` to 2.2.0. The server uses `MCPServer`, serves stdio in production,
and guards the installed SDK's latest protocol revision with
`tests/spec_check.py --mcp-only`.

The mappings below follow the [official protocol changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
and the [Python SDK migration guide](https://py.sdk.modelcontextprotocol.io/migration/).

| Protocol area               | Mapping for this server                                                                                                                                                                                                                                        |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Discovery and lifecycle     | Modern requests use `server/discover` and per-request protocol metadata. The server has no MCP session state; the conformance tests check discovery, identity, capabilities, `resultType`, and absence of `Mcp-Session-Id`. Legacy negotiation is also tested. |
| Streamable HTTP routing     | Production uses stdio. An in-process HTTP test app checks `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` routing headers and the applicable JSON-RPC error codes. No tool parameter opts into `x-mcp-header`.                                            |
| Result metadata and caching | Tool, resource, prompt, and discovery responses are checked for `resultType` and applicable private, zero-TTL cache metadata.                                                                                                                                  |
| Tool schemas and output     | Eleven tools register in stable order. List page sizes have 1–200 bounds. Object results include structured content; generated input schemas remain JSON objects.                                                                                              |
| Resources                   | The server exposes three static resources. Unknown resource URIs return Invalid Params (`-32602`). There is no custom subscription publisher or event store.                                                                                                   |
| Errors                      | Header mismatch uses `-32020`, unsupported protocol `-32022`, and unknown method `-32601` in the tested HTTP path. The server has no capability-gated feature to exercise `-32021`.                                                                            |
| Optional features           | No server-initiated sampling, roots, elicitation, tasks, MCP OAuth, dynamic client registration, or protocol tracing is implemented.                                                                                                                           |

Run the checks from the repository root with the locked environment installed:

```bash
ULTRAVOX_API_KEY=fixture .venv/bin/python -m pytest -q
.venv/bin/ruff check tests ultravox_mcp
ULTRAVOX_API_KEY=fixture .venv/bin/python tests/spec_check.py --mcp-only
uv lock --check --offline
```

The tests use an in-process transport and mocked Ultravox responses; they do
not verify a live account or deployed transport. See the
[migration report](SPEC-MIGRATION-REPORT.md) for the server changes and the
remaining product decision about safe tool-error messages.
