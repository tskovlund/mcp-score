"""Connection tools: which application the server talks to.

Each application has its own connect and disconnect pair, and connecting
to one disconnects the other. The information and ping tools work with
whichever application is connected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp_score.bridge import CommandResult, ScoreBridge, WebSocketBridge, registry
from mcp_score.bridge.dorico import DEFAULT_PORT as DORICO_DEFAULT_PORT
from mcp_score.bridge.musescore import DEFAULT_PORT as MUSESCORE_DEFAULT_PORT
from mcp_score.bridge.websocket import DEFAULT_HOST
from mcp_score.tools import (
    ToolError,
    require_bridge,
    score_tool,
    succeeded,
)

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

__all__ = ["register"]

MUSESCORE_CONNECT_HINT = (
    "Is the MCP Score Bridge plugin running with its window open? "
    "The plugin requires MuseScore Studio 4.4.2 or later."
)
DORICO_CONNECT_HINT = "Is Dorico running with Remote Control enabled?"


async def _connect(
    bridge: WebSocketBridge, host: str, port: int, hint: str
) -> CommandResult:
    """Point *bridge* at host and port and make it the active connection."""
    bridge.host = host
    bridge.port = port
    if not await registry.activate(bridge):
        raise ToolError(
            f"Could not connect to {bridge.application_name} at ws://{host}:{port}. "
            f"{hint}"
        )
    return succeeded(f"Connected to {bridge.application_name} at ws://{host}:{port}.")


async def _disconnect(bridge: ScoreBridge) -> CommandResult:
    await registry.deactivate(bridge)
    return succeeded(f"Disconnected from {bridge.application_name}.")


@score_tool
async def connect_to_musescore(
    host: str = DEFAULT_HOST, port: int = MUSESCORE_DEFAULT_PORT
) -> CommandResult:
    """Connect to a running MuseScore Studio (4.4.2 or later).

    The MCP Score Bridge plugin must be running in MuseScore with its
    window open. Connecting disconnects any other application.

    Args:
        host: WebSocket host (default: localhost).
        port: WebSocket port (default: 8765).
    """
    return await _connect(registry.musescore, host, port, MUSESCORE_CONNECT_HINT)


@score_tool
async def disconnect_from_musescore() -> CommandResult:
    """Disconnect from MuseScore."""
    return await _disconnect(registry.musescore)


@score_tool
async def connect_to_dorico(
    host: str = DEFAULT_HOST, port: int = DORICO_DEFAULT_PORT
) -> CommandResult:
    """Connect to a running Dorico via its Remote Control API (experimental).

    Dorico support is experimental: the Remote Control API is undocumented,
    command-only (it cannot read note content), and this bridge has not
    been verified against a running Dorico. Dorico 4 and later serve the
    API without a plugin; the port is set in Dorico's preferences.
    Connecting disconnects any other application.

    Args:
        host: WebSocket host (default: localhost).
        port: WebSocket port (default: 4560, Dorico's default).
    """
    return await _connect(registry.dorico, host, port, DORICO_CONNECT_HINT)


@score_tool
async def disconnect_from_dorico() -> CommandResult:
    """Disconnect from Dorico."""
    return await _disconnect(registry.dorico)


@score_tool
async def get_live_score_info() -> CommandResult:
    """Get information about the score open in the connected application.

    Requires an active connection (connect_to_musescore or connect_to_dorico).
    """
    return await require_bridge().get_score()


@score_tool
async def ping_score_app() -> CommandResult:
    """Check whether the connected application responds. Does not connect."""
    bridge = require_bridge()
    if not await bridge.ping():
        raise ToolError(f"{bridge.application_name} is not responding.")
    return succeeded(f"{bridge.application_name} is responsive.")


def register(server: MCPServer) -> None:
    for tool in (
        connect_to_musescore,
        disconnect_from_musescore,
        connect_to_dorico,
        disconnect_from_dorico,
        get_live_score_info,
        ping_score_app,
    ):
        server.tool()(tool)
