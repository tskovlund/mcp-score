"""Connection tools — manage the WebSocket bridge to MuseScore."""

import json
from typing import Any

from mcp_score.app import mcp
from mcp_score.bridge import get_bridge

__all__: list[str] = []


def _result(data: dict[str, Any]) -> str:
    """Serialize a result dict to JSON."""
    return json.dumps(data)


@mcp.tool()
async def connect_to_musescore(host: str = "localhost", port: int = 8765) -> str:
    """Connect to a running MuseScore instance.

    The MuseScore MCP Score Bridge plugin must be running.

    Args:
        host: WebSocket host (default: localhost).
        port: WebSocket port (default: 8765).
    """
    bridge = get_bridge()
    bridge.host = host
    bridge.port = port
    connected = await bridge.connect()
    if connected:
        return _result(
            {
                "success": True,
                "message": f"Connected to MuseScore at ws://{host}:{port}.",
            }
        )
    return _result(
        {
            "error": f"Could not connect to MuseScore at ws://{host}:{port}. "
            "Is the MCP Score Bridge plugin running?"
        }
    )


@mcp.tool()
async def disconnect_from_musescore() -> str:
    """Disconnect from MuseScore."""
    bridge = get_bridge()
    await bridge.disconnect()
    return _result(
        {
            "success": True,
            "message": "Disconnected from MuseScore.",
        }
    )


@mcp.tool()
async def get_live_score_info() -> str:
    """Get information about the currently open score in MuseScore."""
    bridge = get_bridge()
    result = await bridge.get_score()
    return _result(result)


@mcp.tool()
async def ping_musescore() -> str:
    """Check if MuseScore is connected and responsive."""
    bridge = get_bridge()
    alive = await bridge.ping()
    if alive:
        return _result({"success": True, "message": "MuseScore is responsive."})
    return _result({"error": "MuseScore is not responding."})
