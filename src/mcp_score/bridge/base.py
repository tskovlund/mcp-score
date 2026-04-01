"""Abstract base class for score application bridges."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from websockets.asyncio.connection import Connection

__all__ = ["ScoreBridge"]

#: WebSocket protocol state name indicating an open connection.
WEBSOCKET_STATE_OPEN = "OPEN"


class ScoreBridge(ABC):
    """Interface for communicating with a score notation application.

    Each concrete bridge (MuseScore, Dorico, etc.) implements this
    interface so that MCP tools can work with any supported DAW.
    """

    _connection: Connection | None

    @property
    def is_connected(self) -> bool:
        """Whether there is an active, open WebSocket connection."""
        connection = self._connection
        if connection is None:
            return False
        try:
            return (
                connection.protocol.state.name  # pyright: ignore[reportUnknownMemberType]
                == WEBSOCKET_STATE_OPEN
            )
        except AttributeError:
            return False

    @property
    @abstractmethod
    def application_name(self) -> str:
        """Human-readable name of the connected application (e.g. 'MuseScore')."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the score application.

        Returns:
            True if connected successfully, False otherwise.
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection to the score application."""

    @abstractmethod
    async def send_command(
        self, action: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command and return the response.

        Args:
            action: Command action name.
            params: Optional command parameters.

        Returns:
            Parsed response from the application.
        """

    @abstractmethod
    async def ping(self) -> bool:
        """Check if the connection is alive."""

    @abstractmethod
    async def get_score(self) -> dict[str, Any]:
        """Get information about the currently open score."""

    @abstractmethod
    async def get_cursor_info(self) -> dict[str, Any]:
        """Get current cursor/selection position info."""

    @abstractmethod
    async def go_to_measure(self, measure: int) -> dict[str, Any]:
        """Navigate to a specific measure (1-indexed)."""

    @abstractmethod
    async def go_to_staff(self, staff: int) -> dict[str, Any]:
        """Navigate to a specific staff (0-indexed)."""

    @abstractmethod
    async def add_rehearsal_mark(self, text: str) -> dict[str, Any]:
        """Add a rehearsal mark at the current position."""

    @abstractmethod
    async def add_chord_symbol(self, text: str) -> dict[str, Any]:
        """Add a chord symbol at the current position."""

    @abstractmethod
    async def set_barline(self, barline_type: str) -> dict[str, Any]:
        """Set a barline at the current position."""

    @abstractmethod
    async def set_key_signature(self, fifths: int) -> dict[str, Any]:
        """Set the key signature (positive = sharps, negative = flats)."""

    @abstractmethod
    async def set_tempo(self, bpm: int, text: str | None = None) -> dict[str, Any]:
        """Set the tempo."""

    @abstractmethod
    async def get_properties(self) -> dict[str, Any]:
        """Get properties of the current selection."""

    @abstractmethod
    async def undo(self) -> dict[str, Any]:
        """Undo the last action."""
