"""Shared WebSocket protocol for Steinberg/Avid Remote Control bridges.

Dorico (4+) and Sibelius (2024.3+) both expose a WebSocket server with
the same handshake protocol:

1. Client sends connect message with clientName and handshakeVersion
2. Server responds with a sessionToken message
3. Client sends acceptsessiontoken with the received token
4. Server responds with ``{"message": "response", "code": "kConnected"}``

If a valid session token from a previous connection is provided in step 1,
the server skips the user prompt and responds directly with ``kConnected``.

This module contains the shared protocol implementation. Dorico and Sibelius
bridges are thin subclasses that provide application-specific defaults.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

import websockets

from mcp_score.bridge.base import ScoreBridge

if TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection

__all__ = [
    "DEFAULT_CLIENT_NAME",
    "HANDSHAKE_VERSION",
    "HandshakeError",
    "RemoteControlBridge",
]

logger = logging.getLogger(__name__)

#: Client name presented to the user in the application's connection dialog.
DEFAULT_CLIENT_NAME = "mcp-score"

#: Handshake protocol version.
HANDSHAKE_VERSION = "1.0"

# ── Protocol constants ────────────────────────────────────────────────

#: Response code indicating a successful connection.
RESPONSE_CONNECTED = "kConnected"

#: Response code indicating an error.
RESPONSE_ERROR = "kError"

#: Message type for a session token response from the application.
MESSAGE_SESSION_TOKEN = "sessiontoken"

#: Barline type to command name mapping (shared by Dorico and Sibelius).
BARLINE_COMMANDS: dict[str, str] = {
    "double": "AddBarlineDouble",
    "final": "AddBarlineFinal",
    "startRepeat": "AddBarlineStartRepeat",
    "endRepeat": "AddBarlineEndRepeat",
}


class RemoteControlBridge(ScoreBridge):
    """WebSocket client for the shared Remote Control protocol.

    Both Dorico and Sibelius expose a WebSocket server with the same
    protocol. This class implements all the shared logic. Subclasses
    provide ``application_name`` and ``DEFAULT_PORT``.
    """

    #: Timeout in seconds for receiving a response.
    RECV_TIMEOUT: float = 30.0

    def __init__(
        self,
        application_name: str,
        host: str = "localhost",
        port: int = 0,
        client_name: str = DEFAULT_CLIENT_NAME,
    ) -> None:
        self._application_name = application_name
        self.host = host
        self.port = port
        self.client_name = client_name
        self._connection: ClientConnection | None = None
        self._session_token: str | None = None

    @property
    def application_name(self) -> str:
        """Human-readable application name."""
        return self._application_name

    @property
    def uri(self) -> str:
        """WebSocket URI."""
        return f"ws://{self.host}:{self.port}"

    async def connect(self) -> bool:
        """Connect to the application and perform the handshake.

        Returns:
            True if connected and handshake succeeded, False otherwise.
        """
        try:
            self._connection = await websockets.connect(self.uri)
            logger.info("WebSocket opened to %s at %s", self.application_name, self.uri)
        except (OSError, websockets.exceptions.WebSocketException) as exception:
            logger.error(
                "Failed to connect to %s at %s: %s",
                self.application_name,
                self.uri,
                exception,
            )
            self._connection = None
            return False

        try:
            await self._handshake()
            logger.info(
                "Handshake complete with %s at %s", self.application_name, self.uri
            )
            return True
        except (
            TimeoutError,
            websockets.exceptions.WebSocketException,
            HandshakeError,
        ) as exception:
            logger.error("%s handshake failed: %s", self.application_name, exception)
            await self._close_connection()
            return False

    async def disconnect(self) -> None:
        """Disconnect from the application."""
        if self._connection is not None:
            with contextlib.suppress(
                websockets.exceptions.WebSocketException, TimeoutError
            ):
                await self._send_json({"message": "disconnect"})
            await self._close_connection()
            logger.info("Disconnected from %s", self.application_name)

    async def send_command(
        self, action: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command and return the response.

        Commands are sent as JSON with ``message`` set to ``"command"``,
        ``commandName`` set to the action, and optional ``parameters``.

        Auto-connects if not already connected. Attempts one reconnect
        on connection failure.

        Args:
            action: Command name (e.g. "Edit.Undo").
            params: Optional command parameters.

        Returns:
            Parsed JSON response from the application.
        """
        message: dict[str, Any] = {
            "message": "command",
            "commandName": action,
        }
        if params is not None:
            message["parameters"] = params

        return await self._send_with_reconnect(message)

    async def ping(self) -> bool:
        """Check if the connection is alive by requesting app info."""
        result = await self.get_app_info()
        return "error" not in result

    async def get_score(self) -> dict[str, Any]:
        """Get information about the currently open score."""
        return await self._send_message("getstatus")

    async def get_cursor_info(self) -> dict[str, Any]:
        """Get current selection info.

        These applications do not have a cursor concept like MuseScore.
        This returns the current status which includes selection state.
        """
        return await self._send_message("getstatus")

    async def go_to_measure(self, measure: int) -> dict[str, Any]:
        """Navigate to a specific measure."""
        return await self.send_command("Edit.GoToBar", {"barNumber": str(measure)})

    async def go_to_staff(self, staff: int) -> dict[str, Any]:
        """Navigate to a specific staff.

        The Remote Control API does not support direct staff navigation.
        """
        return {
            "warning": (
                f"{self.application_name}'s Remote Control WebSocket API "
                "does not support direct staff navigation. The API "
                "operates on the current selection; there is no command "
                "to move to a specific staff. Use the application's UI "
                "to select the desired staff."
            )
        }

    async def add_rehearsal_mark(self, text: str) -> dict[str, Any]:
        """Add a rehearsal mark at the current position.

        The Remote Control API does not support specifying rehearsal mark
        text — the application uses its own auto-numbering instead.
        """
        result = await self.send_command("AddRehearsalMark")
        if "error" not in result:
            result.setdefault(
                "warning",
                (
                    f"{self.application_name} ignores the requested text "
                    f"'{text}' and uses auto-numbering for rehearsal marks. "
                    "The WebSocket API can trigger AddRehearsalMark but "
                    "cannot provide text input to the popover."
                ),
            )
        return result

    async def add_chord_symbol(self, text: str) -> dict[str, Any]:
        """Add a chord symbol.

        The Remote Control API cannot set specific chord text
        programmatically.
        """
        return {
            "error": (
                f"{self.application_name}'s Remote Control WebSocket API "
                f"cannot set chord symbol text ('{text}') programmatically. "
                "Chord symbols are entered through a popover in the UI, "
                "and the WebSocket API cannot interact with popovers."
            )
        }

    async def set_barline(self, barline_type: str) -> dict[str, Any]:
        """Set a barline at the current position."""
        command = BARLINE_COMMANDS.get(barline_type)
        if command is None:
            return {
                "error": (
                    f"Unknown barline type '{barline_type}'. "
                    f"Supported: {', '.join(BARLINE_COMMANDS)}"
                )
            }
        return await self.send_command(command)

    async def set_key_signature(self, fifths: int) -> dict[str, Any]:
        """Set the key signature.

        The Remote Control API does not support setting key signatures
        directly.
        """
        return {
            "error": (
                f"{self.application_name}'s Remote Control WebSocket API "
                "does not support setting key signatures. Key signatures "
                "are entered through a popover in the UI, and the "
                "WebSocket API cannot provide popover input."
            )
        }

    async def set_tempo(self, bpm: int, text: str | None = None) -> dict[str, Any]:
        """Set the tempo.

        The Remote Control API does not support setting tempo directly.
        """
        return {
            "error": (
                f"{self.application_name}'s Remote Control WebSocket API "
                "does not support setting tempo. Tempo marks are entered "
                "through a popover in the UI, and the WebSocket API "
                "cannot provide popover input."
            )
        }

    async def undo(self) -> dict[str, Any]:
        """Undo the last action."""
        return await self.send_command("Edit.Undo")

    # ── Application-info methods ──────────────────────────────────────

    async def get_app_info(self) -> dict[str, Any]:
        """Request version information about the application."""
        return await self._send_message("getappinfo", {"info": "version"})

    async def get_commands(self) -> dict[str, Any]:
        """Request the list of available commands."""
        return await self._send_message("getcommands")

    async def get_status(self) -> dict[str, Any]:
        """Request the current status."""
        return await self._send_message("getstatus")

    async def get_properties(self) -> dict[str, Any]:
        """Request properties of the current selection.

        Returns the names, types, and current values of all properties
        on the currently selected items. This is the closest the Remote
        Control API gets to "reading" score data.
        """
        return await self._send_message("getproperties")

    async def get_flows(self) -> dict[str, Any]:
        """Request the list of flows in the current document.

        Flows are a Dorico concept — each flow is an independent piece
        of music within the same project. Sibelius may return limited
        or empty data for this message type.
        """
        return await self._send_message("getflows")

    async def get_layouts(self) -> dict[str, Any]:
        """Request the list of layouts in the current document.

        Layouts control how music is presented (full score, parts, etc.).
        This is primarily a Dorico concept; Sibelius may return limited
        or empty data.
        """
        return await self._send_message("getlayouts")

    # ── Internal protocol methods ─────────────────────────────────────

    async def _handshake(self) -> None:
        """Perform the Remote Control handshake.

        If we have a cached session token, try to reconnect with it.
        Otherwise, do a fresh connect and wait for a new session token.
        """
        if self._session_token is not None:
            await self._handshake_with_session_token()
        else:
            await self._handshake_without_session_token()

    async def _accept_session_token(self, response: dict[str, Any]) -> None:
        """Extract, accept, and store a session token from a server response.

        Raises:
            HandshakeError: If the token is missing, rejected, or the
                server responds unexpectedly.
        """
        session_token = response.get("sessionToken")
        if not session_token or not isinstance(session_token, str):
            raise HandshakeError("No sessionToken in response")

        accept_message = {
            "message": "acceptsessiontoken",
            "sessionToken": session_token,
        }
        accept_response = await self._send_and_receive(accept_message)

        code = accept_response.get("code")
        if code == RESPONSE_ERROR:
            detail = accept_response.get("detail", "unknown error")
            raise HandshakeError(f"Handshake rejected: {detail}")
        if code != RESPONSE_CONNECTED:
            raise HandshakeError(
                f"Expected 'kConnected' after accepting token, got: {accept_response}"
            )

        self._session_token = session_token

    async def _handshake_without_session_token(self) -> None:
        """Fresh handshake: connect -> receive session token -> accept."""
        connect_message = {
            "message": "connect",
            "clientName": self.client_name,
            "handshakeVersion": HANDSHAKE_VERSION,
        }
        response = await self._send_and_receive(connect_message)

        if response.get("message") != MESSAGE_SESSION_TOKEN:
            raise HandshakeError(f"Expected 'sessiontoken' response, got: {response}")

        await self._accept_session_token(response)

    async def _handshake_with_session_token(self) -> None:
        """Reconnect using a cached session token."""
        connect_message = {
            "message": "connect",
            "clientName": self.client_name,
            "handshakeVersion": HANDSHAKE_VERSION,
            "sessionToken": self._session_token,
        }
        response = await self._send_and_receive(connect_message)

        code = response.get("code")
        if code == RESPONSE_CONNECTED:
            return

        # Session token may have expired — try fresh handshake.
        if response.get("message") == MESSAGE_SESSION_TOKEN:
            await self._accept_session_token(response)
            return

        # Unexpected response — invalidate cached token and fail.
        self._session_token = None
        raise HandshakeError(f"Reconnect with session token failed: {response}")

    async def _send_message(
        self,
        message_type: str,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a raw protocol message (not a command).

        Used for protocol-level messages like ``getstatus``,
        ``getappinfo``, ``getcommands``, etc.
        """
        message: dict[str, Any] = {"message": message_type}
        if extra_fields is not None:
            message.update(extra_fields)

        return await self._send_with_reconnect(message)

    async def _send_with_reconnect(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send a message, auto-connecting and retrying once on failure."""
        if self._connection is None and not await self.connect():
            return {"error": f"Cannot connect to {self.application_name} at {self.uri}"}

        try:
            return await self._send_and_receive(message)
        except (
            websockets.exceptions.ConnectionClosed,
            websockets.exceptions.WebSocketException,
            TimeoutError,
        ):
            logger.warning("Connection lost, attempting reconnect...")
            await self._close_connection()
            if not await self.connect():
                return {
                    "error": (
                        f"Lost connection to {self.application_name} "
                        "and reconnect failed"
                    )
                }
            try:
                return await self._send_and_receive(message)
            except Exception as exception:  # noqa: BLE001
                return {"error": f"Request failed after reconnect: {exception}"}

    async def _send_and_receive(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON message and wait for the response."""
        connection = self._connection
        if connection is None:
            return {"error": "No active connection"}

        message_json = json.dumps(message)
        logger.debug("Sending to %s: %s", self.application_name, message_json)
        await connection.send(message_json)

        response_raw = await asyncio.wait_for(
            connection.recv(), timeout=self.RECV_TIMEOUT
        )
        if not isinstance(response_raw, str):
            return {"error": f"Received non-text response from {self.application_name}"}

        logger.debug("Received from %s: %s", self.application_name, response_raw)
        try:
            result: dict[str, Any] = json.loads(response_raw)
        except json.JSONDecodeError as exception:
            return {
                "error": (f"Invalid JSON from {self.application_name}: {exception}")
            }
        return result

    async def _send_json(self, message: dict[str, Any]) -> None:
        """Send a JSON message without waiting for a response."""
        connection = self._connection
        if connection is not None:
            await connection.send(json.dumps(message))

    async def _close_connection(self) -> None:
        """Close the WebSocket connection and clear internal state."""
        if self._connection is not None:
            with contextlib.suppress(websockets.exceptions.WebSocketException, OSError):
                await self._connection.close()
            self._connection = None  # type: ignore


class HandshakeError(Exception):
    """Raised when the Remote Control handshake protocol fails."""
