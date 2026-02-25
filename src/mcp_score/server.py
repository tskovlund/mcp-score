"""MCP server entry point."""

import sys

from mcp.server.fastmcp import FastMCP

__all__ = ["mcp", "main"]

mcp = FastMCP("mcp-score")


def main() -> None:
    """Run the MCP server."""
    sys.stderr.write("mcp-score server starting...\n")
    sys.stderr.flush()
    mcp.run()
