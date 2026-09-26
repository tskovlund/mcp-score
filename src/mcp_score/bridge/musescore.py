"""Bridge to the MuseScore bridge plugin (``musescore/plugin/``).

The plugin runs inside MuseScore Studio and serves a WebSocket. Each
message is ``{"command": <name>, "params": {...}}`` and each reply carries
``result`` or ``error``. The command names here are the plugin's; this
module is the only place they are spelled out on the Python side.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError
from pydantic.alias_generators import to_snake

from mcp_score.bridge.base import BridgeError
from mcp_score.bridge.results import (
    BarlineSet,
    ChordSymbolAdded,
    CursorInfo,
    CursorPosition,
    DynamicAdded,
    KeySignatureSet,
    MeasuresAppended,
    NoteAdded,
    RehearsalMarkAdded,
    Result,
    ScoreInfo,
    SelectedRange,
    SelectionProperties,
    TempoSet,
    TimeSignatureSet,
    Transposed,
)
from mcp_score.bridge.websocket import DEFAULT_HOST, WebSocketBridge

if TYPE_CHECKING:
    from mcp_score.bridge.base import CommandResult
    from mcp_score.bridge.results import Duration

__all__ = ["DEFAULT_PORT", "MuseScoreBridge", "MuseScoreCommand"]

DEFAULT_PORT = 8765
"""The port the plugin listens on."""

APPLICATION_NAME = "MuseScore"


class MuseScoreCommand(StrEnum):
    """Commands the plugin understands."""

    PING = "ping"
    GET_SCORE = "getScore"
    GET_CURSOR_INFO = "getCursorInfo"
    GO_TO_MEASURE = "goToMeasure"
    GO_TO_STAFF = "goToStaff"
    ADD_NOTE = "addNote"
    ADD_REHEARSAL_MARK = "addRehearsalMark"
    ADD_CHORD_SYMBOL = "addChordSymbol"
    ADD_DYNAMIC = "addDynamic"
    SET_BARLINE = "setBarline"
    SET_KEY_SIGNATURE = "setKeySignature"
    SET_TIME_SIGNATURE = "setTimeSignature"
    SET_TEMPO = "setTempo"
    APPEND_MEASURES = "appendMeasures"
    SELECT_CURRENT_MEASURE = "selectCurrentMeasure"
    SELECT_CUSTOM_RANGE = "selectCustomRange"
    TRANSPOSE = "transpose"
    UNDO = "undo"
    PROCESS_SEQUENCE = "processSequence"


class MuseScoreBridge(WebSocketBridge):
    """Typed client for every plugin command."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        super().__init__(APPLICATION_NAME, host, port)

    async def send_command(
        self, action: str, params: dict[str, Any] | None = None
    ) -> CommandResult:
        payload: dict[str, Any] = {"command": action}
        if params is not None:
            payload["params"] = params
        reply = await self._exchange(payload)
        if "error" in reply:
            details = {key: value for key, value in reply.items() if key != "error"}
            raise BridgeError(str(reply["error"]), **details)
        return reply

    async def ping(self) -> bool:
        try:
            reply = await self.send_command(MuseScoreCommand.PING)
        except BridgeError:
            return False
        return reply.get("result") == "pong"

    async def _run[R: Result](
        self, result_type: type[R], action: str, params: dict[str, Any] | None = None
    ) -> R:
        """Run a plugin command and read its ``result`` as *result_type*.

        The plugin names its fields in camelCase, as the QML side does;
        the models use the Python names.

        Raises:
            BridgeError: When the reply does not have the shape the model
                describes, which means the plugin and this bridge disagree.
        """
        reply = await self.send_command(action, params)
        try:
            return result_type.model_validate(_snake_case_keys(reply.get("result")))
        except ValidationError as error:
            raise BridgeError(
                f"{self.application_name}'s plugin answered {action} with an "
                f"unexpected reply: {error}"
            ) from error

    # ── Reading ─────────────────────────────────────────────────────

    async def get_score(self) -> ScoreInfo:
        return await self._run(ScoreInfo, MuseScoreCommand.GET_SCORE)

    async def get_cursor_info(self) -> CursorInfo:
        return await self._run(CursorInfo, MuseScoreCommand.GET_CURSOR_INFO)

    async def get_properties(self) -> SelectionProperties:
        """The cursor position is the closest MuseScore has to selection properties."""
        return SelectionProperties(cursor=await self.get_cursor_info())

    # ── Navigation and selection ────────────────────────────────────

    async def go_to_measure(self, measure: int) -> CursorPosition:
        return await self._run(
            CursorPosition, MuseScoreCommand.GO_TO_MEASURE, {"measure": measure}
        )

    async def go_to_staff(self, staff: int) -> CursorPosition:
        return await self._run(
            CursorPosition, MuseScoreCommand.GO_TO_STAFF, {"staff": staff}
        )

    async def select_measure(self) -> CursorPosition:
        return await self._run(CursorPosition, MuseScoreCommand.SELECT_CURRENT_MEASURE)

    async def select_range(
        self, start_measure: int, end_measure: int, start_staff: int, end_staff: int
    ) -> SelectedRange:
        return await self._run(
            SelectedRange,
            MuseScoreCommand.SELECT_CUSTOM_RANGE,
            {
                "startMeasure": start_measure,
                "endMeasure": end_measure,
                "startStaff": start_staff,
                "endStaff": end_staff,
            },
        )

    # ── Writing ─────────────────────────────────────────────────────

    async def add_note(
        self, pitch: int, duration: Duration, advance_cursor: bool = True
    ) -> NoteAdded:
        return await self._run(
            NoteAdded,
            MuseScoreCommand.ADD_NOTE,
            {
                "pitch": pitch,
                "duration": duration.model_dump(),
                "advanceCursorAfterAction": advance_cursor,
            },
        )

    async def add_rehearsal_mark(self, text: str) -> RehearsalMarkAdded:
        return await self._run(
            RehearsalMarkAdded, MuseScoreCommand.ADD_REHEARSAL_MARK, {"text": text}
        )

    async def add_chord_symbol(self, text: str) -> ChordSymbolAdded:
        return await self._run(
            ChordSymbolAdded, MuseScoreCommand.ADD_CHORD_SYMBOL, {"text": text}
        )

    async def add_dynamic(self, dynamic: str) -> DynamicAdded:
        return await self._run(
            DynamicAdded, MuseScoreCommand.ADD_DYNAMIC, {"type": dynamic}
        )

    async def set_barline(self, barline_type: str) -> BarlineSet:
        return await self._run(
            BarlineSet, MuseScoreCommand.SET_BARLINE, {"type": barline_type}
        )

    async def set_key_signature(self, fifths: int) -> KeySignatureSet:
        return await self._run(
            KeySignatureSet, MuseScoreCommand.SET_KEY_SIGNATURE, {"fifths": fifths}
        )

    async def set_time_signature(
        self, numerator: int, denominator: int
    ) -> TimeSignatureSet:
        return await self._run(
            TimeSignatureSet,
            MuseScoreCommand.SET_TIME_SIGNATURE,
            {"numerator": numerator, "denominator": denominator},
        )

    async def set_tempo(self, bpm: int, text: str | None = None) -> TempoSet:
        params: dict[str, Any] = {"bpm": bpm}
        if text is not None:
            params["text"] = text
        return await self._run(TempoSet, MuseScoreCommand.SET_TEMPO, params)

    async def append_measures(self, count: int) -> MeasuresAppended:
        return await self._run(
            MeasuresAppended, MuseScoreCommand.APPEND_MEASURES, {"count": count}
        )

    async def transpose(self, semitones: int) -> Transposed:
        return await self._run(
            Transposed, MuseScoreCommand.TRANSPOSE, {"semitones": semitones}
        )

    async def undo(self) -> CursorPosition:
        return await self._run(CursorPosition, MuseScoreCommand.UNDO)

    async def process_sequence(self, steps: list[dict[str, Any]]) -> CommandResult:
        """Run several plugin commands as one undo step.

        Each step is ``{"action": <command>, "params": {...}}``. If a step
        fails, the plugin rolls the score back to before the sequence.
        """
        return await self.send_command(
            MuseScoreCommand.PROCESS_SEQUENCE, {"sequence": steps}
        )


def _snake_case_keys(value: object) -> object:
    """*value* with every mapping key, at any depth, converted to snake_case."""
    if isinstance(value, dict):
        entries = cast("dict[object, object]", value).items()
        return {to_snake(str(key)): _snake_case_keys(item) for key, item in entries}
    if isinstance(value, list):
        return [_snake_case_keys(item) for item in cast("list[object]", value)]
    return value
