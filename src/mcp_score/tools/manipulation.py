"""Score manipulation tools — modify scores in a live MuseScore instance."""

import json
from typing import Any

from mcp_score.app import mcp
from mcp_score.bridge import get_bridge

__all__: list[str] = []


def _result(data: dict[str, Any]) -> str:
    """Serialize a result dict to JSON."""
    return json.dumps(data)


@mcp.tool()
async def add_live_rehearsal_mark(measure: int, text: str) -> str:
    """Add a rehearsal mark in the live MuseScore score.

    Args:
        measure: Measure number (1-indexed).
        text: Rehearsal mark text (e.g. "A", "B", "Intro").
    """
    bridge = get_bridge()
    if not bridge.is_connected:
        return _result(
            {"error": "Not connected to MuseScore. Use connect_to_musescore first."}
        )

    await bridge.go_to_measure(measure)
    result = await bridge.add_rehearsal_mark(text)
    return _result(result)


@mcp.tool()
async def add_live_chord_symbol(measure: int, symbol: str) -> str:
    """Add a chord symbol in the live MuseScore score.

    Args:
        measure: Measure number (1-indexed).
        symbol: Chord symbol (e.g. "Cmaj7", "Dm7", "G7").
    """
    bridge = get_bridge()
    if not bridge.is_connected:
        return _result(
            {"error": "Not connected to MuseScore. Use connect_to_musescore first."}
        )

    await bridge.go_to_measure(measure)
    result = await bridge.add_chord_symbol(symbol)
    return _result(result)


@mcp.tool()
async def set_live_barline(measure: int, barline_type: str) -> str:
    """Set a barline type in the live MuseScore score.

    Args:
        measure: Measure number (1-indexed).
        barline_type: One of "double", "final", "repeat-start", "repeat-end".
    """
    bridge = get_bridge()
    if not bridge.is_connected:
        return _result(
            {"error": "Not connected to MuseScore. Use connect_to_musescore first."}
        )

    await bridge.go_to_measure(measure)
    result = await bridge.set_barline(barline_type)
    return _result(result)


@mcp.tool()
async def set_live_key_signature(measure: int, fifths: int) -> str:
    """Set the key signature in the live MuseScore score.

    Args:
        measure: Measure number (1-indexed).
        fifths: Number of sharps (positive) or flats (negative).
            Examples: 0 = C major, 2 = D major, -3 = Eb major.
    """
    bridge = get_bridge()
    if not bridge.is_connected:
        return _result(
            {"error": "Not connected to MuseScore. Use connect_to_musescore first."}
        )

    await bridge.go_to_measure(measure)
    result = await bridge.set_key_signature(fifths)
    return _result(result)


@mcp.tool()
async def set_live_tempo(measure: int, bpm: int, text: str | None = None) -> str:
    """Set the tempo in the live MuseScore score.

    Args:
        measure: Measure number (1-indexed).
        bpm: Beats per minute.
        text: Optional display text (e.g. "Swing", "Allegro").
    """
    bridge = get_bridge()
    if not bridge.is_connected:
        return _result(
            {"error": "Not connected to MuseScore. Use connect_to_musescore first."}
        )

    await bridge.go_to_measure(measure)
    result = await bridge.set_tempo(bpm, text)
    return _result(result)


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
    bridge = get_bridge()
    if not bridge.is_connected:
        return _result(
            {"error": "Not connected to MuseScore. Use connect_to_musescore first."}
        )

    # Select the range, then apply transposition via command sequence.
    await bridge.go_to_measure(start_measure)
    await bridge.go_to_staff(staff)

    # Select from start to end measure.
    result = await bridge.send_command(
        "selectCustomRange",
        {
            "startMeasure": start_measure,
            "endMeasure": end_measure,
            "startStaff": staff,
            "endStaff": staff + 1,
        },
    )

    if result.get("error"):
        return _result(result)

    # Apply transposition.
    result = await bridge.send_command(
        "transpose",
        {"semitones": semitones},
    )

    return _result(result)


@mcp.tool()
async def undo_last_action() -> str:
    """Undo the last action in MuseScore."""
    bridge = get_bridge()
    if not bridge.is_connected:
        return _result(
            {"error": "Not connected to MuseScore. Use connect_to_musescore first."}
        )

    result = await bridge.undo()
    return _result(result)
