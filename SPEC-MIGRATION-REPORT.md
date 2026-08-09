# MCP 2026-07-28 migration report

## Result

`ultravox-mcp` now targets MCP `2026-07-28`, up from `2025-11-25`. The direct
Python SDK dependency changed from `mcp>=1.28.1,<2` (locked to `1.28.1`) to the
exact migration release `mcp==2.0.0`. The refreshed lock includes the SDK v2
dependency split, including `mcp-types==2.0.0`.

The authoritative repository-specific change analysis is in
[`SPEC-DELTA-2026-07-28.md`](SPEC-DELTA-2026-07-28.md). Sources are the
[official MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog),
[SDK v2.0.0 release notes](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0),
and [official v1-to-v2 migration guide](https://py.sdk.modelcontextprotocol.io/migration/).

No deployment, live Ultravox account, credential, or browser application was
touched.

## Current-revision verdict

This was a migration, not a no-op:

- `pyproject.toml` required SDK v1 and `uv.lock` resolved `mcp==1.28.1`.
- `ultravox_mcp/server.py` constructed v1 `FastMCP` and ran the default stdio
  transport.
- The repository had no tracked test files, raw-wire protocol tests, or MCP
  spec guard.
- Baseline `pytest` collected zero tests and exited 5. Baseline Ruff reported
  nine pre-existing findings.

## Implementation

- Replaced v1 `FastMCP` with v2 `MCPServer`, retained the `ultravox-mcp`
  identity and instructions, and now reports application version `0.1.0`.
- Kept production on stdio and moved the transport choice to
  `mcp.run(transport="stdio")`.
- Preserved the existing tool, resource, prompt, credential, per-call REST
  client, cursor, and cache posture. No MCP session or cross-call state was
  added.
- Changed tool result annotations from bare `dict` to `dict[str, Any]`. SDK v2
  can therefore publish an output schema, validate the vendor object, and fill
  `structuredContent` as well as text content.
- Pinned `mcp==2.0.0`, refreshed `uv.lock`, installed with `uv sync --frozen`,
  and added locked pytest/Ruff development dependencies.
- Added a Python 3.10 Ruff target consistent with the package floor and cleared
  the baseline lint findings.

## Protocol conformance

The migration tests prove:

- Modern sessionless `server/discover` reports only `2026-07-28`, the expected
  identity and capabilities, private zero-TTL cache hints, and
  `resultType: "complete"` without `Mcp-Session-Id`.
- Raw HTTP requests require matching `MCP-Protocol-Version`, `Mcp-Method`, and
  `Mcp-Name` headers. Header mismatch is `-32020`, unsupported protocol is
  `-32022`, and unknown method is `-32601`.
- Tools, prompts, resources, resource templates, and resource reads carry the
  required cache and result metadata.
- Tool discovery is deterministic across repeated calls; all eleven tools have
  JSON Schema object inputs, and each list tool publishes a 1-200 page-size
  constraint.
- Structured tool output remains machine-readable, an invalid tool call is a
  complete error result, and an unknown resource returns Invalid Params
  `-32602`.
- SDK v2 modern auto-negotiation selects `2026-07-28`, while forced legacy
  negotiation still selects `2025-11-25` and lists the same tools.
- `tests/spec_check.py --mcp-only` guards the installed SDK's latest protocol
  constant against unreviewed drift.

## Canary sibling checks

### A. List-tool limit and order — FIXED

All four vendor list tools (`list_calls`, `list_call_messages`, `list_tools`,
and `list_voices`) make exactly one vendor request and never auto-paginate past
the requested amount. Their page size is now schema-enforced and runtime-
enforced from 1 through 200, with regression coverage at the boundaries and
for rejection.

The local API wrapper exposes no sort/order option and introduces no local
oldest-first default; it preserves the vendor's cursor-defined order. The
network grant excluded Ultravox documentation and no account was supplied, so
vendor ordering is method-verified only, not live-verified.

### B. Silent rejections — FIXED

Missing API keys, invalid API keys, non-JSON responses, vendor errors, rate
limits, invalid page sizes, and keyring fallback/failure decisions now have
PII-free reason logs. Logs contain status/reason metadata only, never response
bodies, API keys, call data, account data, or tool payloads.

### C. Origin/CSP ceremony — N-A

This repository serves MCP over stdio and contains no browser pages, CSP,
frontend assets, or application Origin gate. The Streamable HTTP app exists
only inside the raw-wire test harness and uses the SDK's host validation.

### D. PII in logs — FIXED

The source sweep found no application logger receiving `sub`, email, or name
values. Vendor response bodies were removed from raised diagnostics before
those diagnostics can reach stderr, and setup verification now displays a
PII-free account identifier instead of preferring account email. Regression
tests seed email, name, and `sub`-shaped values and prove none reaches the
exception/log output.

## Verification

Baseline on the default branch:

- `uv run --with pytest pytest -q`: **0 tests collected** (exit 5).
- `uvx ruff check .`: **9 findings**.

Migrated branch, from the locked environment:

- `uv run pytest -q`: **25 passed**.
- `uv run ruff check .`: **all checks passed**.
- `uv run python tests/spec_check.py --mcp-only`: **MCP protocol:
  2026-07-28**.
- `uv lock --check` and `uv sync --frozen`: **passed**.

No live Ultravox call was made. REST endpoint wiring is mock-verified; live
account behavior, vendor ordering, and credentials remain intentionally
untested.

## Commits and handoff

The branch is divided into these Conventional Commit subjects, and every commit
contains the required co-author trailer:

1. `docs: document MCP 2026-07-28 delta`
2. `feat: migrate server to MCP 2026-07-28`
3. `test: prove MCP 2026-07-28 conformance`
4. `docs: report MCP 2026-07-28 migration`

The sandbox denied writes to the repository's `.git` directory, so commits were
built in the authorized alternate Git database. The external fan-out handoff
includes a verified portable bundle containing `spec-2026-07-28` with complete
history. That bundle must be imported into the repository; nothing was pushed.
