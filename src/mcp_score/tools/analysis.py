"""Score analysis tools — read and understand musical content."""

from __future__ import annotations

from typing import Any

from mcp_score.app import mcp
from mcp_score.bridge.musescore import MuseScoreBridge
from mcp_score.bridge.remote_control import RemoteControlBridge
from mcp_score.tools import NOT_CONNECTED, check_measure, connected_bridge, to_json

__all__: list[str] = []

_REMOTE_CONTROL_ANALYSIS_WARNING = (
    "Dorico and Sibelius provide limited data through the Remote Control "
    "WebSocket API — you will get application status rather than detailed "
    "note content. Use get_selection_properties for the best results with "
    "Dorico/Sibelius."
)


@mcp.tool()
async def read_passage(
    start_measure: int,
    end_measure: int,
    staff: int | None = None,
) -> str:
    """Read musical content from a range of measures in the live score.

    Returns notes, rests, and musical elements in the specified range.
    Works best with MuseScore; Dorico and Sibelius return limited data
    through the Remote Control WebSocket API.

    Args:
        start_measure: First measure to read (1-indexed).
        end_measure: Last measure to read (inclusive, 1-indexed).
        staff: Staff index to read (0-indexed). If not provided, reads all staves.
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    if error := check_measure(start_measure, "start_measure"):
        return error
    if end_measure < start_measure:
        return to_json({"error": "end_measure must be >= start_measure."})

    elements: list[dict[str, Any]] = []
    for measure_num in range(start_measure, end_measure + 1):
        navigation_result = await bridge.go_to_measure(measure_num)
        if "error" in navigation_result:
            return to_json(navigation_result)
        if staff is not None:
            navigation_result = await bridge.go_to_staff(staff)
            if "error" in navigation_result:
                return to_json(navigation_result)
        cursor_info = await bridge.get_cursor_info()
        elements.append(
            {
                "measure": measure_num,
                "content": cursor_info,
            }
        )

    result: dict[str, Any] = {
        "success": True,
        "start_measure": start_measure,
        "end_measure": end_measure,
        "staff": staff,
        "elements": elements,
    }
    if isinstance(bridge, RemoteControlBridge):
        result["warning"] = _REMOTE_CONTROL_ANALYSIS_WARNING
    return to_json(result)


@mcp.tool()
async def get_measure_content(measure: int, staff: int = 0) -> str:
    """Read the content of a specific measure and staff from the connected score.

    Works best with MuseScore; Dorico and Sibelius return limited data.

    Args:
        measure: Measure number (1-indexed).
        staff: Staff index (0-indexed, default: 0).
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    if error := check_measure(measure):
        return error

    navigation_result = await bridge.go_to_measure(measure)
    if "error" in navigation_result:
        return to_json(navigation_result)
    navigation_result = await bridge.go_to_staff(staff)
    if "error" in navigation_result:
        return to_json(navigation_result)

    if not isinstance(bridge, MuseScoreBridge):
        return to_json(
            {
                "warning": _REMOTE_CONTROL_ANALYSIS_WARNING,
                "measure": measure,
                "staff": staff,
            }
        )

    result = await bridge.send_command("selectCurrentMeasure")
    return to_json(result)


@mcp.tool()
async def get_selection_properties() -> str:
    """Get properties of the current selection in the connected score application.

    Returns information about whatever is currently selected:

    - **MuseScore**: Returns cursor position info (measure, beat, staff).
    - **Dorico/Sibelius**: Returns properties from the Remote Control
      API's ``getproperties`` message — names, types, and values of all
      properties on the selected items. This is the closest the WebSocket
      API gets to "reading" score data.

    Requires an active connection.
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    result = await bridge.get_properties()
    return to_json(result)
