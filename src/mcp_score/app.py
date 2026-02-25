"""FastMCP application instance — shared by all tool modules."""

from mcp.server.fastmcp import FastMCP

__all__ = ["mcp"]

mcp = FastMCP("mcp-score")
