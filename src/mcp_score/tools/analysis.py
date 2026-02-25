"""Score analysis tools — read and understand musical content."""

import json
from typing import Any

from mcp_score.app import mcp
from mcp_score.bridge import get_bridge

__all__: list[str] = []


def _result(data: dict[str, Any]) -> str:
    """Serialize a result dict to JSON."""
    return json.dumps(data)


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
    bridge = get_bridge()
    if not bridge.is_connected:
        return _result(
            {"error": "Not connected to MuseScore. Use connect_to_musescore first."}
        )

    # Navigate to start and read elements for each measure.
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

    return _result(
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
    bridge = get_bridge()
    if not bridge.is_connected:
        return _result(
            {"error": "Not connected to MuseScore. Use connect_to_musescore first."}
        )

    await bridge.go_to_measure(measure)
    await bridge.go_to_staff(staff)

    # Select the full measure to get all elements.
    result = await bridge.send_command("selectCurrentMeasure")
    return _result(result)
