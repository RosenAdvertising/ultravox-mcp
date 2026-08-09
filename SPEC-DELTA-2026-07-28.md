# MCP specification delta: 2025-11-25 to 2026-07-28

Research date: 2026-08-09. Sources are limited to the official MCP
specification and the official MCP Python SDK repository/documentation.

## Current target and migration release

This repository currently targets MCP `2025-11-25`:

- `pyproject.toml` declares `mcp>=1.28.1,<2`, and `uv.lock` resolves MCP Python
  SDK 1.28.1. The v1 line's latest protocol was set to `2025-11-25` in SDK
  1.23.1, and v1.28.1 did not advance that protocol target
  ([official v1.23.1 release notes](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v1.23.1),
  [official v1.28.1 release notes](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v1.28.1)).
- `ultravox_mcp/server.py` constructs v1 `FastMCP` without overriding protocol
  negotiation and calls `run()` with its default stdio transport. The server
  has no explicit hosted HTTP entry point or MCP session state.
- The default branch has no tracked protocol tests or MCP spec guard. Its only
  `tests/` content is ignored Python bytecode, so no test establishes a newer
  protocol revision.

The official changelog says `2026-07-28` follows `2025-11-25`
([spec changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)).
The implementation release is MCP Python SDK `2.0.0`, whose release notes say
it supports `2026-07-28` and earlier protocol revisions from the same server
([SDK v2.0.0 release notes](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)).

Verdicts below mean:

- **AFFECTS-US**: this server exposes or relies on the changed surface. The SDK
  may implement the wire behavior, but the migration must still pin,
  configure, or test it.
- **NOT-APPLICABLE**: the feature or direction is not implemented here. It will
  not be adopted merely because the revision permits it.

## Protocol negotiation and lifecycle

| Normative change | Verdict | Ultravox-specific reason |
| --- | --- | --- |
| Protocol-level sessions and `Mcp-Session-Id` are removed for the modern revision; cross-call application state must use explicit handles. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | The stdio entry point has no session state, and every tool creates an independent REST client. The SDK v2 modern dispatcher and conformance HTTP app must remain sessionless; a test will reject any session-header dependency. |
| `initialize` / `notifications/initialized` are removed for modern requests. Each request carries protocol version and client capabilities in `_meta`, while version mismatch uses `UnsupportedProtocolVersionError`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | The stdio server must accept modern self-describing requests. SDK v2 provides a dual-era dispatcher; tests must exercise both modern requests and legacy negotiation. |
| Servers MUST implement `server/discover`, advertising versions, capabilities, and identity. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | Discovery is required for every modern server and must identify this server and its actual tools, resources, and prompts. |
| All results require `resultType`: `"complete"` for ordinary results or `"input_required"` for MRTR. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | This server returns tool, resource, prompt, and discovery results. The SDK v2 wire serialization must be asserted. |
| Server-initiated requests are replaced by Multi Round-Trip Requests (MRTR). [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | No handler uses sampling, roots, elicitation, or any other server-to-client request. This migration will not add MRTR as a feature. |
| `ping`, `logging/setLevel`, and `notifications/roots/list_changed` are removed; protocol logging becomes per-request opt-in. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The application implements none of these methods and emits no MCP logging notifications. PII-free application diagnostics remain on stderr. |

## Transports and notifications

| Normative change | Verdict | Ultravox-specific reason |
| --- | --- | --- |
| Streamable HTTP POST requests require `Mcp-Method`, plus `Mcp-Name` for named operations; `x-mcp-header` supports selected tool parameters. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Production remains stdio, but the SDK migration's required raw-wire conformance surface constructs the same server as a Streamable HTTP app. It must validate modern routing headers. No tool parameter opts into `x-mcp-header`. |
| HTTP GET and `resources/subscribe` / `resources/unsubscribe` are replaced by opt-in `subscriptions/listen`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | The server exposes tools, prompts, and resources. SDK v2 maps high-level change/subscription declarations to the modern transport. Existing declarations are preserved without adding a publisher, event store, or custom subscription bus. |
| SSE resumability and redelivery (`Last-Event-ID` and SSE event IDs) are removed. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The server configures no event store and depends on no redelivery behavior. |
| Legacy HTTP+SSE is formally deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The production server exposes stdio only and has no HTTP+SSE entry point. |

## Capabilities and extensions

| Normative change | Verdict | Ultravox-specific reason |
| --- | --- | --- |
| `ClientCapabilities` and `ServerCapabilities` gain an `extensions` field. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | `server/discover` exposes this shape. The server adds no extension and must not advertise one. |
| Experimental core tasks move to the `io.modelcontextprotocol/tasks` extension. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The server has no task handlers or task-augmented tools. |
| Roots, Sampling, and Logging are deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | None is declared or used. |
| Sampling `includeContext` values `"thisServer"` and `"allServers"` are deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | Sampling is not used. |

## Tools, resources, prompts, and cache semantics

| Normative change | Verdict | Ultravox-specific reason |
| --- | --- | --- |
| `tools/list`, `prompts/list`, `resources/list`, `resources/templates/list`, and `resources/read` results require `ttlMs` and `cacheScope`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server exposes tools, static resources, and prompts. SDK v2's conservative private, zero-TTL defaults will be verified for every applicable result. |
| Servers SHOULD return `tools/list` in deterministic order. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Eleven tools are registered in stable source order. Repeated listings must preserve that order. |
| Tool schemas accept JSON Schema 2020-12, and `structuredContent` may be any JSON value. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Decorators generate the eleven input schemas and REST results are structured objects. SDK v2 owns revised validation; tests must prove generated object schemas and structured results remain valid. |
| Resource-not-found changes from `-32002` to JSON-RPC Invalid Params `-32602`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server exposes three static resources. An unknown URI must now produce `-32602`. |
| URL-mode elicitation removes its completion notification and `elicitationId`; application `requestState` correlates MRTR retries. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server performs no elicitation. |
| The generated schema now models minimum, maximum, and default as numbers instead of integers. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#other-schema-changes) | **NOT-APPLICABLE** | This repository neither vendors the MCP schema nor directly validates against its numeric meta-schema. SDK v2 absorbs the correction. |

## Authorization and security

| Normative change | Verdict | Ultravox-specific reason |
| --- | --- | --- |
| Authorization servers SHOULD return RFC 9207 `iss`; MCP clients validate a present issuer. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | This is not an MCP authorization server or OAuth client. Its only credential is a vendor API key used downstream. |
| MCP clients performing Dynamic Client Registration must send an appropriate `application_type`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | This code does not dynamically register an MCP client. |
| Persisted MCP client credentials are bound to their authorization-server issuer. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server stores no MCP client registrations. Ultravox API-key storage is a separate downstream credential concern. |
| Dynamic Client Registration is deprecated in favor of Client ID Metadata Documents. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The server neither hosts DCR nor acts as a dynamically registered MCP client. |

## Errors, metadata, and observability

| Normative change | Verdict | Ultravox-specific reason |
| --- | --- | --- |
| MCP reserves `-32020..-32099`; header mismatch, missing capability, and unsupported version use `-32020`, `-32021`, and `-32022`; unknown methods use `-32601`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The raw HTTP conformance entry point can receive mismatched headers, unsupported versions, and unknown methods. Reachable codes will be asserted without adding an artificial capability-gated feature. |
| `_meta` formally carries W3C `traceparent`, `tracestate`, and `baggage`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server has no MCP tracing integration. This migration will not add an observability feature. |

The changelog's governance and SEP workflow changes impose no server runtime or
wire requirement and are intentionally omitted from the verdict tables. The
feature lifecycle is respected by not adopting deprecated Roots, Sampling,
Logging, HTTP+SSE, or DCR.
