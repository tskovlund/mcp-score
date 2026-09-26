"""Analysis tools: read from the connected application.

MuseScore reports what sits under its cursor; the tools move the cursor
measure by measure, so a passage comes back as one entry per measure with
the element at the start of that measure. Dorico's Remote Control API has
no cursor: the only thing it can read is the selection's properties.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp_score.bridge.results import (
    CursorInfo,
    CursorPosition,
    Result,
    SelectionProperties,
)
from mcp_score.context import ScoreContext
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


class MeasureContent(Result):
    measure: int
    content: CursorInfo
    """The cursor at the start of the measure and the element there."""


class Passage(Result):
    start_measure: int
    end_measure: int
    staff: int | None
    elements: list[MeasureContent]
    warning: str | None = None
    """Why the application could not read more, when it could not."""


class Selected(CursorPosition):
    """A measure of a staff is selected in the application."""

    warning: str | None = None


@score_tool
async def read_passage(
    context: ScoreContext,
    start_measure: int,
    end_measure: int,
    staff: int | None = None,
) -> Passage:
    """Read a range of measures in the live score, one entry per measure.

    For each measure MuseScore reports the cursor position (measure, staff,
    voice, beat, tick) and the element at the start of the measure on that
    staff: its type, and for a note or chord its pitches and duration. It
    does not list every element in the measure. Not available with Dorico,
    which cannot read score content.

    Args:
        start_measure: First measure to read (1-indexed).
        end_measure: Last measure to read (inclusive, 1-indexed).
        staff: Staff to read (0-indexed). Omit to read the current staff.
    """
    bridge = require_bridge(context)
    require_measure_range(start_measure, end_measure)

    elements: list[MeasureContent] = []
    for measure in range(start_measure, end_measure + 1):
        await navigate(bridge, measure, staff)
        content = await bridge.get_cursor_info()
        elements.append(MeasureContent(measure=measure, content=content))

    return Passage(
        start_measure=start_measure,
        end_measure=end_measure,
        staff=staff,
        elements=elements,
        warning=bridge.content_reading_limitation,
    )


@score_tool
async def get_measure_content(
    context: ScoreContext, measure: int, staff: int = 0
) -> Selected:
    """Select one measure of one staff in MuseScore and report the selection.

    The selection becomes visible in the score, ready for a manual edit;
    the result names the selected measure and staff, not its content (use
    read_passage for that). Not available with Dorico, which cannot move to
    a staff or select a measure.

    Args:
        measure: Measure number (1-indexed).
        staff: Staff index (0-indexed, default: 0).
    """
    bridge = require_bridge(context)
    require_measure(measure)
    await navigate(bridge, measure, staff)
    selected = await bridge.select_measure()
    return Selected(
        measure=selected.measure,
        staff=selected.staff,
        warning=bridge.content_reading_limitation,
    )


@score_tool
async def get_selection_properties(context: ScoreContext) -> SelectionProperties:
    """Get properties of the current selection in the connected application.

    MuseScore reports the cursor position (measure, beat, staff, element).
    Dorico reports the names, types and values of every property of the
    selected items, which is the closest its API gets to reading the score.
    """
    bridge = require_bridge(context)
    properties = await bridge.get_properties()
    return properties.model_copy(update={"warning": bridge.content_reading_limitation})


def register(server: MCPServer) -> None:
    for tool in (read_passage, get_measure_content, get_selection_properties):
        server.tool()(tool)
