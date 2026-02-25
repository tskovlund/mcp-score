"""Score generation tools — create scores from structured descriptions."""

import json
from typing import Any

from mcp_score.app import mcp
from mcp_score.score_manager import ScoreManager

__all__: list[str] = []

# Module-level score manager instance shared across all tool calls.
_manager = ScoreManager()


def _result(data: dict[str, Any]) -> str:
    """Serialize a result dict to JSON."""
    return json.dumps(data)


def get_manager() -> ScoreManager:
    """Access the shared score manager (for use by other tool modules)."""
    return _manager


@mcp.tool()
async def create_score(
    title: str,
    instruments: list[str],
    key_signature: str = "C major",
    time_signature: str = "4/4",
    tempo: int = 120,
    num_measures: int = 32,
) -> str:
    """Create a new score with specified instrumentation and properties.

    Args:
        title: Score title.
        instruments: List of instrument names
            (e.g. ["trumpet 1", "trumpet 2", "alto sax", "piano"]).
        key_signature: Key signature
            (e.g. "Bb major", "F# minor", "C major").
        time_signature: Time signature (e.g. "4/4", "3/4", "6/8").
        tempo: Tempo in BPM.
        num_measures: Number of measures.
    """
    return _result(
        _manager.create_score(
            title=title,
            instruments=instruments,
            key_signature=key_signature,
            time_signature=time_signature,
            tempo_bpm=tempo,
            num_measures=num_measures,
        )
    )


@mcp.tool()
async def add_rehearsal_mark(measure: int, label: str) -> str:
    """Add a rehearsal mark at the specified measure.

    Args:
        measure: Measure number (1-indexed).
        label: Rehearsal mark text (e.g. "A", "B", "Intro", "Coda").
    """
    return _result(_manager.add_rehearsal_mark(measure=measure, label=label))


@mcp.tool()
async def set_barline(measure: int, barline_type: str) -> str:
    """Set a barline type at the end of the specified measure.

    Args:
        measure: Measure number (1-indexed).
        barline_type: One of "double", "final", "repeat-start",
            "repeat-end".
    """
    return _result(_manager.set_barline(measure=measure, barline_type=barline_type))


@mcp.tool()
async def add_chord_symbol(measure: int, beat: float, symbol: str) -> str:
    """Add a chord symbol at the specified position.

    Chord symbols are added to the first part by default, which is
    standard practice — chord symbols apply to the whole ensemble.

    Args:
        measure: Measure number (1-indexed).
        beat: Beat position (1.0 = beat 1, 2.0 = beat 2, etc.).
        symbol: Chord symbol (e.g. "Cmaj7", "Dm7", "G7alt", "Bb7#11").
    """
    return _result(
        _manager.add_chord_symbol(
            part_index_or_name="0",
            measure=measure,
            beat=beat,
            symbol=symbol,
        )
    )


@mcp.tool()
async def add_tempo_marking(measure: int, bpm: int, text: str | None = None) -> str:
    """Add a tempo marking at the specified measure.

    Args:
        measure: Measure number (1-indexed).
        bpm: Tempo in beats per minute.
        text: Optional display text (e.g. "Swing", "Ballad", "Allegro").
    """
    return _result(_manager.add_tempo_marking(measure=measure, bpm=bpm, text=text))


@mcp.tool()
async def add_notes(part: str, measure: int, notes: list[dict[str, str]]) -> str:
    """Add notes to a specific part and measure.

    Replaces any existing content in the measure for that part.

    Args:
        part: Part name or instrument name (e.g. "Trumpet 1", "Piano").
        measure: Measure number (1-indexed).
        notes: List of note dicts with "pitch" and "duration" keys.
            Pitch: note name with octave (e.g. "C5", "Bb4", "F#3").
            Use "rest" for a rest.
            Duration: "whole", "half", "quarter", "eighth", "16th",
            or "dotted-quarter" etc.
    """
    return _result(
        _manager.add_notes(part_index_or_name=part, measure=measure, notes=notes)
    )


@mcp.tool()
async def get_score_info() -> str:
    """Get information about the current in-memory score."""
    return _result(_manager.get_score_info())


@mcp.tool()
async def export_score(filepath: str) -> str:
    """Export the current score as MusicXML.

    Args:
        filepath: Output file path (should end in .musicxml or .xml).
    """
    return _result(_manager.export_musicxml(filepath=filepath))


@mcp.tool()
async def clear_score() -> str:
    """Clear the current in-memory score."""
    return _result(_manager.clear())
