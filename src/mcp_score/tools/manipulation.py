"""Manipulation tools: change the score in the connected application.

Every tool that takes a measure moves there first and refuses to continue
if the application cannot get there, so a change never lands in the wrong
place. What an application cannot do comes back as its own explanation:
Dorico's Remote Control API triggers commands but cannot type into
popovers or move the selection, so most of these tools work with MuseScore
only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp_score.bridge import CommandResult, NoteDuration
from mcp_score.context import ScoreContext
from mcp_score.tools import (
    ToolError,
    navigate,
    require_bridge,
    require_measure,
    require_measure_range,
    score_tool,
)

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

__all__ = ["register"]

MIN_MIDI_PITCH = 0
MAX_MIDI_PITCH = 127


@score_tool
async def add_live_note(
    context: ScoreContext,
    measure: int,
    pitch: int,
    numerator: int = 1,
    denominator: int = 4,
    staff: int = 0,
) -> CommandResult:
    """Add a note at the start of a measure in the live score.

    Consecutive calls on the same measure append notes one after another,
    since the application advances its cursor after each note. Not
    available with Dorico.

    Args:
        measure: Measure number (1-indexed).
        pitch: MIDI pitch (60 = middle C).
        numerator: Duration numerator (default 1, with denominator 4 = quarter note).
        denominator: Duration denominator (default 4).
        staff: Staff index (0-indexed, default: 0).
    """
    bridge = require_bridge(context)
    require_measure(measure)
    if not MIN_MIDI_PITCH <= pitch <= MAX_MIDI_PITCH:
        raise ToolError(f"pitch must be between {MIN_MIDI_PITCH} and {MAX_MIDI_PITCH}.")
    if numerator < 1 or denominator < 1:
        raise ToolError("numerator and denominator must be >= 1.")
    await navigate(bridge, measure, staff)
    return await bridge.add_note(pitch, NoteDuration(numerator, denominator))


@score_tool
async def add_live_rehearsal_mark(
    context: ScoreContext, measure: int, text: str
) -> CommandResult:
    """Add a rehearsal mark to a measure in the live score.

    Dorico numbers rehearsal marks itself and ignores the text (the result
    says so in a warning).

    Args:
        measure: Measure number (1-indexed).
        text: Rehearsal mark text (e.g. "A", "B", "Intro").
    """
    bridge = require_bridge(context)
    require_measure(measure)
    await navigate(bridge, measure)
    return await bridge.add_rehearsal_mark(text)


@score_tool
async def add_live_chord_symbol(
    context: ScoreContext, measure: int, symbol: str
) -> CommandResult:
    """Add a chord symbol to a measure in the live score.

    Not available with Dorico.

    Args:
        measure: Measure number (1-indexed).
        symbol: Chord symbol (e.g. "Cmaj7", "Dm7", "G7").
    """
    bridge = require_bridge(context)
    require_measure(measure)
    await navigate(bridge, measure)
    return await bridge.add_chord_symbol(symbol)


@score_tool
async def add_live_dynamic(
    context: ScoreContext, measure: int, dynamic: str, staff: int = 0
) -> CommandResult:
    """Add a dynamic marking to a measure in the live score.

    Not available with Dorico.

    Args:
        measure: Measure number (1-indexed).
        dynamic: Dynamic such as "pp", "p", "mp", "mf", "f", "ff", "sfz".
        staff: Staff index (0-indexed, default: 0).
    """
    bridge = require_bridge(context)
    require_measure(measure)
    await navigate(bridge, measure, staff)
    return await bridge.add_dynamic(dynamic)


@score_tool
async def set_live_barline(
    context: ScoreContext, measure: int, barline_type: str
) -> CommandResult:
    """Set the bar line at the end of a measure in the live score.

    Args:
        measure: Measure number (1-indexed).
        barline_type: One of "normal", "double", "final", "dashed", "dotted",
            "tick", "short", "startRepeat", "endRepeat" or "endStartRepeat".
            "startRepeat" marks the start of this measure; "endStartRepeat"
            ends a repeat here and starts one in the next measure. Dorico
            supports "double", "final", "startRepeat" and "endRepeat".
    """
    bridge = require_bridge(context)
    require_measure(measure)
    await navigate(bridge, measure)
    return await bridge.set_barline(barline_type)


@score_tool
async def set_live_key_signature(
    context: ScoreContext, measure: int, fifths: int
) -> CommandResult:
    """Set the key signature from a measure onward in the live score.

    Not available with Dorico.

    Args:
        measure: Measure number (1-indexed).
        fifths: Sharps (positive) or flats (negative): 0 = C major,
            2 = D major, -3 = Eb major.
    """
    bridge = require_bridge(context)
    require_measure(measure)
    await navigate(bridge, measure)
    return await bridge.set_key_signature(fifths)


@score_tool
async def set_live_time_signature(
    context: ScoreContext, measure: int, numerator: int, denominator: int
) -> CommandResult:
    """Set the time signature from a measure onward in the live score.

    Not available with Dorico.

    Args:
        measure: Measure number (1-indexed).
        numerator: Beats per measure (e.g. 3 in 3/4).
        denominator: Beat unit (e.g. 4 in 3/4).
    """
    bridge = require_bridge(context)
    require_measure(measure)
    if numerator < 1 or denominator < 1:
        raise ToolError("numerator and denominator must be >= 1.")
    await navigate(bridge, measure)
    return await bridge.set_time_signature(numerator, denominator)


@score_tool
async def set_live_tempo(
    context: ScoreContext, measure: int, bpm: int, text: str | None = None
) -> CommandResult:
    """Set the tempo at a measure in the live score.

    Not available with Dorico.

    Args:
        measure: Measure number (1-indexed).
        bpm: Beats per minute.
        text: Optional display text (e.g. "Swing", "Allegro").
    """
    bridge = require_bridge(context)
    require_measure(measure)
    if bpm < 1:
        raise ToolError("bpm must be >= 1.")
    await navigate(bridge, measure)
    return await bridge.set_tempo(bpm, text)


@score_tool
async def append_live_measures(context: ScoreContext, count: int = 1) -> CommandResult:
    """Append empty measures to the end of the live score.

    Not available with Dorico.

    Args:
        count: How many measures to append (default: 1).
    """
    bridge = require_bridge(context)
    if count < 1:
        raise ToolError("count must be >= 1.")
    return await bridge.append_measures(count)


@score_tool
async def transpose_passage(
    context: ScoreContext,
    start_measure: int,
    end_measure: int,
    staff: int,
    semitones: int,
) -> CommandResult:
    """Transpose the notes of a passage by a number of semitones in the live score.

    Notes are moved with conventional spelling (a minor second up turns C
    into Db). Key signatures and chord symbols in the passage are left
    unchanged. Not available with Dorico, which cannot select a range.

    Args:
        start_measure: First measure (1-indexed).
        end_measure: Last measure (inclusive, 1-indexed).
        staff: Staff index (0-indexed).
        semitones: Semitones to transpose (positive = up, negative = down).
    """
    bridge = require_bridge(context)
    require_measure_range(start_measure, end_measure)
    await navigate(bridge, start_measure, staff)
    await bridge.select_range(start_measure, end_measure, staff, staff)
    return await bridge.transpose(semitones)


@score_tool
async def undo_last_action(context: ScoreContext) -> CommandResult:
    """Undo the last change in the connected application."""
    return await require_bridge(context).undo()


def register(server: MCPServer) -> None:
    for tool in (
        add_live_note,
        add_live_rehearsal_mark,
        add_live_chord_symbol,
        add_live_dynamic,
        set_live_barline,
        set_live_key_signature,
        set_live_time_signature,
        set_live_tempo,
        append_live_measures,
        transpose_passage,
        undo_last_action,
    ):
        server.tool()(tool)
