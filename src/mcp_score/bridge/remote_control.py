"""Bridge to applications that speak the Remote Control WebSocket protocol.

Dorico 4 and later serve this protocol. It is a command-execution and
UI-state layer: the client can trigger any menu action and read the
application status, but cannot read notes or type into popovers. Bridges
built on it answer such requests with an explanatory error instead.

Handshake:

1. Client sends ``connect`` with ``clientName`` and ``handshakeVersion``
2. Server answers with a ``sessiontoken`` message
3. Client sends ``acceptsessiontoken`` with that token
4. Server answers ``{"message": "response", "code": "kConnected"}``

A session token from an earlier connection can be sent with ``connect``;
the server then skips its approval dialog and answers ``kConnected``
directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp_score.bridge.websocket import (
    TransportError,
    WebSocketBridge,
    WebSocketTransport,
)

if TYPE_CHECKING:
    from mcp_score.bridge.base import CommandResult, NoteDuration

__all__ = [
    "DEFAULT_CLIENT_NAME",
    "HANDSHAKE_VERSION",
    "HandshakeError",
    "RemoteControlBridge",
]

DEFAULT_CLIENT_NAME = "mcp-score"
"""Shown to the user in the application's connection-approval dialog."""

HANDSHAKE_VERSION = "1.0"

# Protocol vocabulary.
MESSAGE_CONNECT = "connect"
MESSAGE_ACCEPT_SESSION_TOKEN = "acceptsessiontoken"
MESSAGE_SESSION_TOKEN = "sessiontoken"
MESSAGE_DISCONNECT = "disconnect"
MESSAGE_COMMAND = "command"
RESPONSE_CONNECTED = "kConnected"
RESPONSE_ERROR = "kError"

# Application commands the protocol exposes for our operations.
COMMAND_UNDO = "Edit.Undo"
COMMAND_GO_TO_BAR = "Edit.GoToBar"
COMMAND_ADD_REHEARSAL_MARK = "AddRehearsalMark"
BARLINE_COMMANDS: dict[str, str] = {
    "double": "AddBarlineDouble",
    "final": "AddBarlineFinal",
    "startRepeat": "AddBarlineStartRepeat",
    "endRepeat": "AddBarlineEndRepeat",
}

POPOVER_REASON = "it is entered through a popover, which the API cannot type into"
SELECTION_REASON = "the API acts on the current selection and cannot move it"


class HandshakeError(TransportError):
    """The Remote Control handshake did not complete."""


class RemoteControlBridge(WebSocketBridge):
    """Protocol implementation; subclasses supply the application's defaults."""

    def __init__(
        self,
        application_name: str,
        host: str,
        port: int,
        client_name: str = DEFAULT_CLIENT_NAME,
    ) -> None:
        super().__init__(application_name, host, port)
        self.client_name = client_name
        self._session_token: str | None = None

    @property
    def content_reading_limitation(self) -> str:
        return (
            f"{self.application_name}'s Remote Control API reports application "
            "status and selection properties, not note content. "
            "get_selection_properties gives the most detail."
        )

    # ── Handshake ───────────────────────────────────────────────────

    async def _on_connected(self, transport: WebSocketTransport) -> None:
        connect_message: dict[str, Any] = {
            "message": MESSAGE_CONNECT,
            "clientName": self.client_name,
            "handshakeVersion": HANDSHAKE_VERSION,
        }
        if self._session_token is not None:
            connect_message["sessionToken"] = self._session_token
        reply = await transport.request(connect_message)

        if reply.get("code") == RESPONSE_CONNECTED:
            return  # The cached session token was accepted.
        if reply.get("message") == MESSAGE_SESSION_TOKEN:
            await self._accept_session_token(transport, reply)
            return
        self._session_token = None
        raise HandshakeError(f"unexpected reply to connect: {reply}")

    async def _accept_session_token(
        self, transport: WebSocketTransport, reply: CommandResult
    ) -> None:
        session_token = reply.get("sessionToken")
        if not isinstance(session_token, str) or not session_token:
            raise HandshakeError("no sessionToken in the server's reply")
        accepted = await transport.request(
            {"message": MESSAGE_ACCEPT_SESSION_TOKEN, "sessionToken": session_token}
        )
        code = accepted.get("code")
        if code == RESPONSE_ERROR:
            raise HandshakeError(
                f"handshake rejected: {accepted.get('detail', 'unknown error')}"
            )
        if code != RESPONSE_CONNECTED:
            raise HandshakeError(f"expected {RESPONSE_CONNECTED}, got: {accepted}")
        self._session_token = session_token

    async def _on_disconnecting(self, transport: WebSocketTransport) -> None:
        await transport.send({"message": MESSAGE_DISCONNECT})

    # ── Messages ────────────────────────────────────────────────────

    async def send_command(
        self, action: str, params: dict[str, Any] | None = None
    ) -> CommandResult:
        payload: dict[str, Any] = {"message": MESSAGE_COMMAND, "commandName": action}
        if params is not None:
            payload["parameters"] = params
        return await self._exchange(payload)

    async def send_message(
        self, message_type: str, fields: dict[str, Any] | None = None
    ) -> CommandResult:
        """Send a protocol-level message such as ``getstatus``."""
        return await self._exchange({"message": message_type, **(fields or {})})

    def _unsupported(self, operation: str, reason: str) -> CommandResult:
        return {
            "error": f"{self.application_name}'s Remote Control API cannot "
            f"{operation}: {reason}."
        }

    # ── ScoreBridge ─────────────────────────────────────────────────

    async def ping(self) -> bool:
        return "error" not in await self.get_app_info()

    async def get_score(self) -> CommandResult:
        return await self.get_status()

    async def get_cursor_info(self) -> CommandResult:
        """The application status is the closest the protocol has to a cursor."""
        return await self.get_status()

    async def get_properties(self) -> CommandResult:
        return await self.send_message("getproperties")

    async def go_to_measure(self, measure: int) -> CommandResult:
        return await self.send_command(COMMAND_GO_TO_BAR, {"barNumber": str(measure)})

    async def go_to_staff(self, staff: int) -> CommandResult:
        return self._unsupported(f"move to staff {staff}", SELECTION_REASON)

    async def select_measure(self) -> CommandResult:
        return self._unsupported("select a measure", SELECTION_REASON)

    async def select_range(
        self, start_measure: int, end_measure: int, start_staff: int, end_staff: int
    ) -> CommandResult:
        return self._unsupported("select a range", SELECTION_REASON)

    async def add_note(
        self, pitch: int, duration: NoteDuration, advance_cursor: bool = True
    ) -> CommandResult:
        return self._unsupported("add notes", POPOVER_REASON)

    async def add_rehearsal_mark(self, text: str) -> CommandResult:
        reply = await self.send_command(COMMAND_ADD_REHEARSAL_MARK)
        if "error" not in reply:
            reply.setdefault(
                "warning",
                f"{self.application_name} numbers rehearsal marks itself; "
                f"the requested text {text!r} was ignored.",
            )
        return reply

    async def add_chord_symbol(self, text: str) -> CommandResult:
        return self._unsupported(f"set chord symbol text {text!r}", POPOVER_REASON)

    async def add_dynamic(self, dynamic: str) -> CommandResult:
        return self._unsupported(f"add the dynamic {dynamic!r}", POPOVER_REASON)

    async def set_barline(self, barline_type: str) -> CommandResult:
        command = BARLINE_COMMANDS.get(barline_type)
        if command is None:
            return {
                "error": f"Unknown barline type {barline_type!r}. "
                f"Supported: {', '.join(BARLINE_COMMANDS)}"
            }
        return await self.send_command(command)

    async def set_key_signature(self, fifths: int) -> CommandResult:
        return self._unsupported("set a key signature", POPOVER_REASON)

    async def set_time_signature(
        self, numerator: int, denominator: int
    ) -> CommandResult:
        return self._unsupported("set a time signature", POPOVER_REASON)

    async def set_tempo(self, bpm: int, text: str | None = None) -> CommandResult:
        return self._unsupported("set a tempo", POPOVER_REASON)

    async def append_measures(self, count: int) -> CommandResult:
        return self._unsupported("append measures", POPOVER_REASON)

    async def transpose(self, semitones: int) -> CommandResult:
        return self._unsupported("transpose a selection", POPOVER_REASON)

    async def undo(self) -> CommandResult:
        return await self.send_command(COMMAND_UNDO)

    # ── Application information ─────────────────────────────────────

    async def get_app_info(self) -> CommandResult:
        return await self.send_message("getappinfo", {"info": "version"})

    async def get_commands(self) -> CommandResult:
        return await self.send_message("getcommands")

    async def get_status(self) -> CommandResult:
        return await self.send_message("getstatus")

    async def get_flows(self) -> CommandResult:
        """The flows (independent pieces) in the open project."""
        return await self.send_message("getflows")

    async def get_layouts(self) -> CommandResult:
        """The layouts (full score, parts, ...) of the open project."""
        return await self.send_message("getlayouts")
