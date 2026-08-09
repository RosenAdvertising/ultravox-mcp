"""Regression tests for list caps, rejection logs, and PII-free diagnostics."""

from __future__ import annotations

import importlib
import logging
from unittest.mock import Mock

import pytest

from ultravox_mcp.client import UltravoxClient

verify_module = importlib.import_module("ultravox_mcp.setup.verify")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> UltravoxClient:
    monkeypatch.setenv("ULTRAVOX_API_KEY", "test-api-key")
    return UltravoxClient()


@pytest.mark.parametrize(
    "method,args,expected_path,expected_params",
    [
        ("list_calls", (200, "next-page"), "/calls", {"pageSize": 200, "cursor": "next-page"}),
        ("list_call_messages", ("call-test", 200), "/calls/call-test/messages", {"pageSize": 200}),
        ("list_tools", (200,), "/tools", {"pageSize": 200}),
        ("list_voices", (200,), "/voices", {"pageSize": 200}),
    ],
)
def test_list_tools_make_one_capped_request(
    client: UltravoxClient,
    method: str,
    args: tuple[object, ...],
    expected_path: str,
    expected_params: dict[str, object],
) -> None:
    vendor_page = {"results": [{"id": "one"}], "next": "more"}
    client.get = Mock(return_value=vendor_page)  # type: ignore[method-assign]

    result = getattr(client, method)(*args)

    assert result is vendor_page
    client.get.assert_called_once_with(expected_path, params=expected_params)


@pytest.mark.parametrize(
    "method,args",
    [
        ("list_calls", (0,)),
        ("list_calls", (201,)),
        ("list_call_messages", ("call-test", 0)),
        ("list_call_messages", ("call-test", 201)),
        ("list_tools", (0,)),
        ("list_tools", (201,)),
        ("list_voices", (0,)),
        ("list_voices", (201,)),
    ],
)
def test_list_tools_reject_out_of_range_limits(
    client: UltravoxClient,
    method: str,
    args: tuple[object, ...],
) -> None:
    client.get = Mock()  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="between 1 and 200"):
        getattr(client, method)(*args)

    client.get.assert_not_called()


def test_vendor_rejection_log_and_error_exclude_pii(
    client: UltravoxClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_values = ("person@example.test", "Alice Example", "auth0|secret-sub")
    response = Mock(
        status_code=500,
        ok=False,
        text=" ".join(sensitive_values),
        headers={},
    )
    client.session.request = Mock(return_value=response)
    caplog.set_level(logging.WARNING, logger="ultravox_mcp.client")

    with pytest.raises(RuntimeError, match=r"Ultravox API error 500") as exc_info:
        client.get("/calls")

    captured = str(exc_info.value) + caplog.text
    for sensitive in sensitive_values:
        assert sensitive not in captured
    assert "ultravox_request_rejected" in caplog.text


def test_missing_credentials_rejection_is_reason_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("ULTRAVOX_API_KEY", raising=False)
    caplog.set_level(logging.WARNING, logger="ultravox_mcp.client")

    with pytest.raises(RuntimeError, match="No Ultravox API key"):
        UltravoxClient()

    assert "ultravox_client_rejected" in caplog.text


def test_verify_output_does_not_display_email_or_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeClient:
        def get_account(self) -> dict[str, str]:
            return {
                "id": "account-test",
                "email": "person@example.test",
                "name": "Alice Example",
            }

    monkeypatch.setattr(verify_module, "UltravoxClient", FakeClient)

    assert verify_module.verify() is True
    output = capsys.readouterr().out
    assert "account-test" in output
    assert "person@example.test" not in output
    assert "Alice Example" not in output
