"""Score manipulation tools — modify the live score in a connected application."""

from mcp_score.app import mcp
from mcp_score.bridge.musescore import MuseScoreBridge
from mcp_score.tools import NOT_CONNECTED, check_measure, connected_bridge, to_json

__all__: list[str] = []


@mcp.tool()
async def add_live_rehearsal_mark(measure: int, text: str) -> str:
    """Add a rehearsal mark in the live score.

    Args:
        measure: Measure number (1-indexed).
        text: Rehearsal mark text (e.g. "A", "B", "Intro").
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    if error := check_measure(measure):
        return error

    await bridge.go_to_measure(measure)
    result = await bridge.add_rehearsal_mark(text)
    return to_json(result)


@mcp.tool()
async def add_live_chord_symbol(measure: int, symbol: str) -> str:
    """Add a chord symbol in the live score.

    Args:
        measure: Measure number (1-indexed).
        symbol: Chord symbol (e.g. "Cmaj7", "Dm7", "G7").
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    if error := check_measure(measure):
        return error

    await bridge.go_to_measure(measure)
    result = await bridge.add_chord_symbol(symbol)
    return to_json(result)


@mcp.tool()
async def set_live_barline(measure: int, barline_type: str) -> str:
    """Set a barline type in the live score.

    Args:
        measure: Measure number (1-indexed).
        barline_type: One of "double", "final", "startRepeat", "endRepeat".
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    if error := check_measure(measure):
        return error

    await bridge.go_to_measure(measure)
    result = await bridge.set_barline(barline_type)
    return to_json(result)


@mcp.tool()
async def set_live_key_signature(measure: int, fifths: int) -> str:
    """Set the key signature in the live score.

    Args:
        measure: Measure number (1-indexed).
        fifths: Number of sharps (positive) or flats (negative).
            Examples: 0 = C major, 2 = D major, -3 = Eb major.
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    if error := check_measure(measure):
        return error

    await bridge.go_to_measure(measure)
    result = await bridge.set_key_signature(fifths)
    return to_json(result)


@mcp.tool()
async def set_live_tempo(measure: int, bpm: int, text: str | None = None) -> str:
    """Set the tempo in the live score.

    Args:
        measure: Measure number (1-indexed).
        bpm: Beats per minute.
        text: Optional display text (e.g. "Swing", "Allegro").
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    if error := check_measure(measure):
        return error

    await bridge.go_to_measure(measure)
    result = await bridge.set_tempo(bpm, text)
    return to_json(result)


@mcp.tool()
async def transpose_passage(
    start_measure: int,
    end_measure: int,
    staff: int,
    semitones: int,
) -> str:
    """Transpose a passage by a number of semitones in the live score.

    Args:
        start_measure: First measure (1-indexed).
        end_measure: Last measure (inclusive, 1-indexed).
        staff: Staff index (0-indexed).
        semitones: Number of semitones to transpose (positive = up, negative = down).
    """
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})
    if not isinstance(bridge, MuseScoreBridge):
        return to_json(
            {
                "error": (
                    "transpose_passage is only supported with MuseScore. "
                    f"{bridge.application_name}'s Remote Control API does not "
                    "support programmatic range selection and transposition."
                )
            }
        )
    if error := check_measure(start_measure, "start_measure"):
        return error
    if end_measure < start_measure:
        return to_json({"error": "end_measure must be >= start_measure."})

    navigation_result = await bridge.go_to_measure(start_measure)
    if "error" in navigation_result:
        return to_json(navigation_result)
    navigation_result = await bridge.go_to_staff(staff)
    if "error" in navigation_result:
        return to_json(navigation_result)

    result = await bridge.send_command(
        "selectCustomRange",
        {
            "startMeasure": start_measure,
            "endMeasure": end_measure,
            "startStaff": staff,
            "endStaff": staff,
        },
    )

    if result.get("error"):
        return to_json(result)

    result = await bridge.send_command(
        "transpose",
        {"semitones": semitones},
    )

    return to_json(result)


@mcp.tool()
async def undo_last_action() -> str:
    """Undo the last action in the connected score application."""
    bridge = connected_bridge()
    if bridge is None:
        return to_json({"error": NOT_CONNECTED})

    result = await bridge.undo()
    return to_json(result)
