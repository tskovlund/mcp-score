"""What every MCP tool module shares.

A tool is a plain async function that returns a :class:`CommandResult`
and raises :class:`ToolError` when it cannot proceed. :func:`score_tool`
turns the error into an ``{"error": ...}`` result, so error handling
lives here once instead of in every tool, and the MCP server delivers the
dict to the model as JSON text and as structured content. Each module
exposes ``register(server)``, which adds its tools to the server; nothing
is registered by importing a module.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Protocol

from mcp_score.bridge import registry

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from mcp.server.mcpserver import MCPServer

    from mcp_score.bridge import CommandResult, ScoreBridge

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


class ToolError(Exception):
    """A tool cannot do what was asked; the message goes to the model."""

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def as_result(self) -> CommandResult:
        return {"error": self.message, **self.details}


class ToolModule(Protocol):
    """A module of tools: ``register(server)`` adds them to the server."""

    def register(self, server: MCPServer) -> None: ...


type Tool[**P] = Callable[P, Awaitable[CommandResult]]
"""An MCP tool: an async function whose result is a :class:`CommandResult`."""


def score_tool[**P](tool: Tool[P]) -> Tool[P]:
    """Deliver a tool's :class:`ToolError` as an ``{"error": ...}`` result.

    The wrapped function keeps its signature, which is what the MCP server
    reads to describe the tool's parameters and result to the model.
    """

    @functools.wraps(tool)
    async def deliver(*args: P.args, **kwargs: P.kwargs) -> CommandResult:
        try:
            return await tool(*args, **kwargs)
        except ToolError as error:
            return error.as_result()

    return deliver


def succeeded(message: str, **fields: Any) -> CommandResult:
    """A success result with a message for the model."""
    return {"success": True, "message": message, **fields}


def require_bridge() -> ScoreBridge:
    """The connected bridge.

    Raises:
        ToolError: When no application is connected.
    """
    bridge = registry.connected()
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
        ToolError: With the application's reply when it refuses to move,
            so a command never runs at the wrong position.
    """
    reply = await bridge.go_to_measure(measure)
    if "error" in reply:
        raise ToolError(str(reply["error"]))
    if staff is not None:
        reply = await bridge.go_to_staff(staff)
        if "error" in reply:
            raise ToolError(str(reply["error"]))
