"""Score analysis tools — read and understand musical content."""

from typing import Any

from mcp_score.app import mcp
from mcp_score.tools import NOT_CONNECTED, check_measure, connected_bridge, to_json

__all__: list[str] = []


@mcp.tool()
async def read_passage(
    start_measure: int,
    end_measure: int,
    staff: int | None = None,
) -> str:
    """Read musical content from a range of measures in the live MuseScore score.

    Returns notes, rests, and musical elements in the specified range.

    Args:
        start_measure: First measure to read (1-indexed).
        end_measure: Last measure to read (inclusive, 1-indexed).
        staff: Staff index to read (0-indexed). If not provided, reads all staves.
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    if err := check_measure(start_measure, "start_measure"):
        return err
    if end_measure < start_measure:
        return to_json({"error": "end_measure must be >= start_measure."})

    elements: list[dict[str, Any]] = []
    for measure_num in range(start_measure, end_measure + 1):
        await bridge.go_to_measure(measure_num)
        if staff is not None:
            await bridge.go_to_staff(staff)
        cursor_info = await bridge.get_cursor_info()
        elements.append(
            {
                "measure": measure_num,
                "content": cursor_info,
            }
        )

    return to_json(
        {
            "success": True,
            "start_measure": start_measure,
            "end_measure": end_measure,
            "staff": staff,
            "elements": elements,
        }
    )


@mcp.tool()
async def get_measure_content(measure: int, staff: int = 0) -> str:
    """Read the content of a specific measure and staff from MuseScore.

    Args:
        measure: Measure number (1-indexed).
        staff: Staff index (0-indexed, default: 0).
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    if err := check_measure(measure):
        return err

    await bridge.go_to_measure(measure)
    await bridge.go_to_staff(staff)

    result = await bridge.send_command("selectCurrentMeasure")
    return to_json(result)
