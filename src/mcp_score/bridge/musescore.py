"""WebSocket server for the MuseScore plugin bridge.

The MuseScore 4.4+ plugin system sandboxes plugins and forbids server-side
socket operations. The QML plugin therefore runs as a WebSocket *client* that
connects outward to this server on localhost:8765. The JSON command/response
protocol is unchanged; only the direction of the TCP connection is flipped.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

import websockets
import websockets.asyncio.server

from mcp_score.bridge.base import ScoreBridge

if TYPE_CHECKING:
    from websockets.asyncio.server import Server, ServerConnection

__all__ = ["DEFAULT_PORT", "MuseScoreBridge"]

logger = logging.getLogger(__name__)

#: Default WebSocket port for the MuseScore QML plugin.
DEFAULT_PORT = 8765

#: Timeout in seconds to wait for the MuseScore plugin to connect.
_CONNECT_TIMEOUT: float = 30.0


class MuseScoreBridge(ScoreBridge):
    """WebSocket server that waits for the MuseScore QML plugin to connect.

    Start this server first (via ``mcp-score serve``), then run the QML plugin
    inside MuseScore. The plugin dials out to ``ws://localhost:8765``, and this
    class sends commands and receives responses over that connection.
    """

    #: Timeout in seconds for receiving a response from MuseScore.
    RECV_TIMEOUT: float = 30.0

    def __init__(self, host: str = "localhost", port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self._connection: ServerConnection | None = None
        self._server: Server | None = None
        self._client_connected: asyncio.Event = asyncio.Event()

    @property
    def application_name(self) -> str:
        """Human-readable application name."""
        return "MuseScore"

    @property
    def uri(self) -> str:
        """WebSocket URI the server listens on."""
        return f"ws://{self.host}:{self.port}"

    async def _handle_client(self, connection: ServerConnection) -> None:
        """Accept an incoming connection from the MuseScore plugin."""
        logger.info("MuseScore plugin connected from %s", connection.remote_address)
        self._connection = connection
        self._client_connected.set()
        try:
            await connection.wait_closed()
        finally:
            logger.info("MuseScore plugin disconnected")
            if self._connection is connection:
                self._connection = None

    async def connect(self) -> bool:
        """Start the WebSocket server and wait for the MuseScore plugin to connect.

        Returns:
            True if the plugin connected within the timeout, False otherwise.
        """
        self._client_connected.clear()
        try:
            self._server = await websockets.asyncio.server.serve(
                self._handle_client, self.host, self.port
            )
            logger.info("WebSocket server listening at %s", self.uri)
        except OSError as exception:
            logger.error(
                "Failed to start WebSocket server at %s: %s", self.uri, exception
            )
            self._server = None
            return False

        try:
            await asyncio.wait_for(
                self._client_connected.wait(), timeout=_CONNECT_TIMEOUT
            )
            logger.info("MuseScore plugin connected")
            return True
        except TimeoutError:
            logger.error("Timed out waiting for MuseScore plugin to connect")
            await self._stop_server()
            return False

    async def _stop_server(self) -> None:
        """Stop the WebSocket server."""
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
            self._server = None

    async def disconnect(self) -> None:
        """Close the plugin connection and stop the WebSocket server."""
        if self._connection is not None:
            with contextlib.suppress(websockets.exceptions.WebSocketException, OSError):
                await self._connection.close()
            self._connection = None
        await self._stop_server()
        self._client_connected.clear()
        logger.info("Disconnected from MuseScore")

    async def _send_raw(self, command_json: str) -> dict[str, Any]:
        """Send a raw JSON command string over the active connection."""
        connection = self._connection
        if connection is None:
            return {"error": "No active connection"}

        await connection.send(command_json)
        response_raw = await asyncio.wait_for(
            connection.recv(), timeout=self.RECV_TIMEOUT
        )
        if not isinstance(response_raw, str):
            return {"error": "Received non-text response from MuseScore"}
        logger.debug("Received: %s", response_raw)
        try:
            result: dict[str, Any] = json.loads(response_raw)
        except json.JSONDecodeError as exception:
            return {"error": f"Invalid JSON from MuseScore: {exception}"}
        return result

    async def send_command(
        self, action: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command to MuseScore and return the response.

        If not already connected, starts the server and waits for the plugin
        to connect. Attempts one reconnect on connection failure.

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
            with contextlib.suppress(websockets.exceptions.WebSocketException, OSError):
                if self._connection is not None:
                    await self._connection.close()
            self._connection = None  # type: ignore
            if not await self.connect():
                return {"error": "Lost connection to MuseScore and reconnect failed"}

            # Retry the command once after reconnecting.
            try:
                return await self._send_raw(command_json)
            except Exception as exception:  # noqa: BLE001
                return {"error": f"Command failed after reconnect: {exception}"}

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

    async def get_properties(self) -> dict[str, Any]:
        """Get properties of the current selection.

        Returns cursor info as MuseScore's equivalent of selection properties.
        """
        return await self.get_cursor_info()

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
