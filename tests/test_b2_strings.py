"""The setup wizard prints the same Claude Desktop config the README shows."""

from __future__ import annotations

import re
from pathlib import Path

from ultravox_mcp.setup import setup

README = Path(__file__).resolve().parent.parent / "README.md"


def _readme_claude_desktop_json() -> str:
    text = README.read_text(encoding="utf-8")
    section = text.split("## Usage with Claude Desktop", 1)[1]
    match = re.search(r"```json\n(.*?)\n```", section, re.DOTALL)
    assert match is not None
    return match.group(1)


def test_setup_prints_the_readme_claude_desktop_config(monkeypatch, capsys) -> None:
    monkeypatch.setattr("ultravox_mcp.setup.verify.verify", lambda: True)

    setup._run_verify()
    output = capsys.readouterr().out

    assert _readme_claude_desktop_json() in output
    assert _readme_claude_desktop_json() == setup.CLAUDE_DESKTOP_CONFIG
    assert '"command": "uv"' in output
    assert '"--directory", "/absolute/path/to/ultravox-mcp", "ultravox-mcp"' in output
    assert (
        "Replace /absolute/path/to/ultravox-mcp with the path of your clone" in output
    )
    # The old snippet was a partial, bare-command fragment that the README does not show.
    assert '"command": "ultravox-mcp"' not in output
