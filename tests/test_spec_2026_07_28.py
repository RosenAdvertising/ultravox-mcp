"""Raw-wire and dual-era conformance tests for MCP 2026-07-28."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from mcp.client import Client
from starlette.testclient import TestClient

import ultravox_mcp.server as server_module
from ultravox_mcp.server import mcp

from .spec_check import (
    EXPECTED_MCP_PROTOCOL_VERSION,
    assert_mcp_protocol_version,
)

PROTOCOL_VERSION = EXPECTED_MCP_PROTOCOL_VERSION
LEGACY_PROTOCOL_VERSION = "2025-11-25"
PROTOCOL_VERSION_META = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
EXPECTED_TOOLS = [
    "get_account",
    "list_calls",
    "get_call",
    "create_call",
    "delete_call",
    "list_call_messages",
    "list_tools",
    "get_tool",
    "create_tool",
    "delete_tool",
    "list_voices",
]
LIST_TOOL_NAMES = ("list_calls", "list_call_messages", "list_tools", "list_voices")
_OMIT = object()


@pytest.fixture(scope="module")
def wire_client() -> Iterator[TestClient]:
    app = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        host="testserver",
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _meta(version: str = PROTOCOL_VERSION) -> dict[str, Any]:
    return {
        PROTOCOL_VERSION_META: version,
        CLIENT_CAPABILITIES_META: {},
        CLIENT_INFO_META: {"name": "ultravox-mcp-tests", "version": "1"},
    }


def _post(
    client: TestClient,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    version: str = PROTOCOL_VERSION,
    method_header: str | object = _OMIT,
    name_header: str | object = _OMIT,
):
    request_params = dict(params or {})
    request_params["_meta"] = _meta(version)
    headers = {
        "MCP-Protocol-Version": version,
        "Mcp-Method": method if method_header is _OMIT else str(method_header),
    }
    if name_header is not _OMIT:
        headers["Mcp-Name"] = str(name_header)
    return client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": request_params,
        },
        headers=headers,
    )


def _result(response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    return payload["result"]


def test_spec_guard_and_modern_discovery(wire_client: TestClient) -> None:
    assert_mcp_protocol_version()
    response = _post(wire_client, "server/discover")
    result = _result(response)

    assert result["supportedVersions"] == [PROTOCOL_VERSION]
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"] == {
        "name": "ultravox-mcp",
        "version": "0.1.0",
    }
    assert result["capabilities"] == {
        "prompts": {"listChanged": True},
        "resources": {"listChanged": True, "subscribe": True},
        "tools": {"listChanged": True},
    }
    assert "extensions" not in result["capabilities"]
    assert "Mcp-Session-Id" not in response.headers


@pytest.mark.parametrize(
    "method,result_key",
    [
        ("tools/list", "tools"),
        ("prompts/list", "prompts"),
        ("resources/list", "resources"),
        ("resources/templates/list", "resourceTemplates"),
    ],
)
def test_list_results_have_cache_and_result_metadata(
    wire_client: TestClient,
    method: str,
    result_key: str,
) -> None:
    result = _result(_post(wire_client, method))
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"
    assert result_key in result


def test_resource_read_has_cache_metadata_and_result_type(
    wire_client: TestClient,
) -> None:
    uri = "ultravox://security-notes"
    result = _result(
        _post(
            wire_client,
            "resources/read",
            {"uri": uri},
            name_header=uri,
        )
    )
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"
    assert result["contents"][0]["uri"] == uri


def test_tool_order_schemas_and_structured_result(
    wire_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _result(_post(wire_client, "tools/list"))["tools"]
    second = _result(_post(wire_client, "tools/list"))["tools"]
    assert [tool["name"] for tool in first] == EXPECTED_TOOLS
    assert [tool["name"] for tool in second] == EXPECTED_TOOLS

    schemas = {tool["name"]: tool["inputSchema"] for tool in first}
    for tool_name in LIST_TOOL_NAMES:
        page_size = schemas[tool_name]["properties"]["page_size"]
        assert page_size["minimum"] == 1
        assert page_size["maximum"] == 200

    class FakeClient:
        def get_account(self) -> dict[str, str]:
            return {"id": "account-test"}

    monkeypatch.setattr(server_module, "_client", FakeClient)
    result = _result(
        _post(
            wire_client,
            "tools/call",
            {"name": "get_account", "arguments": {}},
            name_header="get_account",
        )
    )
    assert result["resultType"] == "complete"
    assert result["structuredContent"] == {"id": "account-test"}
    assert result.get("isError", False) is False


def test_required_http_routing_headers(wire_client: TestClient) -> None:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {"_meta": _meta()},
    }
    mismatched_version = wire_client.post(
        "/mcp",
        json=request,
        headers={
            "MCP-Protocol-Version": "2099-01-01",
            "Mcp-Method": "tools/list",
        },
    ).json()
    assert mismatched_version["error"]["code"] == -32020

    missing_method = wire_client.post(
        "/mcp",
        json=request,
        headers={"MCP-Protocol-Version": PROTOCOL_VERSION},
    ).json()
    assert missing_method["error"]["code"] == -32020

    blank_method = _post(
        wire_client,
        "tools/list",
        method_header="",
    ).json()
    assert blank_method["error"]["code"] == -32020

    mismatched_method = _post(
        wire_client,
        "tools/list",
        method_header="prompts/list",
    ).json()
    assert mismatched_method["error"]["code"] == -32020

    missing_name = _post(
        wire_client,
        "tools/call",
        {"name": "get_account", "arguments": {}},
    ).json()
    assert missing_name["error"]["code"] == -32020

    mismatched_name = _post(
        wire_client,
        "tools/call",
        {"name": "get_account", "arguments": {}},
        name_header="list_calls",
    ).json()
    assert mismatched_name["error"]["code"] == -32020


def test_modern_error_codes_and_tool_validation(wire_client: TestClient) -> None:
    missing_uri = "ultravox://missing"
    not_found = _post(
        wire_client,
        "resources/read",
        {"uri": missing_uri},
        name_header=missing_uri,
    ).json()
    assert not_found["error"]["code"] == -32602

    unsupported = _post(
        wire_client,
        "tools/list",
        version="2099-01-01",
    ).json()
    assert unsupported["error"]["code"] == -32022

    unknown = _post(wire_client, "ultravox/unknown").json()
    assert unknown["error"]["code"] == -32601

    invalid_tool = _result(
        _post(
            wire_client,
            "tools/call",
            {"name": "list_calls", "arguments": {"page_size": 0}},
            name_header="list_calls",
        )
    )
    assert invalid_tool["resultType"] == "complete"
    assert invalid_tool["isError"] is True


def test_modern_and_legacy_negotiation() -> None:
    async def exercise_both_eras() -> None:
        async with Client(mcp, mode="auto") as modern:
            assert modern.session.protocol_version == PROTOCOL_VERSION
            assert modern.session.discover_result is not None
            result = await modern.list_tools(cache_mode="reload")
            assert [tool.name for tool in result.tools] == EXPECTED_TOOLS
            assert result.result_type == "complete"

        async with Client(mcp, mode="legacy") as legacy:
            assert legacy.session.protocol_version == LEGACY_PROTOCOL_VERSION
            result = await legacy.list_tools(cache_mode="reload")
            assert [tool.name for tool in result.tools] == EXPECTED_TOOLS

    asyncio.run(exercise_both_eras())
