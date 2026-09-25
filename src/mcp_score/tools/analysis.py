"""Analysis tools: read musical content from the connected application."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp_score.bridge import CommandResult
from mcp_score.tools import (
    navigate,
    require_bridge,
    require_measure,
    require_measure_range,
    score_tool,
)

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

__all__ = ["register"]


def _with_limitation(result: CommandResult, limitation: str | None) -> CommandResult:
    """Attach the application's content-reading caveat, when it has one."""
    if limitation is not None:
        result["warning"] = limitation
    return result


@score_tool
async def read_passage(
    start_measure: int, end_measure: int, staff: int | None = None
) -> CommandResult:
    """Read the content of a range of measures in the live score.

    Returns what is at the cursor in each measure: notes, rests and other
    elements. MuseScore gives full note content; Dorico only reports its
    application status (see the warning in the result).

    Args:
        start_measure: First measure to read (1-indexed).
        end_measure: Last measure to read (inclusive, 1-indexed).
        staff: Staff to read (0-indexed). Omit to read the current staff.
    """
    bridge = require_bridge()
    require_measure_range(start_measure, end_measure)

    elements: list[dict[str, Any]] = []
    for measure in range(start_measure, end_measure + 1):
        await navigate(bridge, measure, staff)
        elements.append({"measure": measure, "content": await bridge.get_cursor_info()})

    return _with_limitation(
        {
            "success": True,
            "start_measure": start_measure,
            "end_measure": end_measure,
            "staff": staff,
            "elements": elements,
        },
        bridge.content_reading_limitation,
    )


@score_tool
async def get_measure_content(measure: int, staff: int = 0) -> CommandResult:
    """Select one measure of one staff in the live score and report it.

    Args:
        measure: Measure number (1-indexed).
        staff: Staff index (0-indexed, default: 0).
    """
    bridge = require_bridge()
    require_measure(measure)
    await navigate(bridge, measure, staff)
    return _with_limitation(
        await bridge.select_measure(), bridge.content_reading_limitation
    )


@score_tool
async def get_selection_properties() -> CommandResult:
    """Get properties of the current selection in the connected application.

    MuseScore reports the cursor position (measure, beat, staff, element).
    Dorico reports the names, types and values of every property of the
    selected items, which is the closest its API gets to reading the score.
    """
    return await require_bridge().get_properties()


def register(server: MCPServer) -> None:
    for tool in (read_passage, get_measure_content, get_selection_properties):
        server.tool()(tool)
