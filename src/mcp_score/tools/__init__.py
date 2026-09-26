"""The MCP tools, one module per category.

A tool is a plain async function returning a :class:`CommandResult`; the
shared plumbing (``ToolError``, the ``score_tool`` decorator and the
precondition guards) lives in :mod:`mcp_score.tools.base`. Each category
module exposes ``register(server)``, which adds its tools to the server;
nothing is registered by importing a module.
"""

from mcp_score.tools.base import (
    NOT_CONNECTED,
    Tool,
    ToolError,
    ToolModule,
    navigate,
    require_bridge,
    require_measure,
    require_measure_range,
    score_tool,
    succeeded,
)

__all__ = [
    "NOT_CONNECTED",
    "Tool",
    "ToolError",
    "ToolModule",
    "navigate",
    "require_bridge",
    "require_measure",
    "require_measure_range",
    "score_tool",
    "succeeded",
]
