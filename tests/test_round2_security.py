"""Round 2 policy regressions through registered MCP calls, with mocked transport."""

import pytest

from .test_daybreak_security import BAD_URLS, invoke, text
from .test_daybreak_security import api as api

SETTING = "ULTRAVOX_ALLOWED_DESTINATION_HOSTS"


@pytest.mark.parametrize(
    "name,args,key",
    [
        (
            "create_tool",
            {"name": "probe", "description": "probe", "parameters_schema": {}},
            "http_config",
        )
    ],
)
@pytest.mark.parametrize(
    "url",
    BAD_URLS
    + [
        "https://127.0.0.1.sslip.io/",
        "https://example.com/redirect?next=http%3A%2F%2F127.0.0.1%2F",
        "https://unlisted.example/",
        "https://hooks.firm.example.attacker.example/",
        "https://nothooks.firm.example/",
    ],
)
def test_unapproved_destination_zero_requests(api, monkeypatch, name, args, key, url):
    monkeypatch.setenv(SETTING, "hooks.firm.example")
    arguments = dict(args)
    arguments[key] = {"baseUrlPattern": url, "httpMethod": "POST"}
    result = invoke(name, arguments)
    assert result.is_error, text(result)
    api.post.assert_not_called()
    api.put.assert_not_called()


@pytest.mark.parametrize(
    "name,args,key",
    [
        (
            "create_tool",
            {"name": "probe", "description": "probe", "parameters_schema": {}},
            "http_config",
        )
    ],
)
@pytest.mark.parametrize("setting", [None, "", " , "])
def test_missing_allowlist_actionable_zero_requests(
    api, monkeypatch, name, args, key, setting
):
    if setting is None:
        monkeypatch.delenv(SETTING, raising=False)
    else:
        monkeypatch.setenv(SETTING, setting)
    url = "https://hooks.firm.example/event"
    arguments = dict(args)
    arguments[key] = {"baseUrlPattern": url, "httpMethod": "POST"}
    result = invoke(name, arguments)
    assert result.is_error, text(result)
    assert SETTING in text(result)
    api.post.assert_not_called()
    api.put.assert_not_called()


@pytest.mark.parametrize(
    "name,args,key",
    [
        (
            "create_tool",
            {"name": "probe", "description": "probe", "parameters_schema": {}},
            "http_config",
        )
    ],
)
@pytest.mark.parametrize(
    "setting,url",
    [
        ("hooks.firm.example", "https://hooks.firm.example/event"),
        (
            " unrelated.example, HOOKS.FIRM.EXAMPLE. ",
            "https://HOOKS.FIRM.EXAMPLE./event",
        ),
        (".firm.example", "https://firm.example/event"),
        (".firm.example", "https://sub.hooks.firm.example/event"),
        ("bücher.example", "https://xn--bcher-kva.example/event"),
        ("xn--bcher-kva.example", "https://bücher.example/event"),
    ],
)
def test_approved_destination_preserved(
    api, monkeypatch, name, args, key, setting, url
):
    monkeypatch.setenv(SETTING, setting)
    arguments = dict(args)
    arguments[key] = {"baseUrlPattern": url, "httpMethod": "POST"}
    result = invoke(name, arguments)
    assert not result.is_error, text(result)
    assert api.post.called or api.put.called
    assert url in str(api.post.call_args_list + api.put.call_args_list)


@pytest.mark.parametrize(
    "name,args,key",
    [
        (
            "create_tool",
            {"name": "probe", "description": "probe", "parameters_schema": {}},
            "http_config",
        )
    ],
)
@pytest.mark.parametrize(
    "setting,url",
    [
        ("firm.example", "https://sub.firm.example/"),
        (".firm.example", "https://notfirm.example/"),
        (".firm.example", "https://firm.example.attacker.example/"),
        ("*", "https://hooks.firm.example/"),
        ("https://hooks.firm.example", "https://hooks.firm.example/"),
        ("hooks.firm.example/path", "https://hooks.firm.example/"),
        ("hooks.firm.example:443", "https://hooks.firm.example/"),
    ],
)
def test_allowlist_is_exact_and_fail_closed(
    api, monkeypatch, name, args, key, setting, url
):
    monkeypatch.setenv(SETTING, setting)
    arguments = dict(args)
    arguments[key] = {"baseUrlPattern": url, "httpMethod": "POST"}
    result = invoke(name, arguments)
    assert result.is_error, text(result)
    api.post.assert_not_called()
    api.put.assert_not_called()


@pytest.mark.parametrize(
    "name,args,key",
    [
        (
            "create_tool",
            {"name": "probe", "description": "probe", "parameters_schema": {}},
            "http_config",
        )
    ],
)
@pytest.mark.parametrize(
    "setting,url",
    [
        (None, "https://hooks.firm.example/"),
        ("hooks.firm.example", "https://127.0.0.1.sslip.io/"),
        (
            "hooks.firm.example",
            "https://example.com/redirect?next=http%3A%2F%2F127.0.0.1%2F",
        ),
    ],
)
def test_rejection_precedes_client_construction(
    monkeypatch, name, args, key, setting, url
):
    from unittest.mock import Mock

    from ultravox_mcp import server

    factory = Mock(side_effect=AssertionError("no client or token refresh"))
    monkeypatch.setattr(server, "UltravoxClient", factory)
    if setting is None:
        monkeypatch.delenv(SETTING, raising=False)
    else:
        monkeypatch.setenv(SETTING, setting)
    arguments = dict(args)
    arguments[key] = {"baseUrlPattern": url, "httpMethod": "POST"}
    assert invoke(name, arguments).is_error
    factory.assert_not_called()
