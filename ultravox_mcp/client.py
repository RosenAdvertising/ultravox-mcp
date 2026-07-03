#!/usr/bin/env python3
"""Ultravox REST API client — handles auth, retries, and all endpoint calls."""

import os
import sys
import time

import requests

from ultravox_mcp import credentials

BASE_URL = "https://api.ultravox.ai/api"

# Resolve credentials through the pluggable store (OS keyring -> .env file).
credentials.load_into_environ(["ULTRAVOX_API_KEY"])


def _retry_after_seconds(resp, default=10):
    try:
        return int(resp.headers.get("Retry-After", default))
    except (TypeError, ValueError):
        return default


def _json_response(resp):
    try:
        return resp.json()
    except ValueError:
        raise RuntimeError(
            f"Ultravox API returned non-JSON ({resp.status_code}): {resp.text[:200]}"
        )


class UltravoxClient:
    def __init__(self):
        api_key = os.environ.get("ULTRAVOX_API_KEY", "")
        if not api_key:
            raise RuntimeError("No Ultravox API key found. Run: ultravox-mcp-setup")
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
        resp = self.session.request(method, url, params=params, json=json_body)
        if resp.status_code == 401:
            raise RuntimeError("Ultravox API key invalid. Run: ultravox-mcp-setup")
        if resp.status_code == 429 and _rate_retries < 3:
            wait = _retry_after_seconds(resp)
            print(f"Rate limited. Waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            return self._request(
                method,
                path,
                params=params,
                json_body=json_body,
                _rate_retries=_rate_retries + 1,
            )
        if resp.status_code == 204:
            return {"success": True}
        if not resp.ok:
            raise RuntimeError(
                f"Ultravox API error {resp.status_code}: {resp.text[:400]}"
            )
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
        params: dict[str, object] = {"pageSize": page_size}
        if cursor:
            params["cursor"] = cursor
        return self.get("/calls", params=params)

    def get_call(self, call_id: str):
        """Get a single call by ID."""
        return self.get(f"/calls/{call_id}")

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
        return self.delete(f"/calls/{call_id}")

    def list_call_messages(self, call_id: str, page_size: int = 50):
        """List messages (transcript) for a call."""
        params = {"pageSize": page_size}
        return self.get(f"/calls/{call_id}/messages", params=params)

    # -------------------------------------------------------------------------
    # Tools
    # -------------------------------------------------------------------------

    def list_tools(self, page_size: int = 25):
        """List all configured Ultravox tools."""
        params = {"pageSize": page_size}
        return self.get("/tools", params=params)

    def get_tool(self, tool_id: str):
        """Get a single tool by ID."""
        return self.get(f"/tools/{tool_id}")

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
        return self.delete(f"/tools/{tool_id}")

    # -------------------------------------------------------------------------
    # Voices
    # -------------------------------------------------------------------------

    def list_voices(self, page_size: int = 25):
        """List available Ultravox voices."""
        params = {"pageSize": page_size}
        return self.get("/voices", params=params)
