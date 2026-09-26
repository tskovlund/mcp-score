"""The MCP server: one place that assembles the tool modules and their state."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from mcp.server.mcpserver import MCPServer

from mcp_score.bridge import BridgeRegistry
from mcp_score.context import AppState
from mcp_score.tools import ToolModule, analysis, connection, generate, manipulation
from mcp_score.tools import render as render_tools

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

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


def create_server(registry: BridgeRegistry | None = None) -> MCPServer[AppState]:
    """Build a server with every tool registered.

    The tools reach *registry* (a fresh one by default) through the context
    the SDK injects, so a test can build a server around any registry.
    """
    state = AppState(registry if registry is not None else BridgeRegistry())

    @asynccontextmanager
    async def lifespan(_server: MCPServer[AppState]) -> AsyncGenerator[AppState]:
        yield state

    server = MCPServer(SERVER_NAME, lifespan=lifespan)
    for module in TOOL_MODULES:
        module.register(server)
    return server


def main() -> None:
    """Serve over stdio until the client disconnects."""
    logging.basicConfig(level=logging.INFO)
    logger.info("%s server starting", SERVER_NAME)
    create_server().run()
