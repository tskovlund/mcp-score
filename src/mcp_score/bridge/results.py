"""What the score operations report back.

Every model here is what a tool returns to the model, so the MCP server
publishes it as the tool's output schema and validates each result
against it. The bridges build them from the applications' replies.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = [
    "ApplicationReply",
    "BarlineSet",
    "ChordSymbolAdded",
    "CursorInfo",
    "CursorPosition",
    "Duration",
    "DynamicAdded",
    "Element",
    "KeySignatureSet",
    "MeasuresAppended",
    "Note",
    "NoteAdded",
    "Part",
    "RehearsalMarkAdded",
    "Result",
    "ScoreInfo",
    "SelectedRange",
    "SelectionProperties",
    "TempoSet",
    "TimeSignature",
    "TimeSignatureSet",
    "Transposed",
]


class Result(BaseModel):
    """Base of every result: strict about fields, documented by attribute."""

    model_config = ConfigDict(extra="forbid", use_attribute_docstrings=True)


class ApplicationReply(BaseModel):
    """An application's reply passed on as it came, for data with no fixed shape."""

    model_config = ConfigDict(extra="allow", use_attribute_docstrings=True)


# ── Score ─────────────────────────────────────────────────────────────


class Duration(Result):
    """A note length as a fraction of a whole note (1/4 is a quarter note)."""

    numerator: int
    denominator: int


class TimeSignature(Result):
    numerator: int
    denominator: int


class Part(Result):
    name: str
    start_staff: int
    """First staff of the part (0-indexed)."""
    end_staff: int
    """Last staff of the part (0-indexed, inclusive)."""


class ScoreInfo(Result):
    """What is known about the open score without reading its content."""

    title: str
    part_count: int
    parts: list[Part]
    measure_count: int
    key_signature: int | None
    """Sharps (positive) or flats (negative) at the start, when known."""
    time_signature: TimeSignature | None
    """The time signature at the start, when known."""


# ── Cursor ────────────────────────────────────────────────────────────


class CursorPosition(Result):
    """Where the application's cursor is."""

    measure: int
    """Measure number (1-indexed)."""
    staff: int
    """Staff index (0-indexed)."""


class Note(Result):
    pitch: int
    """MIDI pitch (60 = middle C)."""
    tpc: int
    """Tonal pitch class, which fixes the spelling (C# versus Db)."""
    name: str | None
    """Note name with octave, when the application gives one."""


class Element(Result):
    """What sits at the cursor: a chord, a rest, a single note or something else."""

    type: int
    """The application's element type code."""
    notes: list[Note] | None = None
    """The notes of a chord."""
    duration: Duration | None = None
    """The length of a chord or rest."""
    pitch: int | None = None
    """MIDI pitch of a single note."""
    tpc: int | None = None
    """Tonal pitch class of a single note."""
    name: str | None = None
    """Name of a single note."""


class CursorInfo(CursorPosition):
    """The cursor position and what is there."""

    voice: int
    beat: int | None
    """Beat within the measure (1-indexed), when the time signature is known."""
    tick: int
    """Position in the application's internal ticks."""
    element: Element | None
    """The element at the cursor, or None on an empty position."""


class SelectionProperties(Result):
    """What the application reports about the current selection.

    MuseScore reports the cursor position; Dorico reports the properties
    of the selected items as they come from its API.
    """

    cursor: CursorInfo | None = None
    properties: ApplicationReply | None = None
    warning: str | None = None


# ── Selection ─────────────────────────────────────────────────────────


class SelectedRange(Result):
    start_measure: int
    end_measure: int
    start_staff: int
    end_staff: int


# ── Edits: each echoes what was written and where ─────────────────────


class NoteAdded(CursorPosition):
    """A note was added; the position is where the cursor went afterwards."""

    pitch: int
    duration: Duration


class RehearsalMarkAdded(Result):
    text: str
    measure: int
    warning: str | None = None
    """Set when the application kept the mark but not the text."""


class ChordSymbolAdded(Result):
    text: str
    measure: int


class DynamicAdded(Result):
    dynamic: str
    measure: int


class BarlineSet(Result):
    barline_type: str
    measure: int


class KeySignatureSet(Result):
    fifths: int
    measure: int


class TimeSignatureSet(TimeSignature):
    measure: int


class TempoSet(Result):
    bpm: int
    text: str
    """The tempo marking as written."""
    measure: int


class MeasuresAppended(Result):
    count: int
    total_measures: int


class Transposed(Result):
    semitones: int
    notes: int
    """How many notes were moved."""
