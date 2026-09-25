"""MCPServer application instance — shared by all tool modules."""

from mcp.server.mcpserver import MCPServer

__all__ = ["mcp"]

mcp = MCPServer("mcp-score")
