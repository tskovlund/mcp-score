"""Connection tools — manage the WebSocket bridge to MuseScore."""

from mcp_score.app import mcp
from mcp_score.bridge import get_bridge
from mcp_score.tools import NOT_CONNECTED, connected_bridge, to_json

__all__: list[str] = []


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
        return to_json(
            {
                "success": True,
                "message": f"Connected to MuseScore at ws://{host}:{port}.",
            }
        )
    return to_json(
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
    return to_json(
        {
            "success": True,
            "message": "Disconnected from MuseScore.",
        }
    )


@mcp.tool()
async def get_live_score_info() -> str:
    """Get information about the currently open score in MuseScore.

    Requires an active connection — use connect_to_musescore first.
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    result = await bridge.get_score()
    return to_json(result)


@mcp.tool()
async def ping_musescore() -> str:
    """Check if MuseScore is connected and responsive.

    Does NOT auto-connect — returns an error if not already connected.
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    alive = await bridge.ping()
    if alive:
        return to_json({"success": True, "message": "MuseScore is responsive."})
    return to_json({"error": "MuseScore is not responding."})
