"""Connection tools — manage bridges to score notation applications."""

from mcp_score.app import mcp
from mcp_score.bridge import (
    get_active_bridge,
    get_dorico_bridge,
    get_musescore_bridge,
    set_active_bridge,
)
from mcp_score.tools import NOT_CONNECTED, connected_bridge, to_json

__all__: list[str] = []


# ── MuseScore ────────────────────────────────────────────────────────


@mcp.tool()
async def connect_to_musescore(host: str = "localhost", port: int = 8765) -> str:
    """Connect to a running MuseScore instance.

    The MuseScore MCP Score Bridge plugin must be running.

    Args:
        host: WebSocket host (default: localhost).
        port: WebSocket port (default: 8765).
    """
    # Disconnect any existing active bridge first.
    current = get_active_bridge()
    if current is not None and current.is_connected:
        await current.disconnect()
        set_active_bridge(None)

    bridge = get_musescore_bridge()
    bridge.host = host
    bridge.port = port
    connected = await bridge.connect()
    if connected:
        set_active_bridge(bridge)
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
    bridge = get_musescore_bridge()
    await bridge.disconnect()
    if get_active_bridge() is bridge:
        set_active_bridge(None)
    return to_json(
        {
            "success": True,
            "message": "Disconnected from MuseScore.",
        }
    )


# ── Dorico ───────────────────────────────────────────────────────────


@mcp.tool()
async def connect_to_dorico(host: str = "localhost", port: int = 4560) -> str:
    """Connect to a running Dorico instance via its Remote Control API.

    Dorico 4+ has a built-in WebSocket server (no plugin needed).
    The port is configurable in Dorico's preferences.

    Args:
        host: WebSocket host (default: localhost).
        port: WebSocket port (default: 4560, Dorico's default).
    """
    # Disconnect any existing active bridge first.
    current = get_active_bridge()
    if current is not None and current.is_connected:
        await current.disconnect()
        set_active_bridge(None)

    bridge = get_dorico_bridge()
    bridge.host = host
    bridge.port = port
    connected = await bridge.connect()
    if connected:
        set_active_bridge(bridge)
        return to_json(
            {
                "success": True,
                "message": f"Connected to Dorico at ws://{host}:{port}.",
            }
        )
    return to_json(
        {
            "error": f"Could not connect to Dorico at ws://{host}:{port}. "
            "Is Dorico running with Remote Control enabled?"
        }
    )


@mcp.tool()
async def disconnect_from_dorico() -> str:
    """Disconnect from Dorico."""
    bridge = get_dorico_bridge()
    await bridge.disconnect()
    if get_active_bridge() is bridge:
        set_active_bridge(None)
    return to_json(
        {
            "success": True,
            "message": "Disconnected from Dorico.",
        }
    )


# ── Shared tools (work with any connected application) ──────────────


@mcp.tool()
async def get_live_score_info() -> str:
    """Get information about the currently open score.

    Requires an active connection — use connect_to_musescore or
    connect_to_dorico first.
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    result = await bridge.get_score()
    return to_json(result)


@mcp.tool()
async def ping_score_app() -> str:
    """Check if the connected score application is responsive.

    Works with any connected application (MuseScore or Dorico).
    Does NOT auto-connect — returns an error if not already connected.
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    alive = await bridge.ping()
    if alive:
        return to_json(
            {
                "success": True,
                "message": f"{bridge.application_name} is responsive.",
            }
        )
    return to_json({"error": f"{bridge.application_name} is not responding."})
