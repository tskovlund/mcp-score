"""WebSocket client for the MuseScore plugin bridge."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

import websockets

from mcp_score.bridge.base import ScoreBridge

if TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection

__all__ = ["MuseScoreBridge"]

logger = logging.getLogger(__name__)


class MuseScoreBridge(ScoreBridge):
    """WebSocket client for communicating with the MuseScore QML plugin.

    The QML plugin runs inside MuseScore and exposes a WebSocket server.
    This client sends commands and receives responses.
    """

    #: Timeout in seconds for receiving a response from MuseScore.
    RECV_TIMEOUT: float = 30.0

    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._connection: ClientConnection | None = None

    @property
    def application_name(self) -> str:
        """Human-readable application name."""
        return "MuseScore"

    @property
    def uri(self) -> str:
        """WebSocket URI."""
        return f"ws://{self.host}:{self.port}"

    @property
    def is_connected(self) -> bool:
        """Whether there is an active, open WebSocket connection."""
        conn = self._connection
        if conn is None:
            return False
        # Check the actual connection state, not just object presence.
        try:
            return conn.protocol.state.name == "OPEN"  # pyright: ignore[reportUnknownMemberType]
        except AttributeError:
            return False  # Fallback: assume disconnected if state is unknown

    async def connect(self) -> bool:
        """Connect to the MuseScore WebSocket server.

        Returns:
            True if connected successfully, False otherwise.
        """
        try:
            self._connection = await websockets.connect(self.uri)
            logger.info("Connected to MuseScore at %s", self.uri)
            return True
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            logger.error("Failed to connect to MuseScore at %s: %s", self.uri, exc)
            self._connection = None
            return False

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            logger.info("Disconnected from MuseScore")

    async def _send_raw(self, command_json: str) -> dict[str, Any]:
        """Send a raw JSON command string over the active connection."""
        conn = self._connection
        if conn is None:
            return {"error": "No active connection"}

        await conn.send(command_json)
        response_raw = await asyncio.wait_for(conn.recv(), timeout=self.RECV_TIMEOUT)
        if not isinstance(response_raw, str):
            return {"error": "Received non-text response from MuseScore"}
        logger.debug("Received: %s", response_raw)
        try:
            result: dict[str, Any] = json.loads(response_raw)
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid JSON from MuseScore: {exc}"}
        return result

    async def send_command(
        self, action: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command to MuseScore and return the response.

        Auto-connects if not already connected. Attempts one reconnect
        on connection failure.

        Args:
            action: Command action name (e.g. "getScore", "addNote").
            params: Optional command parameters.

        Returns:
            Parsed JSON response from MuseScore.
        """
        if self._connection is None and not await self.connect():
            return {"error": f"Cannot connect to MuseScore at {self.uri}"}

        command: dict[str, Any] = {"command": action}
        if params is not None:
            command["params"] = params

        command_json = json.dumps(command)
        logger.debug("Sending: %s", command_json)

        try:
            return await self._send_raw(command_json)
        except (
            websockets.exceptions.ConnectionClosed,
            websockets.exceptions.WebSocketException,
            TimeoutError,
        ):
            logger.warning("Connection lost, attempting reconnect...")
            self._connection = None
            if not await self.connect():
                return {"error": "Lost connection to MuseScore and reconnect failed"}

            # Retry the command once after reconnecting.
            try:
                return await self._send_raw(command_json)
            except Exception as exc:  # noqa: BLE001
                return {"error": f"Command failed after reconnect: {exc}"}

    async def ping(self) -> bool:
        """Check if the connection is alive."""
        result = await self.send_command("ping")
        return result.get("result") == "pong"

    # ── Convenience methods ──────────────────────────────────────────

    async def get_score(self) -> dict[str, Any]:
        """Get the current score information."""
        return await self.send_command("getScore")

    async def get_cursor_info(self) -> dict[str, Any]:
        """Get current cursor position info."""
        return await self.send_command("getCursorInfo")

    async def go_to_measure(self, measure: int) -> dict[str, Any]:
        """Navigate to a specific measure (1-indexed)."""
        return await self.send_command("goToMeasure", {"measure": measure})

    async def go_to_staff(self, staff: int) -> dict[str, Any]:
        """Navigate to a specific staff (0-indexed)."""
        return await self.send_command("goToStaff", {"staff": staff})

    async def add_note(
        self,
        pitch: int,
        duration: dict[str, int],
        advance_cursor: bool = True,
    ) -> dict[str, Any]:
        """Add a note at the current cursor position."""
        return await self.send_command(
            "addNote",
            {
                "pitch": pitch,
                "duration": duration,
                "advanceCursorAfterAction": advance_cursor,
            },
        )

    async def add_rehearsal_mark(self, text: str) -> dict[str, Any]:
        """Add a rehearsal mark at the current cursor position."""
        return await self.send_command("addRehearsalMark", {"text": text})

    async def set_barline(self, barline_type: str) -> dict[str, Any]:
        """Set a barline at the current cursor position."""
        return await self.send_command("setBarline", {"type": barline_type})

    async def set_key_signature(self, fifths: int) -> dict[str, Any]:
        """Set the key signature (positive = sharps, negative = flats)."""
        return await self.send_command("setKeySignature", {"fifths": fifths})

    async def set_time_signature(
        self, numerator: int, denominator: int
    ) -> dict[str, Any]:
        """Set the time signature."""
        return await self.send_command(
            "setTimeSignature",
            {"numerator": numerator, "denominator": denominator},
        )

    async def set_tempo(self, bpm: int, text: str | None = None) -> dict[str, Any]:
        """Set the tempo."""
        params: dict[str, Any] = {"bpm": bpm}
        if text is not None:
            params["text"] = text
        return await self.send_command("setTempo", params)

    async def add_chord_symbol(self, text: str) -> dict[str, Any]:
        """Add a chord symbol at the current cursor position."""
        return await self.send_command("addChordSymbol", {"text": text})

    async def add_dynamic(self, dynamic_type: str) -> dict[str, Any]:
        """Add a dynamic marking at the current cursor position."""
        return await self.send_command("addDynamic", {"type": dynamic_type})

    async def append_measures(self, count: int = 1) -> dict[str, Any]:
        """Append measures to the end of the score."""
        return await self.send_command("appendMeasures", {"count": count})

    async def process_sequence(self, commands: list[dict[str, Any]]) -> dict[str, Any]:
        """Execute a sequence of commands atomically."""
        return await self.send_command("processSequence", {"sequence": commands})

    async def undo(self) -> dict[str, Any]:
        """Undo the last action."""
        return await self.send_command("undo")
