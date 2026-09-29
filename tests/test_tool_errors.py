from __future__ import annotations

import asyncio
import logging
from typing import cast
from unittest.mock import Mock

import pytest
import requests
from mcp import Client
from mcp_types import CallToolResult, TextContent

import ultravox_mcp.server as server_module
from ultravox_mcp.client import (
    ArgumentValidationError,
    AuthenticationError,
    MissingCredentialsError,
    NotFoundError,
    RateLimitError,
    UltravoxClient,
    VendorHTTPError,
)
from ultravox_mcp.setup import verify as verify_module


def _call(name: str, arguments: dict[str, object] | None = None) -> CallToolResult:
    async def call():
        async with Client(server_module.mcp, cache=None) as sdk:
            return await sdk.call_tool(name, arguments or {})

    result = asyncio.run(call())
    assert isinstance(result, CallToolResult)
    return result


def _texts(result: CallToolResult) -> list[str]:
    return [cast(TextContent, part).text for part in result.content]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            MissingCredentialsError(
                "No Ultravox API key found. Set ULTRAVOX_API_KEY or run: ultravox-mcp-setup, then restart the MCP server."
            ),
            "No Ultravox API key found. Set ULTRAVOX_API_KEY or run: ultravox-mcp-setup, then restart the MCP server.",
        ),
        (
            AuthenticationError(
                "Ultravox authorization expired. Re-run ultravox-mcp-setup."
            ),
            "Ultravox authorization expired. Re-run ultravox-mcp-setup.",
        ),
        (
            VendorHTTPError(
                "Ultravox API error 502: The service rejected the request."
            ),
            "Ultravox API error 502: The service rejected the request.",
        ),
        (
            RateLimitError(
                "Ultravox rate limit reached (HTTP 429). Retry after 10 seconds."
            ),
            "Ultravox rate limit reached (HTTP 429). Retry after 10 seconds.",
        ),
        (
            NotFoundError(
                "Ultravox resource was not found (HTTP 404). Check the supplied identifier."
            ),
            "Ultravox resource was not found (HTTP 404). Check the supplied identifier.",
        ),
        (
            ArgumentValidationError("page_size must be between 1 and 200"),
            "page_size must be between 1 and 200",
        ),
    ],
)
def test_classified_errors_return_exact_sdk_result(monkeypatch, error, expected):
    class FakeClient:
        def get_account(self):
            raise error

    monkeypatch.setattr(server_module, "_client", FakeClient)
    result = _call("get_account")
    assert isinstance(result, CallToolResult)
    assert result.is_error is True
    assert _texts(result) == [expected]


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("person@example.test secret-token"),
        ValueError("https://private.test/x?token=abc"),
        TypeError("Alice Example"),
    ],
)
def test_unknown_errors_are_masked_and_fixed_reason_logged(monkeypatch, caplog, error):
    class FakeClient:
        def get_account(self):
            raise error

    monkeypatch.setattr(server_module, "_client", FakeClient)
    caplog.set_level(logging.WARNING, logger="ultravox_mcp.server")
    result = _call("get_account")
    assert result.is_error is True
    assert _texts(result) == ["Error executing tool get_account"]
    combined = caplog.text + repr(result.content)
    for secret in (
        "person@example.test",
        "secret-token",
        "private.test",
        "Alice Example",
        "token=abc",
    ):
        assert secret not in combined
    assert "unexpected_tool_error" in caplog.text


def test_schema_validation_returns_name_and_shape_without_value():
    result = _call("list_calls", {"page_size": "FAKE-PII-secret-token"})
    assert result.is_error is True
    assert _texts(result) == [
        "Invalid arguments for list_calls: page_size (expected an integer from 1 to 200)."
    ]
    assert "FAKE-PII" not in repr(result.content)


@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (
            401,
            {},
            "Ultravox authorization expired. Re-run ultravox-mcp-setup.",
        ),
        (
            403,
            {},
            "Ultravox access denied: the connected account lacks permission for this action (or the authorization expired; re-run ultravox-mcp-setup if so).",
        ),
        (
            404,
            {},
            "Ultravox resource was not found (HTTP 404). Check the supplied identifier.",
        ),
        (429, {}, "Ultravox rate limit reached (HTTP 429). Retry after 10 seconds."),
        (
            503,
            {
                "error": {
                    "code": "unavailable",
                    "message": "Alice Example secret-token https://private.test",
                }
            },
            "Ultravox API error 503: The service is temporarily unavailable.",
        ),
        (
            500,
            {"error": {"message": "Alice Example secret-token https://private.test"}},
            "Ultravox API error 500: The service rejected the request.",
        ),
    ],
)
def test_http_failures_are_classified_and_sanitized(
    monkeypatch, status, payload, expected
):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "DUMMY-TEST-TOKEN")
    client = UltravoxClient()
    monkeypatch.setattr("ultravox_mcp.client.time.sleep", lambda _seconds: None)
    response = Mock(
        status_code=status, ok=False, headers={}, json=Mock(return_value=payload)
    )
    client.session.request = Mock(return_value=response)
    with pytest.raises(RuntimeError) as caught:
        client.get("/calls")
    assert str(caught.value) == expected
    monkeypatch.setattr(server_module, "_client", lambda: client)
    result = _call("get_account")
    assert result.is_error
    assert _texts(result) == [expected]
    for unsafe in ("Alice Example", "secret-token", "private.test"):
        assert unsafe not in str(caught.value)


def test_retry_after_unsafe_header_uses_safe_default(monkeypatch):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "DUMMY-TEST-TOKEN")
    client = UltravoxClient()
    monkeypatch.setattr("ultravox_mcp.client.time.sleep", lambda _seconds: None)
    response = Mock(
        status_code=429, ok=False, headers={"Retry-After": "https://private.test/token"}
    )
    client.session.request = Mock(return_value=response)
    with pytest.raises(RateLimitError, match="Retry after 10 seconds") as caught:
        client._request("GET", "/calls", _rate_retries=3)
    assert "private.test" not in str(caught.value)


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        (
            "GET",
            "Ultravox request timed out or the connection failed. Check connectivity and retry.",
        ),
        (
            "POST",
            "Ultravox request timed out or the connection failed; the outcome is unknown. Check whether the operation completed before retrying.",
        ),
    ],
)
def test_transport_failures_are_safe_at_mcp_dispatch(monkeypatch, method, expected):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "DUMMY-TEST-TOKEN")
    client = UltravoxClient()
    client.session.request = Mock(side_effect=requests.Timeout("private token"))

    class FakeClient:
        def get_account(self):
            client._request(method, "/calls")

    monkeypatch.setattr(server_module, "_client", FakeClient)
    result = _call("get_account")
    assert result.is_error is True
    assert _texts(result) == [expected]


@pytest.mark.parametrize(
    "transport_error", [requests.Timeout, requests.ConnectionError]
)
def test_transport_error_types_are_classified(monkeypatch, transport_error):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "DUMMY-TEST-TOKEN")
    client = UltravoxClient()
    client.session.request = Mock(side_effect=transport_error("private token"))
    with pytest.raises(VendorHTTPError) as caught:
        client.post("/calls", body={})
    assert "outcome is unknown" in str(caught.value)
    assert "private token" not in str(caught.value)


def test_string_id_is_quoted_before_preparation_and_timeout_is_present(monkeypatch):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "DUMMY-TEST-TOKEN")
    client = UltravoxClient()
    response = Mock(status_code=200, ok=True, json=Mock(return_value={}))
    client.session.request = Mock(return_value=response)
    client.get_call("../x")
    args, kwargs = client.session.request.call_args
    assert args[1].endswith("/calls/..%2Fx")
    assert kwargs["timeout"] == 30


def test_retry_after_budget_stops_without_exceeding_sixty_seconds(monkeypatch):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "DUMMY-TEST-TOKEN")
    client = UltravoxClient()
    response = Mock(status_code=429, ok=False, headers={"Retry-After": "40"})
    client.session.request = Mock(return_value=response)
    sleeps = []
    monkeypatch.setattr("ultravox_mcp.client.time.sleep", sleeps.append)
    with pytest.raises(RateLimitError, match="Retry after 40 seconds"):
        client.get("/calls")
    assert sleeps == [40]
    assert client.session.request.call_count == 2


def test_http_200_success_false_is_a_safe_failure(monkeypatch):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "DUMMY-TEST-TOKEN")
    client = UltravoxClient()
    response = Mock(
        status_code=200,
        ok=True,
        json=Mock(return_value={"success": False, "message": "secret"}),
    )
    client.session.request = Mock(return_value=response)
    with pytest.raises(VendorHTTPError, match="operation failed"):
        client.post("/calls", body={})


def test_verify_bad_key_is_actionable_and_nonzero(monkeypatch, capsys):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "FAKE-BAD-KEY")
    client = UltravoxClient()
    response = Mock(status_code=401, ok=False, headers={})
    client.session.request = Mock(return_value=response)
    monkeypatch.setattr(verify_module, "UltravoxClient", lambda: client)
    with pytest.raises(SystemExit) as caught:
        verify_module.main()
    assert caught.value.code == 1
    assert "authorization expired" in capsys.readouterr().err


def test_setup_eof_is_clean_and_nonzero(monkeypatch, capsys):
    from ultravox_mcp.setup import setup as setup_module

    monkeypatch.setattr(setup_module.credentials, "get_secret", lambda _key: "")
    monkeypatch.setattr(
        setup_module.getpass,
        "getpass",
        lambda _prompt: (_ for _ in ()).throw(EOFError()),
    )
    with pytest.raises(SystemExit) as caught:
        setup_module.main()
    assert caught.value.code == 1
    captured = capsys.readouterr()
    assert "Re-run ultravox-mcp-setup in an interactive terminal" in captured.err
    assert "Traceback" not in captured.err


def test_setup_blank_secret_is_clean_and_nonzero(monkeypatch, capsys):
    from ultravox_mcp.setup import setup as setup_module

    monkeypatch.setattr(setup_module.credentials, "get_secret", lambda _key: "")
    monkeypatch.setattr(setup_module.getpass, "getpass", lambda _prompt: "   ")
    with pytest.raises(SystemExit) as caught:
        setup_module.main()
    assert caught.value.code == 1
    captured = capsys.readouterr()
    assert "No key entered" in captured.err
    assert "Traceback" not in captured.err


def test_verify_without_credentials_exits_actionably(monkeypatch, capsys):
    monkeypatch.delenv("ULTRAVOX_API_KEY", raising=False)
    with pytest.raises(SystemExit) as caught:
        verify_module.main()
    assert caught.value.code == 1
    captured = capsys.readouterr()
    assert "No Ultravox API key found" in captured.err
    assert "restart the MCP server" in captured.err
    assert "Traceback" not in captured.err


def test_setup_fake_bad_key_exits_actionably(monkeypatch, capsys):
    from ultravox_mcp.setup import setup as setup_module

    monkeypatch.setenv("ULTRAVOX_API_KEY", "FAKE-BAD-KEY")
    monkeypatch.setattr(setup_module.credentials, "get_secret", lambda _key: "")
    monkeypatch.setattr(
        setup_module.credentials, "set_secret", lambda _key, _value: "file"
    )
    monkeypatch.setattr(setup_module.getpass, "getpass", lambda _prompt: "FAKE-BAD-KEY")
    client = UltravoxClient()
    client.session.request = Mock(
        return_value=Mock(status_code=401, ok=False, headers={})
    )
    monkeypatch.setattr(verify_module, "UltravoxClient", lambda: client)
    with pytest.raises(SystemExit) as caught:
        setup_module.main()
    assert caught.value.code == 1
    output = capsys.readouterr()
    assert "authorization expired" in output.err
    assert "Traceback" not in output.err


def test_unexpected_pydantic_failure_is_not_argument_validation(monkeypatch, caplog):
    from pydantic import ValidationError

    failure = ValidationError.from_exception_data(
        "Vendor",
        [
            {
                "type": "string_type",
                "loc": ("private@example.invalid",),
                "input": "secret-token",
            }
        ],
    )

    class FakeClient:
        def get_account(self):
            raise failure

    monkeypatch.setattr(server_module, "_client", FakeClient)
    caplog.set_level(logging.WARNING)
    result = _call("get_account")
    assert result.is_error
    assert _texts(result) == ["Error executing tool get_account"]
    assert "private@example.invalid" not in caplog.text
    assert "secret-token" not in caplog.text


@pytest.mark.parametrize("error_type", [requests.Timeout, requests.ConnectionError])
@pytest.mark.parametrize("write", [False, True])
def test_real_dispatch_transport_contract(monkeypatch, error_type, write):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "fake-test-key")
    client = UltravoxClient()
    request = Mock(side_effect=error_type("PRIVATE_SENTINEL"))
    client.session.request = request
    monkeypatch.setattr(server_module, "_client", lambda: client)
    name = "delete_call" if write else "get_account"
    arguments: dict[str, object] = {"call_id": "../x"} if write else {}
    result = _call(name, arguments)
    expected = (
        "Ultravox request timed out or the connection failed; the outcome is unknown. Check whether the operation completed before retrying."
        if write
        else "Ultravox request timed out or the connection failed. Check connectivity and retry."
    )
    assert result.is_error is True
    assert _texts(result) == [expected]
    assert request.call_count == 1
    args, kwargs = request.call_args
    assert kwargs["timeout"] == 30
    if write:
        assert (
            requests.Request("DELETE", args[1]).prepare().path_url
            == "/api/calls/..%2Fx"
        )


@pytest.mark.parametrize(
    ("header", "expected_sleeps"), [("120", []), ("40", [40]), ("30", [30, 30])]
)
def test_rate_budget_and_hint_at_sdk_boundary(monkeypatch, header, expected_sleeps):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "fake-test-key")
    client = UltravoxClient()
    client.session.request = Mock(
        return_value=Mock(status_code=429, ok=False, headers={"Retry-After": header})
    )
    sleeps = []
    monkeypatch.setattr("ultravox_mcp.client.time.sleep", sleeps.append)
    monkeypatch.setattr(server_module, "_client", lambda: client)
    result = _call("get_account")
    assert result.is_error is True
    assert _texts(result) == [
        f"Ultravox rate limit reached (HTTP 429). Retry after {header} seconds."
    ]
    assert sleeps == expected_sleeps
    assert sum(sleeps) <= 60
    assert getattr(client, "_retry_sleep_budget", 0) == 0


@pytest.mark.parametrize(
    "resource", [server_module.voices_resource, server_module.tools_resource]
)
def test_unknown_resource_failure_is_sanitized(monkeypatch, resource):
    from mcp.server.mcpserver.exceptions import ResourceError

    def fail():
        raise RuntimeError("PRIVATE_SENTINEL")

    monkeypatch.setattr(server_module, "_client", fail)
    with pytest.raises(ResourceError) as caught:
        resource()
    assert (
        str(caught.value)
        == "Unable to read this Ultravox resource. Try again or check the connection."
    )


def test_verify_masks_unexpected_exception_text(monkeypatch, capsys):
    monkeypatch.setattr(
        verify_module,
        "UltravoxClient",
        Mock(side_effect=RuntimeError("PRIVATE_SENTINEL")),
    )
    assert verify_module.verify() is False
    assert (
        capsys.readouterr().err.strip()
        == "ERROR: Unable to verify the Ultravox connection. Check the API key or run ultravox-mcp-setup."
    )


def test_unsuccessful_200_is_a_tool_error(monkeypatch):
    monkeypatch.setenv("ULTRAVOX_API_KEY", "fake-test-key")
    client = UltravoxClient()
    client.session.request = Mock(
        return_value=Mock(
            status_code=200,
            ok=True,
            json=Mock(return_value={"success": False, "error": "PRIVATE_SENTINEL"}),
        )
    )
    monkeypatch.setattr(server_module, "_client", lambda: client)
    result = _call("delete_call", {"call_id": "../x"})
    assert result.is_error is True
    assert _texts(result) == ["Ultravox API reported that the operation failed."]
