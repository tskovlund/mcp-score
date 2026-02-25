"""WebSocket client for the Dorico Remote Control API.

Dorico 4+ has a built-in WebSocket server (default port 4560). The protocol
uses a two-step handshake:

1. Client sends connect message with clientName and handshakeVersion
2. Dorico responds with a sessionToken message
3. Client sends acceptsessiontoken with the received token
4. Dorico responds with ``{"message": "response", "code": "kConnected"}``

If a valid session token from a previous connection is provided in step 1,
Dorico skips the user prompt and responds directly with ``kConnected``.

Protocol details reverse-engineered from github.com/scott-janssens/Dorico.Net.
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

__all__ = ["DoricoBridge"]

logger = logging.getLogger(__name__)

#: Client name presented to the user in Dorico's connection dialog.
DEFAULT_CLIENT_NAME = "mcp-score"

#: Handshake protocol version.
HANDSHAKE_VERSION = "1.0"


class DoricoBridge(ScoreBridge):
    """WebSocket client for the Dorico Remote Control API.

    Connects to Dorico's built-in WebSocket server and communicates
    using the Remote Control protocol. Unlike MuseScore, no plugin is
    needed — Dorico IS the server.
    """

    #: Timeout in seconds for receiving a response from Dorico.
    RECV_TIMEOUT: float = 30.0

    def __init__(
        self,
        host: str = "localhost",
        port: int = 4560,
        client_name: str = DEFAULT_CLIENT_NAME,
    ) -> None:
        self.host = host
        self.port = port
        self.client_name = client_name
        self._connection: ClientConnection | None = None
        self._session_token: str | None = None

    @property
    def application_name(self) -> str:
        """Human-readable application name."""
        return "Dorico"

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
        try:
            return conn.protocol.state.name == "OPEN"  # pyright: ignore[reportUnknownMemberType]
        except AttributeError:
            return False  # Fallback: assume disconnected if state is unknown

    async def connect(self) -> bool:
        """Connect to Dorico and perform the handshake.

        Returns:
            True if connected and handshake succeeded, False otherwise.
        """
        try:
            self._connection = await websockets.connect(self.uri)
            logger.info("WebSocket opened to Dorico at %s", self.uri)
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            logger.error("Failed to connect to Dorico at %s: %s", self.uri, exc)
            self._connection = None
            return False

        try:
            await self._handshake()
            logger.info("Handshake complete with Dorico at %s", self.uri)
            return True
        except (
            TimeoutError,
            websockets.exceptions.WebSocketException,
            HandshakeError,
        ) as exc:
            logger.error("Dorico handshake failed: %s", exc)
            await self._close_connection()
            return False

    async def disconnect(self) -> None:
        """Disconnect from Dorico."""
        if self._connection is not None:
            with contextlib.suppress(
                websockets.exceptions.WebSocketException, TimeoutError
            ):
                await self._send_json({"message": "disconnect"})
            await self._close_connection()
            logger.info("Disconnected from Dorico")

    async def send_command(
        self, action: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command to Dorico and return the response.

        Dorico commands are sent as JSON messages with a ``message`` field
        set to ``"command"``, a ``commandName`` field, and optional parameters.

        Auto-connects if not already connected. Attempts one reconnect
        on connection failure.

        Args:
            action: Command name (e.g. "Edit.Undo").
            params: Optional command parameters.

        Returns:
            Parsed JSON response from Dorico.
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
        """Get information about the currently open score.

        Uses Dorico's ``getstatus`` message to retrieve score state.
        """
        return await self._send_message("getstatus")

    async def get_cursor_info(self) -> dict[str, Any]:
        """Get current selection info.

        Dorico does not have a cursor concept like MuseScore. This returns
        the current status which includes selection state.
        """
        return await self._send_message("getstatus")

    async def go_to_measure(self, measure: int) -> dict[str, Any]:
        """Navigate to a specific measure.

        Dorico's Remote Control API has limited navigation support.
        This uses the ``Edit.GoToBar`` command.
        """
        return await self.send_command("Edit.GoToBar", {"barNumber": str(measure)})

    async def go_to_staff(self, staff: int) -> dict[str, Any]:
        """Navigate to a specific staff.

        Dorico's API does not support direct staff navigation. Returns
        a descriptive limitation message.
        """
        return {
            "warning": (
                "Dorico's Remote Control API does not support direct "
                "staff navigation. Use Dorico's UI to select the "
                "desired staff."
            )
        }

    async def add_rehearsal_mark(self, text: str) -> dict[str, Any]:
        """Add a rehearsal mark at the current position.

        Dorico's Remote Control API does not support specifying the
        rehearsal mark text — it uses Dorico's auto-numbering instead.
        """
        result = await self.send_command("AddRehearsalMark")
        if "error" not in result:
            result.setdefault(
                "warning",
                (
                    f"Dorico ignores the requested text '{text}' and uses "
                    "its own auto-numbering for rehearsal marks."
                ),
            )
        return result

    async def add_chord_symbol(self, text: str) -> dict[str, Any]:
        """Add a chord symbol.

        Dorico's Remote Control API can only enter chord input mode —
        it cannot set specific chord text programmatically.
        """
        return {
            "error": (
                "Dorico's Remote Control API cannot set chord symbol text "
                f"('{text}') programmatically. Use Dorico's UI to enter "
                "chord symbols."
            )
        }

    async def set_barline(self, barline_type: str) -> dict[str, Any]:
        """Set a barline at the current position."""
        dorico_barline_map: dict[str, str] = {
            "double": "AddBarlineDouble",
            "final": "AddBarlineFinal",
            "startRepeat": "AddBarlineStartRepeat",
            "endRepeat": "AddBarlineEndRepeat",
        }
        command = dorico_barline_map.get(barline_type)
        if command is None:
            return {
                "error": (
                    f"Unknown barline type '{barline_type}'. "
                    f"Supported: {', '.join(dorico_barline_map)}"
                )
            }
        return await self.send_command(command)

    async def set_key_signature(self, fifths: int) -> dict[str, Any]:
        """Set the key signature.

        Dorico's Remote Control API does not support setting key signatures
        directly via commands. This is a known limitation.
        """
        return {
            "error": (
                "Dorico's Remote Control API does not support setting "
                "key signatures directly. Use Dorico's UI instead."
            )
        }

    async def set_tempo(self, bpm: int, text: str | None = None) -> dict[str, Any]:
        """Set the tempo.

        Dorico's Remote Control API has limited tempo manipulation
        support. Fixed tempo mode can be toggled via status properties.
        """
        return {
            "error": (
                "Dorico's Remote Control API does not support setting "
                "tempo directly. Use Dorico's UI instead."
            )
        }

    async def undo(self) -> dict[str, Any]:
        """Undo the last action."""
        return await self.send_command("Edit.Undo")

    # ── Dorico-specific methods ──────────────────────────────────────

    async def get_app_info(self) -> dict[str, Any]:
        """Request version information about the Dorico instance."""
        return await self._send_message("getappinfo", {"info": "version"})

    async def get_commands(self) -> dict[str, Any]:
        """Request the list of available commands from Dorico."""
        return await self._send_message("getcommands")

    async def get_status(self) -> dict[str, Any]:
        """Request the current status from Dorico."""
        return await self._send_message("getstatus")

    # ── Internal protocol methods ────────────────────────────────────

    async def _handshake(self) -> None:
        """Perform the Dorico Remote Control handshake.

        If we have a cached session token, try to reconnect with it.
        Otherwise, do a fresh connect and wait for a new session token.
        """
        if self._session_token is not None:
            await self._handshake_with_session_token()
        else:
            await self._handshake_without_session_token()

    async def _handshake_without_session_token(self) -> None:
        """Fresh handshake: connect -> receive session token -> accept."""
        connect_message = {
            "message": "connect",
            "clientName": self.client_name,
            "handshakeVersion": HANDSHAKE_VERSION,
        }
        response = await self._send_and_receive(connect_message)

        if response.get("message") != "sessiontoken":
            raise HandshakeError(f"Expected 'sessiontoken' response, got: {response}")

        session_token = response.get("sessionToken")
        if not session_token or not isinstance(session_token, str):
            raise HandshakeError("No sessionToken in response")

        accept_message = {
            "message": "acceptsessiontoken",
            "sessionToken": session_token,
        }
        accept_response = await self._send_and_receive(accept_message)

        code = accept_response.get("code")
        if code == "kError":
            detail = accept_response.get("detail", "unknown error")
            raise HandshakeError(f"Handshake rejected: {detail}")
        if code != "kConnected":
            raise HandshakeError(
                f"Expected 'kConnected' after accepting token, got: {accept_response}"
            )

        self._session_token = session_token

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
        if code == "kConnected":
            return

        # Session token may have expired — try fresh handshake.
        if response.get("message") == "sessiontoken":
            session_token = response.get("sessionToken")
            if not session_token or not isinstance(session_token, str):
                raise HandshakeError("No sessionToken in response")

            accept_message = {
                "message": "acceptsessiontoken",
                "sessionToken": session_token,
            }
            accept_response = await self._send_and_receive(accept_message)

            code = accept_response.get("code")
            if code == "kError":
                detail = accept_response.get("detail", "unknown error")
                raise HandshakeError(f"Handshake rejected: {detail}")
            self._session_token = session_token
            return

        # Unexpected response — invalidate cached token and fail.
        self._session_token = None
        raise HandshakeError(f"Reconnect with session token failed: {response}")

    async def _send_message(
        self,
        message_type: str,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a raw Dorico protocol message (not a command).

        Used for protocol-level messages like ``getstatus``, ``getappinfo``,
        ``getcommands``, etc.
        """
        message: dict[str, Any] = {"message": message_type}
        if extra_fields is not None:
            message.update(extra_fields)

        return await self._send_with_reconnect(message)

    async def _send_with_reconnect(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send a message, auto-connecting and retrying once on failure."""
        if self._connection is None and not await self.connect():
            return {"error": f"Cannot connect to Dorico at {self.uri}"}

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
                return {"error": "Lost connection to Dorico and reconnect failed"}
            try:
                return await self._send_and_receive(message)
            except Exception as exc:  # noqa: BLE001
                return {"error": f"Request failed after reconnect: {exc}"}

    async def _send_and_receive(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON message and wait for the response."""
        conn = self._connection
        if conn is None:
            return {"error": "No active connection"}

        message_json = json.dumps(message)
        logger.debug("Sending to Dorico: %s", message_json)
        await conn.send(message_json)

        response_raw = await asyncio.wait_for(conn.recv(), timeout=self.RECV_TIMEOUT)
        if not isinstance(response_raw, str):
            return {"error": "Received non-text response from Dorico"}

        logger.debug("Received from Dorico: %s", response_raw)
        try:
            result: dict[str, Any] = json.loads(response_raw)
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid JSON from Dorico: {exc}"}
        return result

    async def _send_json(self, message: dict[str, Any]) -> None:
        """Send a JSON message without waiting for a response."""
        conn = self._connection
        if conn is not None:
            await conn.send(json.dumps(message))

    async def _close_connection(self) -> None:
        """Close the WebSocket connection and clear internal state."""
        if self._connection is not None:
            with contextlib.suppress(websockets.exceptions.WebSocketException):
                await self._connection.close()
            self._connection = None


class HandshakeError(Exception):
    """Raised when the Dorico handshake protocol fails."""
