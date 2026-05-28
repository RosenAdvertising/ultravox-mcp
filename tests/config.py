from pathlib import Path

from mcp_test_kit.config import (
    ResilienceConfig,
    SeedConfig,
    SpecCheckConfig,
    SmokeConfig,
    ToolkitConfig,
    WriteConfig,
    WriteStep,
)
from ultravox_mcp.server import mcp

_TESTS_DIR = Path(__file__).parent

TOOLKIT = ToolkitConfig(
    mcp_server=mcp,
    seed=SeedConfig(seed_script=_TESTS_DIR / "seed_data.py"),
    spec_check=SpecCheckConfig(
        endpoints_path=_TESTS_DIR.parent / "endpoints.yaml",
        openapi_path=_TESTS_DIR.parent
        / "endpoints.yaml",  # dummy — contract tier skipped
    ),
    source_path=_TESTS_DIR.parent / "ultravox_mcp",
    module_path="ultravox_mcp",
    server_path=_TESTS_DIR.parent / "ultravox_mcp" / "server.py",
    resilience=ResilienceConfig(tools_to_timeout_test=["list_calls"]),
    skip_tiers={
        "contract": "no published OpenAPI spec for Ultravox API",
    },
    smoke=SmokeConfig(
        server=mcp,
        # Zero-arg read probes against live API.
        # Note: get_account returns 404 on this account tier — omitted.
        read_tools=["list_calls", "list_tools", "list_voices"],
    ),
    write=WriteConfig(
        server=mcp,
        # get_account returns 404 on trial tier. list_tools shows 8 account-specific
        # tools — sufficient identity signal to confirm the right sandbox.
        identity_tool="list_tools",
        steps=[
            # Tool CRUD — fully reversible, no lingering state.
            WriteStep(
                tool="create_tool",
                args={
                    "name": "mcp_test_kit_probe",
                    "description": "[mcp-test-kit write test — delete immediately]",
                    "parameters_schema": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "Test message",
                            }
                        },
                        "required": [],
                    },
                    "http_config": {
                        "baseUrlPattern": "https://httpbin.org/post",
                        "httpMethod": "POST",
                    },
                },
                state_key="tool_id",
                # Ultravox uses toolId at top level (not data.id)
                extract=lambda r: r.get("toolId"),
            ),
            WriteStep(
                tool="delete_tool",
                args=lambda s: {"tool_id": s["tool_id"]},
                skip_if_missing="tool_id",
                cleanup=True,
            ),
            # create_call is verified separately (manual test confirmed callId
            # field and create works). Excluded from write tier because the
            # Ultravox API returns 425 when deleting ongoing/unbilled calls —
            # there is no immediate cleanup path. Calls expire at maxDuration.
        ],
    ),
)
