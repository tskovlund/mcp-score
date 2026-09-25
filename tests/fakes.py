"""Test doubles shared by the unit tests.

``FakeBridge`` stands in for a score application behind the ``ScoreBridge``
interface: it records every call and answers with canned results, so tool
tests can assert what the application was asked to do without a socket.
The WebSocket helpers build the mock connection that the bridge tests hand
to a patched ``websockets.connect``.
"""

from __future__ import annotations

import json
from typing import Any, NamedTuple
from unittest.mock import AsyncMock

from websockets.protocol import State

from mcp_score.bridge import CommandResult, NoteDuration, ScoreBridge

__all__ = [
    "REMOTE_CONTROL_HANDSHAKE",
    "SESSION_TOKEN",
    "WEBSOCKETS_CONNECT",
    "BridgeCall",
    "FakeBridge",
    "fake_connection",
    "sent_payloads",
]

WEBSOCKETS_CONNECT = "mcp_score.bridge.websocket.websockets.connect"
"""Patch target for the function every bridge opens its connection with."""

DEFAULT_RESULT: CommandResult = {"result": "ok"}


class BridgeCall(NamedTuple):
    """One method call a ``FakeBridge`` received."""

    method: str
    arguments: tuple[Any, ...]


class FakeBridge(ScoreBridge):
    """A ``ScoreBridge`` that records calls and returns canned results.

    Every operation returns a copy of the result registered with
    :meth:`reply` (or :meth:`fail`) for its method name, and
    ``DEFAULT_RESULT`` otherwise.
    """

    def __init__(
        self,
        application_name: str = "FakeApp",
        *,
        is_connected: bool = True,
        content_reading_limitation: str | None = None,
    ) -> None:
        self.calls: list[BridgeCall] = []
        self.connect_succeeds = True
        self.ping_succeeds = True
        self._application_name = application_name
        self._is_connected = is_connected
        self._content_reading_limitation = content_reading_limitation
        self._results: dict[str, CommandResult] = {}

    # ── Test controls ────────────────────────────────────────────────

    @property
    def application_name(self) -> str:
        return self._application_name

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @is_connected.setter
    def is_connected(self, value: bool) -> None:
        self._is_connected = value

    @property
    def content_reading_limitation(self) -> str | None:
        return self._content_reading_limitation

    def reply(self, method: str, result: CommandResult) -> None:
        """Make *method* return *result* from now on."""
        self._results[method] = result

    def fail(self, method: str, message: str) -> None:
        """Make *method* return an ``{"error": message}`` result from now on."""
        self.reply(method, {"error": message})

    def calls_to(self, method: str) -> list[BridgeCall]:
        return [call for call in self.calls if call.method == method]

    def _record(self, method: str, *arguments: Any) -> CommandResult:
        self.calls.append(BridgeCall(method, arguments))
        return dict(self._results.get(method, DEFAULT_RESULT))

    # ── ScoreBridge ──────────────────────────────────────────────────

    async def connect(self) -> bool:
        self._record("connect")
        self._is_connected = self.connect_succeeds
        return self.connect_succeeds

    async def disconnect(self) -> None:
        self._record("disconnect")
        self._is_connected = False

    async def ping(self) -> bool:
        self._record("ping")
        return self.ping_succeeds

    async def send_command(
        self, action: str, params: dict[str, Any] | None = None
    ) -> CommandResult:
        return self._record("send_command", action, params)

    async def get_score(self) -> CommandResult:
        return self._record("get_score")

    async def get_cursor_info(self) -> CommandResult:
        return self._record("get_cursor_info")

    async def get_properties(self) -> CommandResult:
        return self._record("get_properties")

    async def go_to_measure(self, measure: int) -> CommandResult:
        return self._record("go_to_measure", measure)

    async def go_to_staff(self, staff: int) -> CommandResult:
        return self._record("go_to_staff", staff)

    async def select_measure(self) -> CommandResult:
        return self._record("select_measure")

    async def select_range(
        self, start_measure: int, end_measure: int, start_staff: int, end_staff: int
    ) -> CommandResult:
        return self._record(
            "select_range", start_measure, end_measure, start_staff, end_staff
        )

    async def add_note(
        self, pitch: int, duration: NoteDuration, advance_cursor: bool = True
    ) -> CommandResult:
        return self._record("add_note", pitch, duration, advance_cursor)

    async def add_rehearsal_mark(self, text: str) -> CommandResult:
        return self._record("add_rehearsal_mark", text)

    async def add_chord_symbol(self, text: str) -> CommandResult:
        return self._record("add_chord_symbol", text)

    async def add_dynamic(self, dynamic: str) -> CommandResult:
        return self._record("add_dynamic", dynamic)

    async def set_barline(self, barline_type: str) -> CommandResult:
        return self._record("set_barline", barline_type)

    async def set_key_signature(self, fifths: int) -> CommandResult:
        return self._record("set_key_signature", fifths)

    async def set_time_signature(
        self, numerator: int, denominator: int
    ) -> CommandResult:
        return self._record("set_time_signature", numerator, denominator)

    async def set_tempo(self, bpm: int, text: str | None = None) -> CommandResult:
        return self._record("set_tempo", bpm, text)

    async def append_measures(self, count: int) -> CommandResult:
        return self._record("append_measures", count)

    async def transpose(self, semitones: int) -> CommandResult:
        return self._record("transpose", semitones)

    async def undo(self) -> CommandResult:
        return self._record("undo")


# ── WebSocket doubles ────────────────────────────────────────────────


def fake_connection(*replies: Any, state: State = State.OPEN) -> AsyncMock:
    """A mock ``ClientConnection`` whose ``recv`` yields *replies* in order.

    A ``dict`` reply is sent as JSON text; anything else (an exception
    instance, bytes, a malformed string) is handed back as-is so tests can
    exercise the failure paths.
    """
    connection = AsyncMock()
    connection.state = state
    connection.send = AsyncMock()
    connection.recv = AsyncMock(
        side_effect=[
            json.dumps(reply) if isinstance(reply, dict) else reply for reply in replies
        ]
    )
    connection.close = AsyncMock()
    return connection


def sent_payloads(connection: AsyncMock) -> list[dict[str, Any]]:
    """Every JSON message sent over a ``fake_connection``, decoded, in order."""
    return [json.loads(call.args[0]) for call in connection.send.call_args_list]


SESSION_TOKEN = "session-token-123"
"""The token the fake Remote Control server hands out."""

REMOTE_CONTROL_HANDSHAKE: tuple[dict[str, Any], ...] = (
    {"message": "sessiontoken", "sessionToken": SESSION_TOKEN},
    {"message": "response", "code": "kConnected"},
)
"""What a Remote Control server replies during a fresh handshake, in order."""
