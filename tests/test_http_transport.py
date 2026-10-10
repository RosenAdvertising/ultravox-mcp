"""In-process Streamable HTTP checks for MCP 2026-07-28."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any

import pytest
from mcp import Client
from starlette.testclient import TestClient

import ultravox_mcp.server as server

PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_VERSION_META = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META = "io.modelcontextprotocol/serverInfo"


def _headers(method: str, name: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if name is not None:
        headers["Mcp-Name"] = name
    return headers


def _body(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: int = 1,
) -> dict[str, Any]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META: PROTOCOL_VERSION,
        CLIENT_CAPABILITIES_META: {},
        CLIENT_INFO_META: {"name": "ultravox-http-test", "version": "0"},
    }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


def _post(
    client: TestClient,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    name: str | None = None,
    extra_headers: dict[str, str] | None = None,
    request_id: int = 1,
):
    headers = _headers(method, name)
    if extra_headers:
        headers.update(extra_headers)
    return client.post(
        "/mcp",
        json=_body(method, params, request_id=request_id),
        headers=headers,
    )


def _result(response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    return payload["result"]


@pytest.fixture
def http_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("ULTRAVOX_MCP_HOST", raising=False)
    monkeypatch.delenv("ULTRAVOX_MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("ULTRAVOX_MCP_ALLOWED_ORIGINS", raising=False)
    app = server.create_serve_app()
    with TestClient(app, base_url="http://127.0.0.1:8080") as client:
        yield client


def test_http_tools_list_matches_stdio_server(http_client: TestClient) -> None:
    async def stdio_tools() -> list[dict[str, Any]]:
        async with Client(server.mcp) as client:
            listed = await client.list_tools()
        return [
            tool.model_dump(by_alias=True, mode="json", exclude_none=True)
            for tool in listed.tools
        ]

    stdio = asyncio.run(stdio_tools())
    http_tools = _result(_post(http_client, "tools/list"))["tools"]
    assert [tool["name"] for tool in http_tools] == [tool["name"] for tool in stdio]
    assert [tool["inputSchema"] for tool in http_tools] == [
        tool["inputSchema"] for tool in stdio
    ]


def test_read_tool_runs_over_http(
    http_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeClient:
        def get_account(self) -> dict[str, str]:
            return {"id": "account-test"}

    monkeypatch.setattr(server, "_client", FakeClient)
    result = _result(
        _post(
            http_client,
            "tools/call",
            {"name": "get_account", "arguments": {}},
            name="get_account",
        )
    )
    assert result.get("isError", False) is False
    assert result["structuredContent"] == {"id": "account-test"}


def test_responses_are_sessionless(http_client: TestClient) -> None:
    first = _post(http_client, "tools/list", request_id=1)
    second = _post(
        http_client,
        "tools/list",
        request_id=2,
        extra_headers={"Mcp-Session-Id": "not-a-session"},
    )
    assert _result(first)["tools"]
    assert _result(second)["tools"]
    assert "mcp-session-id" not in first.headers
    assert "mcp-session-id" not in second.headers
    assert first.headers.get("mcp-session-id") is None
    assert second.headers.get("mcp-session-id") is None


def test_bogus_transport_exits_and_default_is_stdio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ULTRAVOX_MCP_TRANSPORT", "bogus")
    with pytest.raises(SystemExit, match="stdio") as exc_info:
        server.main()
    message = str(exc_info.value)
    assert "streamable-http" in message
    assert "bogus" in message

    monkeypatch.delenv("ULTRAVOX_MCP_TRANSPORT", raising=False)
    assert server._requested_transport() == "stdio"
    seen: dict[str, Any] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        seen["args"] = args
        seen["kwargs"] = kwargs

    monkeypatch.setattr(server.mcp, "run", fake_run)
    server.main()
    assert seen["args"] == ()
    assert seen["kwargs"] == {"transport": "stdio"}


def test_allowed_hosts_refuse_other_host_and_bad_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ULTRAVOX_MCP_HOST", "10.1.2.3")
    monkeypatch.setenv("ULTRAVOX_MCP_ALLOWED_HOSTS", "mcp.internal")
    monkeypatch.setenv("ULTRAVOX_MCP_ALLOWED_ORIGINS", "https://app.example")
    app = server.create_serve_app()
    with TestClient(app, base_url="http://mcp.internal") as client:
        refused = _post(
            client,
            "tools/list",
            extra_headers={"Host": "other.internal"},
        )
        assert refused.status_code == 421

        forbidden = _post(
            client,
            "tools/list",
            extra_headers={"Origin": "https://evil.example"},
        )
        assert forbidden.status_code == 403


def test_non_loopback_host_without_allowed_hosts_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ULTRAVOX_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("ULTRAVOX_MCP_HOST", "10.1.2.3")
    monkeypatch.delenv("ULTRAVOX_MCP_ALLOWED_HOSTS", raising=False)
    with pytest.raises(SystemExit, match="ULTRAVOX_MCP_ALLOWED_HOSTS"):
        server.main()


def test_get_and_delete_are_rejected_and_discover_advertises_version(
    http_client: TestClient,
) -> None:
    modern = {"MCP-Protocol-Version": PROTOCOL_VERSION}
    assert http_client.get("/mcp", headers=modern).status_code == 405
    assert http_client.delete("/mcp", headers=modern).status_code == 405

    result = _result(_post(http_client, "server/discover"))
    assert PROTOCOL_VERSION in result["supportedVersions"]
    version = result["_meta"][SERVER_INFO_META]["version"]
    assert isinstance(version, str) and version


def test_non_integer_port_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "nope")
    with pytest.raises(SystemExit, match="PORT must be an integer"):
        server._port()


def test_stateless_lifespan_runs_once(monkeypatch: pytest.MonkeyPatch) -> None:
    entries: list[str] = []

    @asynccontextmanager
    async def counting_lifespan(_app: object) -> Iterator[dict[str, Any]]:
        entries.append("enter")
        try:
            yield {}
        finally:
            entries.append("exit")

    monkeypatch.delenv("ULTRAVOX_MCP_HOST", raising=False)
    original = server.mcp._lowlevel_server.lifespan
    server.mcp._lowlevel_server.lifespan = counting_lifespan
    try:
        app = server.create_serve_app()
        with TestClient(app, base_url="http://127.0.0.1:8080") as client:
            assert _result(_post(client, "tools/list", request_id=1))["tools"]
            assert _result(_post(client, "tools/list", request_id=2))["tools"]
            assert entries == ["enter"]
        assert entries == ["enter", "exit"]
    finally:
        server.mcp._lowlevel_server.lifespan = original


def test_distinct_requests_do_not_share_connection_state(
    http_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Distinct POSTs must not observe a previous request's Connection.state.

    tools/list still has to succeed. Before each listing returns, the handler
    records the connection scratch dict and writes a token only this request
    should retain. A from_envelope that reuses one Connection.state dict leaves
    those tokens visible to the later requests.
    """
    handlers = server.mcp._lowlevel_server._request_handlers
    entry = handlers["tools/list"]
    retained: list[dict[str, Any]] = []
    state_ids: list[int] = []

    async def recording_list_tools(ctx: Any, params: Any) -> Any:
        connection = ctx.session._connection
        retained.append(dict(connection.state))
        state_ids.append(id(connection.state))
        token = f"request-{ctx.request_id}"
        connection.state[token] = token
        return await entry.handler(ctx, params)

    monkeypatch.setitem(
        handlers, "tools/list", replace(entry, handler=recording_list_tools)
    )

    for request_id in range(1, 10):
        result = _result(
            _post(
                http_client,
                "tools/list",
                request_id=request_id,
                extra_headers={"X-Request-Token": f"request-{request_id}"},
            )
        )
        assert any(tool["name"] == "get_account" for tool in result["tools"])

    assert len(retained) == 9
    leaked = [
        (request_id, prior)
        for request_id, prior in enumerate(retained, start=1)
        if prior != {}
    ]
    assert leaked == []
    assert len(set(state_ids)) == 9
