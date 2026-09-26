"""Connection tools: which application the server talks to.

Each application has its own connect and disconnect pair, and connecting
to one disconnects the other. The information and ping tools work with
whichever application is connected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp_score.bridge.dorico import DEFAULT_PORT as DORICO_DEFAULT_PORT
from mcp_score.bridge.musescore import DEFAULT_PORT as MUSESCORE_DEFAULT_PORT
from mcp_score.bridge.results import Result, ScoreInfo
from mcp_score.bridge.websocket import DEFAULT_HOST
from mcp_score.context import ScoreContext, registry_of
from mcp_score.tools import ToolError, require_bridge, score_tool

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from mcp_score.bridge import ScoreBridge, WebSocketBridge

__all__ = ["register"]

MUSESCORE_CONNECT_HINT = (
    "Is the MCP Score Bridge plugin running with its window open? "
    "The plugin requires MuseScore Studio 4.4.2 or later."
)
DORICO_CONNECT_HINT = "Is Dorico running with Remote Control enabled?"


class Connected(Result):
    application: str
    uri: str


class Disconnected(Result):
    application: str


class Responsive(Result):
    """The connected application answered a ping."""

    application: str


async def _connect(
    context: ScoreContext, bridge: WebSocketBridge, host: str, port: int, hint: str
) -> Connected:
    """Point *bridge* at host and port and make it the active connection."""
    bridge.host = host
    bridge.port = port
    if not await registry_of(context).activate(bridge):
        raise ToolError(
            f"Could not connect to {bridge.application_name} at {bridge.uri}. {hint}"
        )
    return Connected(application=bridge.application_name, uri=bridge.uri)


async def _disconnect(context: ScoreContext, bridge: ScoreBridge) -> Disconnected:
    await registry_of(context).deactivate(bridge)
    return Disconnected(application=bridge.application_name)


@score_tool
async def connect_to_musescore(
    context: ScoreContext, host: str = DEFAULT_HOST, port: int = MUSESCORE_DEFAULT_PORT
) -> Connected:
    """Connect to a running MuseScore Studio (4.4.2 or later).

    The MCP Score Bridge plugin must be running in MuseScore with its
    window open. Connecting disconnects any other application.

    Args:
        host: WebSocket host (default: localhost).
        port: WebSocket port (default: 8765).
    """
    return await _connect(
        context, registry_of(context).musescore, host, port, MUSESCORE_CONNECT_HINT
    )


@score_tool
async def disconnect_from_musescore(context: ScoreContext) -> Disconnected:
    """Disconnect from MuseScore."""
    return await _disconnect(context, registry_of(context).musescore)


@score_tool
async def connect_to_dorico(
    context: ScoreContext, host: str = DEFAULT_HOST, port: int = DORICO_DEFAULT_PORT
) -> Connected:
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
    return await _connect(
        context, registry_of(context).dorico, host, port, DORICO_CONNECT_HINT
    )


@score_tool
async def disconnect_from_dorico(context: ScoreContext) -> Disconnected:
    """Disconnect from Dorico."""
    return await _disconnect(context, registry_of(context).dorico)


@score_tool
async def get_live_score_info(context: ScoreContext) -> ScoreInfo:
    """Get information about the score open in MuseScore.

    Title, parts, measure count and the opening key and time signatures.
    Not available with Dorico, whose API cannot describe the score.
    """
    return await require_bridge(context).get_score()


@score_tool
async def ping_score_app(context: ScoreContext) -> Responsive:
    """Check whether the connected application responds. Does not connect."""
    bridge = require_bridge(context)
    if not await bridge.ping():
        raise ToolError(f"{bridge.application_name} is not responding.")
    return Responsive(application=bridge.application_name)


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
