"""The interface every score application bridge implements.

A bridge talks to one running notation application. The MCP tools only
depend on this interface, so an application is supported by adding a
bridge, not by touching the tools. Every operation returns one of the
result models in :mod:`mcp_score.bridge.results`; an operation the
application cannot perform raises :class:`BridgeError` with the
application's explanation, which the tools report as a tool error.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp_score.bridge.results import (
        BarlineSet,
        ChordSymbolAdded,
        CursorInfo,
        CursorPosition,
        Duration,
        DynamicAdded,
        KeySignatureSet,
        MeasuresAppended,
        NoteAdded,
        RehearsalMarkAdded,
        ScoreInfo,
        SelectedRange,
        SelectionProperties,
        TempoSet,
        TimeSignatureSet,
        Transposed,
    )

__all__ = ["BridgeError", "CommandResult", "ScoreBridge"]

type CommandResult = dict[str, Any]
"""An application's decoded JSON reply, before a bridge reads a result out of it."""


class BridgeError(Exception):
    """The application could not do what was asked; the message says why.

    Raised for the application's own refusals (``details`` carries any
    other fields of its reply), for operations its protocol cannot
    express, and for a connection that could not be made or kept.
    """

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ScoreBridge(ABC):
    """Interface for communicating with a score notation application.

    Every operation returns the result model that describes what the
    application reported, and raises :class:`BridgeError` when it could
    not do what was asked.
    """

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
        """Send an application-native command and return its raw reply."""

    # ── Reading ─────────────────────────────────────────────────────

    @abstractmethod
    async def get_score(self) -> ScoreInfo:
        """Metadata about the open score."""

    @abstractmethod
    async def get_cursor_info(self) -> CursorInfo:
        """The current position and what is there."""

    @abstractmethod
    async def get_properties(self) -> SelectionProperties:
        """Properties of the current selection."""

    # ── Navigation and selection ────────────────────────────────────

    @abstractmethod
    async def go_to_measure(self, measure: int) -> CursorPosition:
        """Move to a measure (1-indexed)."""

    @abstractmethod
    async def go_to_staff(self, staff: int) -> CursorPosition:
        """Move to a staff (0-indexed)."""

    @abstractmethod
    async def select_measure(self) -> CursorPosition:
        """Select the measure at the current position."""

    @abstractmethod
    async def select_range(
        self, start_measure: int, end_measure: int, start_staff: int, end_staff: int
    ) -> SelectedRange:
        """Select a range of measures (1-indexed) and staves (0-indexed), inclusive."""

    # ── Writing ─────────────────────────────────────────────────────

    @abstractmethod
    async def add_note(
        self, pitch: int, duration: Duration, advance_cursor: bool = True
    ) -> NoteAdded:
        """Add a note (MIDI pitch) at the current position."""

    @abstractmethod
    async def add_rehearsal_mark(self, text: str) -> RehearsalMarkAdded:
        """Add a rehearsal mark at the current position."""

    @abstractmethod
    async def add_chord_symbol(self, text: str) -> ChordSymbolAdded:
        """Add a chord symbol at the current position."""

    @abstractmethod
    async def add_dynamic(self, dynamic: str) -> DynamicAdded:
        """Add a dynamic marking (``"mf"``, ``"p"``, ...) at the current position."""

    @abstractmethod
    async def set_barline(self, barline_type: str) -> BarlineSet:
        """Set the bar line at the end of the current measure."""

    @abstractmethod
    async def set_key_signature(self, fifths: int) -> KeySignatureSet:
        """Set the key signature (positive = sharps, negative = flats)."""

    @abstractmethod
    async def set_time_signature(
        self, numerator: int, denominator: int
    ) -> TimeSignatureSet:
        """Set the time signature at the current position."""

    @abstractmethod
    async def set_tempo(self, bpm: int, text: str | None = None) -> TempoSet:
        """Set the tempo at the current position."""

    @abstractmethod
    async def append_measures(self, count: int) -> MeasuresAppended:
        """Append empty measures to the end of the score."""

    @abstractmethod
    async def transpose(self, semitones: int) -> Transposed:
        """Transpose the current selection by a number of semitones."""

    @abstractmethod
    async def undo(self) -> CursorPosition:
        """Undo the last change; the cursor may move if the change removed measures."""
