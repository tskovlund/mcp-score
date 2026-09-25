"""The MCP server: one place that assembles the tool modules."""

from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer

from mcp_score.tools import ToolModule, analysis, connection, generate, manipulation
from mcp_score.tools import render as render_tools

__all__ = ["SERVER_NAME", "create_server", "main"]

SERVER_NAME = "mcp-score"

TOOL_MODULES: tuple[ToolModule, ...] = (
    connection,
    analysis,
    manipulation,
    generate,
    render_tools,
)
"""Every module whose tools the server offers, in the order they register."""

logger = logging.getLogger(__name__)


def create_server() -> MCPServer:
    """Build a server with every tool registered."""
    server = MCPServer(SERVER_NAME)
    for module in TOOL_MODULES:
        module.register(server)
    return server


def main() -> None:
    """Serve over stdio until the client disconnects."""
    logging.basicConfig(level=logging.INFO)
    logger.info("%s server starting", SERVER_NAME)
    create_server().run()
