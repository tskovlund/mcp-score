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

from mcp_score.bridge.base import BridgeError
from mcp_score.bridge.results import (
    ApplicationReply,
    BarlineSet,
    CursorPosition,
    RehearsalMarkAdded,
    SelectionProperties,
)
from mcp_score.bridge.websocket import (
    TransportError,
    WebSocketBridge,
    WebSocketTransport,
)

if TYPE_CHECKING:
    from mcp_score.bridge.base import CommandResult
    from mcp_score.bridge.results import (
        ChordSymbolAdded,
        CursorInfo,
        Duration,
        DynamicAdded,
        KeySignatureSet,
        MeasuresAppended,
        NoteAdded,
        ScoreInfo,
        SelectedRange,
        TempoSet,
        TimeSignatureSet,
        Transposed,
    )

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
READING_REASON = "the API triggers commands and cannot read the score"


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
        self._measure = 1
        """The measure last navigated to; the protocol cannot report a position."""

    @property
    def content_reading_limitation(self) -> str:
        return (
            f"{self.application_name}'s Remote Control API reads the selection's "
            "properties, not note content."
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

    async def _exchange(self, payload: dict[str, Any]) -> CommandResult:
        reply = await super()._exchange(payload)
        if reply.get("code") == RESPONSE_ERROR:
            raise BridgeError(
                str(reply.get("detail", "the application reported an error"))
            )
        return reply

    def _unsupported(self, operation: str, reason: str) -> BridgeError:
        return BridgeError(
            f"{self.application_name}'s Remote Control API cannot "
            f"{operation}: {reason}."
        )

    # ── ScoreBridge ─────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            await self.get_app_info()
        except BridgeError:
            return False
        return True

    async def get_score(self) -> ScoreInfo:
        raise self._unsupported("describe the score", READING_REASON)

    async def get_cursor_info(self) -> CursorInfo:
        raise self._unsupported("report the cursor", READING_REASON)

    async def get_properties(self) -> SelectionProperties:
        """The properties of the selected items, as the application reports them."""
        reply = await self.send_message("getproperties")
        properties = {key: value for key, value in reply.items() if key != "message"}
        return SelectionProperties(
            properties=ApplicationReply.model_validate(properties)
        )

    async def go_to_measure(self, measure: int) -> CursorPosition:
        await self.send_command(COMMAND_GO_TO_BAR, {"barNumber": str(measure)})
        self._measure = measure
        return self._position()

    async def go_to_staff(self, staff: int) -> CursorPosition:
        raise self._unsupported(f"move to staff {staff}", SELECTION_REASON)

    async def select_measure(self) -> CursorPosition:
        raise self._unsupported("select a measure", SELECTION_REASON)

    async def select_range(
        self, start_measure: int, end_measure: int, start_staff: int, end_staff: int
    ) -> SelectedRange:
        raise self._unsupported("select a range", SELECTION_REASON)

    async def add_note(
        self, pitch: int, duration: Duration, advance_cursor: bool = True
    ) -> NoteAdded:
        raise self._unsupported("add notes", POPOVER_REASON)

    async def add_rehearsal_mark(self, text: str) -> RehearsalMarkAdded:
        await self.send_command(COMMAND_ADD_REHEARSAL_MARK)
        return RehearsalMarkAdded(
            text=text,
            measure=self._measure,
            warning=f"{self.application_name} numbers rehearsal marks itself; "
            f"the requested text {text!r} was ignored.",
        )

    async def add_chord_symbol(self, text: str) -> ChordSymbolAdded:
        raise self._unsupported(f"set chord symbol text {text!r}", POPOVER_REASON)

    async def add_dynamic(self, dynamic: str) -> DynamicAdded:
        raise self._unsupported(f"add the dynamic {dynamic!r}", POPOVER_REASON)

    async def set_barline(self, barline_type: str) -> BarlineSet:
        command = BARLINE_COMMANDS.get(barline_type)
        if command is None:
            raise BridgeError(
                f"Unknown barline type {barline_type!r}. "
                f"Supported: {', '.join(BARLINE_COMMANDS)}"
            )
        await self.send_command(command)
        return BarlineSet(barline_type=barline_type, measure=self._measure)

    async def set_key_signature(self, fifths: int) -> KeySignatureSet:
        raise self._unsupported("set a key signature", POPOVER_REASON)

    async def set_time_signature(
        self, numerator: int, denominator: int
    ) -> TimeSignatureSet:
        raise self._unsupported("set a time signature", POPOVER_REASON)

    async def set_tempo(self, bpm: int, text: str | None = None) -> TempoSet:
        raise self._unsupported("set a tempo", POPOVER_REASON)

    async def append_measures(self, count: int) -> MeasuresAppended:
        raise self._unsupported("append measures", POPOVER_REASON)

    async def transpose(self, semitones: int) -> Transposed:
        raise self._unsupported("transpose a selection", POPOVER_REASON)

    async def undo(self) -> CursorPosition:
        await self.send_command(COMMAND_UNDO)
        return self._position()

    def _position(self) -> CursorPosition:
        """The last measure navigated to; the protocol has no staves."""
        return CursorPosition(measure=self._measure, staff=0)

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
