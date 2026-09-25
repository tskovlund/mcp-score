"""The interface every score application bridge implements.

A bridge talks to one running notation application. The MCP tools only
depend on this interface, so an application is supported by adding a
bridge, not by touching the tools. Operations an application cannot
perform return an ``{"error": ...}`` result that explains why; the tools
pass such results straight back to the model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, NamedTuple

__all__ = ["CommandResult", "NoteDuration", "ScoreBridge"]

type CommandResult = dict[str, Any]
"""What every score operation returns: the application's decoded JSON reply.

A reply carries either a ``result`` field or an ``error`` field. Bridges
add a ``warning`` field when the application did something, but not quite
what was asked.
"""


class NoteDuration(NamedTuple):
    """A note length as a fraction of a whole note (1/4 is a quarter note)."""

    numerator: int
    denominator: int


class ScoreBridge(ABC):
    """Interface for communicating with a score notation application."""

    @property
    @abstractmethod
    def application_name(self) -> str:
        """Human-readable name of the application, for messages to the model."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether commands can be sent right now."""

    @property
    def content_reading_limitation(self) -> str | None:
        """Why reading score content is limited, or ``None`` when it is not.

        Analysis tools attach this as a warning so the model knows the data
        it got is the best the application can give.
        """
        return None

    # ── Connection ──────────────────────────────────────────────────

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the application. Returns whether it succeeded."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection to the application."""

    @abstractmethod
    async def ping(self) -> bool:
        """Whether the application answers."""

    @abstractmethod
    async def send_command(
        self, action: str, params: dict[str, Any] | None = None
    ) -> CommandResult:
        """Send an application-native command and return its reply."""

    # ── Reading ─────────────────────────────────────────────────────

    @abstractmethod
    async def get_score(self) -> CommandResult:
        """Metadata about the open score."""

    @abstractmethod
    async def get_cursor_info(self) -> CommandResult:
        """The current position and what is there."""

    @abstractmethod
    async def get_properties(self) -> CommandResult:
        """Properties of the current selection."""

    # ── Navigation and selection ────────────────────────────────────

    @abstractmethod
    async def go_to_measure(self, measure: int) -> CommandResult:
        """Move to a measure (1-indexed)."""

    @abstractmethod
    async def go_to_staff(self, staff: int) -> CommandResult:
        """Move to a staff (0-indexed)."""

    @abstractmethod
    async def select_measure(self) -> CommandResult:
        """Select the measure at the current position."""

    @abstractmethod
    async def select_range(
        self, start_measure: int, end_measure: int, start_staff: int, end_staff: int
    ) -> CommandResult:
        """Select a range of measures (1-indexed) and staves (0-indexed), inclusive."""

    # ── Writing ─────────────────────────────────────────────────────

    @abstractmethod
    async def add_note(
        self, pitch: int, duration: NoteDuration, advance_cursor: bool = True
    ) -> CommandResult:
        """Add a note (MIDI pitch) at the current position."""

    @abstractmethod
    async def add_rehearsal_mark(self, text: str) -> CommandResult:
        """Add a rehearsal mark at the current position."""

    @abstractmethod
    async def add_chord_symbol(self, text: str) -> CommandResult:
        """Add a chord symbol at the current position."""

    @abstractmethod
    async def add_dynamic(self, dynamic: str) -> CommandResult:
        """Add a dynamic marking (``"mf"``, ``"p"``, ...) at the current position."""

    @abstractmethod
    async def set_barline(self, barline_type: str) -> CommandResult:
        """Set the bar line at the end of the current measure."""

    @abstractmethod
    async def set_key_signature(self, fifths: int) -> CommandResult:
        """Set the key signature (positive = sharps, negative = flats)."""

    @abstractmethod
    async def set_time_signature(
        self, numerator: int, denominator: int
    ) -> CommandResult:
        """Set the time signature at the current position."""

    @abstractmethod
    async def set_tempo(self, bpm: int, text: str | None = None) -> CommandResult:
        """Set the tempo at the current position."""

    @abstractmethod
    async def append_measures(self, count: int) -> CommandResult:
        """Append empty measures to the end of the score."""

    @abstractmethod
    async def transpose(self, semitones: int) -> CommandResult:
        """Transpose the current selection by a number of semitones."""

    @abstractmethod
    async def undo(self) -> CommandResult:
        """Undo the last change."""
