"""Ultravox REST API client — handles auth, retries, and all endpoint calls."""

import logging
import os
import re
import time
from urllib.parse import quote

import requests

from ultravox_mcp import credentials
from ultravox_mcp.url_security import validate_public_https

BASE_URL = "https://api.ultravox.ai/api"
MAX_PAGE_SIZE = 200

logger = logging.getLogger(__name__)


def _path_id(value, parameter: str) -> str:
    """Validate a plain identifier before URL quoting or any HTTP request."""
    expected = (
        "a non-empty plain identifier (ASCII letters, digits, -, _, ., ~); not . or .."
    )
    if (
        isinstance(value, bool)
        or not isinstance(value, (str, int))
        or str(value) in {".", ".."}
        or re.fullmatch(r"[A-Za-z0-9._~-]+", str(value)) is None
    ):
        message = f"Invalid argument '{parameter}': use {expected}."
        raise ArgumentValidationError(message)
    return quote(str(value), safe="")


class UltravoxClientError(RuntimeError):
    """A classified, safe-to-display Ultravox request failure."""


class MissingCredentialsError(UltravoxClientError):
    pass


class AuthenticationError(UltravoxClientError):
    pass


class VendorHTTPError(UltravoxClientError):
    pass


class RateLimitError(UltravoxClientError):
    pass


class NotFoundError(UltravoxClientError):
    pass


class ArgumentValidationError(ValueError):
    """A client-side argument failed a documented constraint."""


# Resolve credentials through the pluggable store (OS keyring -> .env file).
credentials.load_into_environ(["ULTRAVOX_API_KEY"])


def _retry_after_seconds(resp, default=10):
    try:
        value = resp.headers.get("Retry-After", default)
        # Only accept a small decimal delay. Dates, URLs, and arbitrary header text
        # are not reflected to the caller.
        if not str(value).isascii() or not str(value).isdigit():
            return default
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


_SAFE_VENDOR_REASONS = {
    "invalid_request": "The request was rejected.",
    "permission_denied": "The operation is not permitted.",
    "resource_exhausted": "The service is temporarily busy.",
    "unavailable": "The service is temporarily unavailable.",
    "internal": "The service could not complete the request.",
}


def _safe_vendor_reason(resp) -> str:
    """Map a structured vendor code to an allowlisted explanation, else stay generic."""
    try:
        payload = resp.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        code = error.get("code") if isinstance(error, dict) else None
        if isinstance(code, str):
            return _SAFE_VENDOR_REASONS.get(
                code.lower(), "The service rejected the request."
            )
    except (ValueError, TypeError, AttributeError):
        pass
    return "The service rejected the request."


def _json_response(resp):
    try:
        payload = resp.json()
    except ValueError:
        logger.warning(
            "ultravox_response_rejected",
            extra={"reason": "non_json_response", "status_code": resp.status_code},
        )
        raise VendorHTTPError(
            f"Ultravox API returned non-JSON ({resp.status_code})"
        ) from None
    if isinstance(payload, dict) and payload.get("success") is False:
        logger.warning(
            "ultravox_response_rejected",
            extra={"reason": "unsuccessful_response", "status_code": resp.status_code},
        )
        raise VendorHTTPError("Ultravox API reported that the operation failed.")
    return payload


def _validate_page_size(page_size: int) -> int:
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        logger.warning(
            "ultravox_list_rejected",
            extra={"reason": "page_size_out_of_range"},
        )
        raise ArgumentValidationError(
            f"page_size must be between 1 and {MAX_PAGE_SIZE}"
        )
    return page_size


class UltravoxClient:
    def __init__(self):
        api_key = os.environ.get("ULTRAVOX_API_KEY", "")
        if not api_key:
            logger.warning(
                "ultravox_client_rejected",
                extra={"reason": "missing_api_key"},
            )
            raise MissingCredentialsError(
                "No Ultravox API key found. Set ULTRAVOX_API_KEY or run: ultravox-mcp-setup, then restart the MCP server."
            )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-Key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _request(self, method, path, params=None, json_body=None, _rate_retries=0):
        url = f"{BASE_URL}/{path.lstrip('/')}"
        try:
            resp = self.session.request(
                method, url, params=params, json=json_body, timeout=30
            )
        except (requests.Timeout, requests.ConnectionError):
            if method.upper() == "GET":
                message = "Ultravox request timed out or the connection failed. Check connectivity and retry."
            else:
                message = "Ultravox request timed out or the connection failed; the outcome is unknown. Check whether the operation completed before retrying."
            raise VendorHTTPError(message) from None
        if resp.status_code == 401:
            logger.warning(
                "ultravox_request_rejected",
                extra={"reason": "invalid_api_key", "status_code": resp.status_code},
            )
            raise AuthenticationError(
                "Ultravox authorization expired. Re-run ultravox-mcp-setup."
            )
        if resp.status_code == 403:
            raise AuthenticationError(
                "Ultravox access denied: the connected account lacks permission for this action (or the authorization expired; re-run ultravox-mcp-setup if so)."
            )
        if resp.status_code == 429 and _rate_retries < 3:
            wait = _retry_after_seconds(resp)
            spent = getattr(self, "_retry_sleep_budget", 0)
            if wait > 60 - spent:
                raise RateLimitError(
                    f"Ultravox rate limit reached (HTTP 429). Retry after {wait} seconds."
                )
            logger.warning(
                "ultravox_request_rate_limited",
                extra={"retry_after_seconds": wait},
            )
            self._retry_sleep_budget = spent + wait
            try:
                time.sleep(wait)
                return self._request(
                    method,
                    path,
                    params=params,
                    json_body=json_body,
                    _rate_retries=_rate_retries + 1,
                )
            finally:
                if _rate_retries == 0:
                    self._retry_sleep_budget = 0
        if resp.status_code == 204:
            return {"success": True}
        if not resp.ok:
            logger.warning(
                "ultravox_request_rejected",
                extra={
                    "reason": "vendor_error",
                    "status_code": resp.status_code,
                },
            )
            if resp.status_code == 404:
                raise NotFoundError(
                    "Ultravox resource was not found (HTTP 404). Check the supplied identifier."
                )
            if resp.status_code == 429:
                retry_after = _retry_after_seconds(resp)
                raise RateLimitError(
                    f"Ultravox rate limit reached (HTTP 429). Retry after {retry_after} seconds."
                )
            reason = _safe_vendor_reason(resp)
            raise VendorHTTPError(f"Ultravox API error {resp.status_code}: {reason}")
        return _json_response(resp)

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, body=None):
        return self._request("POST", path, json_body=body)

    def delete(self, path):
        return self._request("DELETE", path)

    # -------------------------------------------------------------------------
    # Account
    # -------------------------------------------------------------------------

    def get_account(self):
        """Return account details for the authenticated user."""
        return self.get("/accounts/me")

    # -------------------------------------------------------------------------
    # Calls
    # -------------------------------------------------------------------------

    def list_calls(self, page_size: int = 25, cursor: str = ""):
        """List calls with optional pagination cursor."""
        params: dict[str, object] = {"pageSize": _validate_page_size(page_size)}
        if cursor:
            params["cursor"] = cursor
        return self.get("/calls", params=params)

    def get_call(self, call_id: str):
        """Get a single call by ID."""
        return self.get(f"/calls/{_path_id(call_id, 'call_id')}")

    def create_call(
        self,
        system_prompt: str,
        voice: str = "terrence",
        temperature: float = 0.7,
        first_speaker: str = "FIRST_SPEAKER_AGENT",
        max_duration: str = "600s",
    ):
        """
        Create a new Ultravox call.

        Returns a joinUrl — use your WebSocket/SDK client to join.
        The MCP handles REST only; real-time audio is out of scope.
        """
        body = {
            "systemPrompt": system_prompt,
            "voice": voice,
            "temperature": temperature,
            "firstSpeaker": first_speaker,
            "maxDuration": max_duration,
        }
        return self.post("/calls", body=body)

    def delete_call(self, call_id: str):
        """Delete a call by ID."""
        return self.delete(f"/calls/{_path_id(call_id, 'call_id')}")

    def list_call_messages(self, call_id: str, page_size: int = 50):
        """List messages (transcript) for a call."""
        params = {"pageSize": _validate_page_size(page_size)}
        return self.get(
            f"/calls/{_path_id(call_id, 'call_id')}/messages", params=params
        )

    # -------------------------------------------------------------------------
    # Tools
    # -------------------------------------------------------------------------

    def list_tools(self, page_size: int = 25):
        """List all configured Ultravox tools."""
        params = {"pageSize": _validate_page_size(page_size)}
        return self.get("/tools", params=params)

    def get_tool(self, tool_id: str):
        """Get a single tool by ID."""
        return self.get(f"/tools/{_path_id(tool_id, 'tool_id')}")

    def create_tool(
        self,
        name: str,
        description: str,
        parameters_schema: dict,
        http_config: dict,
    ):
        """
        Create a new Ultravox tool.

        parameters_schema: JSON Schema object for the tool's parameters.
            Converted internally to Ultravox's dynamicParameters format.
        http_config: {"baseUrlPattern": "...", "httpMethod": "..."}.
            Mapped to definition.http.

        The Ultravox API requires all tool config inside a `definition`
        wrapper with a mandatory `modelToolName` field (the name the AI
        model uses when calling the tool).
        """
        validate_http_config(http_config)
        required_set = set(parameters_schema.get("required") or [])
        dynamic_params = [
            {
                "name": param_name,
                "location": "PARAMETER_LOCATION_BODY",
                "schema": param_schema,
                "required": param_name in required_set,
            }
            for param_name, param_schema in (
                parameters_schema.get("properties") or {}
            ).items()
        ]
        body: dict = {
            "name": name,
            "definition": {
                "modelToolName": name,
                "description": description,
                "http": http_config,
            },
        }
        if dynamic_params:
            body["definition"]["dynamicParameters"] = dynamic_params
        return self.post("/tools", body=body)

    def delete_tool(self, tool_id: str):
        """Delete a tool by ID."""
        return self.delete(f"/tools/{_path_id(tool_id, 'tool_id')}")

    # -------------------------------------------------------------------------
    # Voices
    # -------------------------------------------------------------------------

    def list_voices(self, page_size: int = 25):
        """List available Ultravox voices."""
        params = {"pageSize": _validate_page_size(page_size)}
        return self.get("/voices", params=params)


def validate_http_config(http_config):
    """Validate HTTP tool configuration before constructing a credentialed client."""
    if not isinstance(http_config, dict) or set(http_config) - {
        "baseUrlPattern",
        "httpMethod",
    }:
        raise ArgumentValidationError(
            "http_config accepts only baseUrlPattern and httpMethod."
        )
    method = http_config.get("httpMethod", "")
    if not isinstance(method, str) or method not in {
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "HEAD",
        "OPTIONS",
    }:
        raise ArgumentValidationError(
            "httpMethod must be GET, POST, PUT, PATCH, DELETE, HEAD, or OPTIONS."
        )
    try:
        validate_public_https(http_config.get("baseUrlPattern"))
    except ValueError:
        raise ArgumentValidationError(
            "baseUrlPattern must be a public HTTPS URL with a fixed hostname and no userinfo. "
            "Configure ULTRAVOX_ALLOWED_DESTINATION_HOSTS with trusted hosts."
        ) from None
