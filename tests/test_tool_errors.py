from __future__ import annotations

import asyncio
import logging
from typing import cast
from unittest.mock import Mock

import pytest
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
                "No Ultravox API key found. Set ULTRAVOX_API_KEY or run: ultravox-mcp-setup"
            ),
            "No Ultravox API key found. Set ULTRAVOX_API_KEY or run: ultravox-mcp-setup",
        ),
        (
            AuthenticationError(
                "Ultravox authorization was rejected or expired. Re-authorize with: ultravox-mcp-setup"
            ),
            "Ultravox authorization was rejected or expired. Re-authorize with: ultravox-mcp-setup",
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
            "Ultravox authorization was rejected or expired. Re-authorize with: ultravox-mcp-setup",
        ),
        (
            403,
            {},
            "Ultravox authorization was rejected or expired. Re-authorize with: ultravox-mcp-setup",
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
