"""What every tool module shares.

A tool raises the MCP SDK's :class:`ToolError` when it cannot proceed,
and the server reports it to the model as a tool error. An application's
refusal reaches a tool as a :class:`BridgeError`; :func:`score_tool`
reports it the same way, so no tool handles errors itself. Tools that
talk to an application take the server's :class:`ScoreContext` first,
which the MCP SDK injects; the ``require_*`` guards check the common
preconditions and :func:`navigate` moves the application's cursor before
an edit.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Protocol

from mcp.server.mcpserver.exceptions import ToolError

from mcp_score.bridge import BridgeError
from mcp_score.context import registry_of

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from mcp.server.mcpserver import MCPServer

    from mcp_score.bridge import CommandResult, ScoreBridge
    from mcp_score.context import ScoreContext

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

NOT_CONNECTED = (
    "Not connected to any score application. "
    "Use connect_to_musescore or connect_to_dorico first."
)


class ToolModule(Protocol):
    """A module of tools: ``register(server)`` adds them to the server."""

    def register(self, server: MCPServer) -> None: ...


type Tool[**P] = Callable[P, Awaitable[CommandResult]]
"""An MCP tool: an async function whose result is a :class:`CommandResult`."""


def score_tool[**P](tool: Tool[P]) -> Tool[P]:
    """Report an application's refusal (:class:`BridgeError`) as a tool error.

    The wrapped function keeps its signature, which is what the MCP server
    reads to describe the tool's parameters and result to the model.
    """

    @functools.wraps(tool)
    async def deliver(*args: P.args, **kwargs: P.kwargs) -> CommandResult:
        try:
            return await tool(*args, **kwargs)
        except BridgeError as error:
            raise ToolError(error.message) from error

    return deliver


def succeeded(message: str, **fields: Any) -> CommandResult:
    """A success result with a message for the model."""
    return {"success": True, "message": message, **fields}


def require_bridge(context: ScoreContext) -> ScoreBridge:
    """The connected bridge.

    Raises:
        ToolError: When no application is connected.
    """
    bridge = registry_of(context).connected()
    if bridge is None:
        raise ToolError(NOT_CONNECTED)
    return bridge


def require_measure(measure: int, name: str = "measure") -> None:
    """Validate a 1-indexed measure number.

    Raises:
        ToolError: When it is below 1.
    """
    if measure < 1:
        raise ToolError(f"{name} must be >= 1.")


def require_measure_range(start_measure: int, end_measure: int) -> None:
    """Validate an inclusive, 1-indexed measure range.

    Raises:
        ToolError: When the range is empty or starts below 1.
    """
    require_measure(start_measure, "start_measure")
    if end_measure < start_measure:
        raise ToolError("end_measure must be >= start_measure.")


async def navigate(bridge: ScoreBridge, measure: int, staff: int | None = None) -> None:
    """Move the application's cursor to *measure* (and *staff*, if given).

    Raises:
        BridgeError: When the application refuses to move, so a command
            never runs at the wrong position.
    """
    await bridge.go_to_measure(measure)
    if staff is not None:
        await bridge.go_to_staff(staff)
