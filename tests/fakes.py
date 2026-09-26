"""Test doubles shared by the unit tests.

``FakeBridge`` stands in for a score application behind the ``ScoreBridge``
interface: it records every call and answers with canned result models, so
tool tests can assert what the application was asked to do without a
socket. The WebSocket helpers build the mock connection that the bridge
tests hand to a patched ``websockets.connect``.
"""

from __future__ import annotations

import json
from typing import Any, NamedTuple
from unittest.mock import AsyncMock, MagicMock

from mcp.server.context import ServerRequestContext
from mcp.server.mcpserver import Context
from pydantic import BaseModel
from websockets.protocol import State

from mcp_score.bridge import BridgeError, BridgeRegistry, CommandResult, ScoreBridge
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
    Part,
    RehearsalMarkAdded,
    ScoreInfo,
    SelectedRange,
    SelectionProperties,
    TempoSet,
    TimeSignature,
    TimeSignatureSet,
    Transposed,
)
from mcp_score.context import AppState, ScoreContext

__all__ = [
    "REMOTE_CONTROL_HANDSHAKE",
    "SESSION_TOKEN",
    "WEBSOCKETS_CONNECT",
    "BridgeCall",
    "FakeBridge",
    "fake_connection",
    "score_context",
    "sent_payloads",
]

PROTOCOL_VERSION = "2025-06-18"


def score_context(registry: BridgeRegistry) -> ScoreContext:
    """The context the SDK would inject for a request on a server holding *registry*."""
    request_context = ServerRequestContext(
        session=MagicMock(),
        lifespan_context=AppState(registry),
        protocol_version=PROTOCOL_VERSION,
        method="tools/call",
    )
    return Context(request_context=request_context)


WEBSOCKETS_CONNECT = "mcp_score.bridge.websocket.websockets.connect"
"""Patch target for the function every bridge opens its connection with."""

_START = CursorPosition(measure=1, staff=0)
_START_CURSOR = CursorInfo(measure=1, staff=0, voice=0, beat=1, tick=0, element=None)
_QUARTER_NOTE = Duration(numerator=1, denominator=4)

DEFAULT_REPLIES: dict[str, BaseModel] = {
    "get_score": ScoreInfo(
        title="Fake Score",
        part_count=1,
        parts=[Part(name="Piano", start_staff=0, end_staff=0)],
        measure_count=8,
        key_signature=0,
        time_signature=TimeSignature(numerator=4, denominator=4),
    ),
    "get_cursor_info": _START_CURSOR,
    "get_properties": SelectionProperties(cursor=_START_CURSOR),
    "go_to_measure": _START,
    "go_to_staff": _START,
    "select_measure": _START,
    "select_range": SelectedRange(
        start_measure=1, end_measure=1, start_staff=0, end_staff=0
    ),
    "add_note": NoteAdded(measure=1, staff=0, pitch=60, duration=_QUARTER_NOTE),
    "add_rehearsal_mark": RehearsalMarkAdded(text="A", measure=1),
    "add_chord_symbol": ChordSymbolAdded(text="C", measure=1),
    "add_dynamic": DynamicAdded(dynamic="mf", measure=1),
    "set_barline": BarlineSet(barline_type="normal", measure=1),
    "set_key_signature": KeySignatureSet(fifths=0, measure=1),
    "set_time_signature": TimeSignatureSet(numerator=4, denominator=4, measure=1),
    "set_tempo": TempoSet(bpm=120, text="Quarter = 120", measure=1),
    "append_measures": MeasuresAppended(count=1, total_measures=9),
    "transpose": Transposed(semitones=0, notes=0),
    "undo": _START,
}
"""What a ``FakeBridge`` answers for each operation unless a test says otherwise."""


class BridgeCall(NamedTuple):
    """One method call a ``FakeBridge`` received."""

    method: str
    arguments: tuple[Any, ...]


class FakeBridge(ScoreBridge):
    """A ``ScoreBridge`` that records calls and returns canned result models.

    Every operation returns the model registered with :meth:`reply` for its
    method name (the entry of ``DEFAULT_REPLIES`` otherwise), or raises the
    ``BridgeError`` registered with :meth:`fail`.
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
        self._replies: dict[str, BaseModel] = {}
        self._failures: dict[str, BridgeError] = {}

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

    def reply(self, method: str, result: BaseModel) -> None:
        """Make *method* return *result* from now on."""
        self._failures.pop(method, None)
        self._replies[method] = result

    def fail(self, method: str, message: str) -> None:
        """Make *method* raise ``BridgeError(message)`` from now on."""
        self._failures[method] = BridgeError(message)

    def calls_to(self, method: str) -> list[BridgeCall]:
        return [call for call in self.calls if call.method == method]

    def _record(self, method: str, *arguments: Any) -> None:
        self.calls.append(BridgeCall(method, arguments))
        if method in self._failures:
            raise self._failures[method]

    def _answer[R: BaseModel](
        self, result_type: type[R], method: str, *arguments: Any
    ) -> R:
        """Record the call and return the reply registered for *method*.

        Raises:
            TypeError: When a test registered a reply of the wrong model.
        """
        self._record(method, *arguments)
        result = self._replies.get(method, DEFAULT_REPLIES[method])
        if not isinstance(result, result_type):
            raise TypeError(
                f"{method} must reply with {result_type.__name__}, "
                f"not {type(result).__name__}"
            )
        return result

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
        self._record("send_command", action, params)
        return {}

    async def get_score(self) -> ScoreInfo:
        return self._answer(ScoreInfo, "get_score")

    async def get_cursor_info(self) -> CursorInfo:
        return self._answer(CursorInfo, "get_cursor_info")

    async def get_properties(self) -> SelectionProperties:
        return self._answer(SelectionProperties, "get_properties")

    async def go_to_measure(self, measure: int) -> CursorPosition:
        return self._answer(CursorPosition, "go_to_measure", measure)

    async def go_to_staff(self, staff: int) -> CursorPosition:
        return self._answer(CursorPosition, "go_to_staff", staff)

    async def select_measure(self) -> CursorPosition:
        return self._answer(CursorPosition, "select_measure")

    async def select_range(
        self, start_measure: int, end_measure: int, start_staff: int, end_staff: int
    ) -> SelectedRange:
        return self._answer(
            SelectedRange,
            "select_range",
            start_measure,
            end_measure,
            start_staff,
            end_staff,
        )

    async def add_note(
        self, pitch: int, duration: Duration, advance_cursor: bool = True
    ) -> NoteAdded:
        return self._answer(NoteAdded, "add_note", pitch, duration, advance_cursor)

    async def add_rehearsal_mark(self, text: str) -> RehearsalMarkAdded:
        return self._answer(RehearsalMarkAdded, "add_rehearsal_mark", text)

    async def add_chord_symbol(self, text: str) -> ChordSymbolAdded:
        return self._answer(ChordSymbolAdded, "add_chord_symbol", text)

    async def add_dynamic(self, dynamic: str) -> DynamicAdded:
        return self._answer(DynamicAdded, "add_dynamic", dynamic)

    async def set_barline(self, barline_type: str) -> BarlineSet:
        return self._answer(BarlineSet, "set_barline", barline_type)

    async def set_key_signature(self, fifths: int) -> KeySignatureSet:
        return self._answer(KeySignatureSet, "set_key_signature", fifths)

    async def set_time_signature(
        self, numerator: int, denominator: int
    ) -> TimeSignatureSet:
        return self._answer(
            TimeSignatureSet, "set_time_signature", numerator, denominator
        )

    async def set_tempo(self, bpm: int, text: str | None = None) -> TempoSet:
        return self._answer(TempoSet, "set_tempo", bpm, text)

    async def append_measures(self, count: int) -> MeasuresAppended:
        return self._answer(MeasuresAppended, "append_measures", count)

    async def transpose(self, semitones: int) -> Transposed:
        return self._answer(Transposed, "transpose", semitones)

    async def undo(self) -> CursorPosition:
        return self._answer(CursorPosition, "undo")


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
