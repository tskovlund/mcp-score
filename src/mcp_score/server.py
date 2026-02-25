"""MCP server entry point."""

import sys

import mcp_score.tools.analysis as _analysis  # noqa: F401
import mcp_score.tools.connection as _connection  # noqa: F401
import mcp_score.tools.generation as _generation  # noqa: F401
import mcp_score.tools.manipulation as _manipulation  # noqa: F401
from mcp_score.app import mcp

# Prevent pyright from complaining about "unused" side-effect imports.
_TOOL_MODULES = [_analysis, _connection, _generation, _manipulation]

__all__ = ["mcp", "main"]


def main() -> None:
    """Run the MCP server."""
    sys.stderr.write("mcp-score server starting...\n")
    sys.stderr.flush()
    mcp.run()
