"""Bridge to the MuseScore bridge plugin (``musescore/plugin/``).

The plugin runs inside MuseScore Studio and serves a WebSocket. Each
message is ``{"command": <name>, "params": {...}}`` and each reply carries
``result`` or ``error``. The command names here are the plugin's; this
module is the only place they are spelled out on the Python side.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from mcp_score.bridge.base import BridgeError
from mcp_score.bridge.websocket import DEFAULT_HOST, WebSocketBridge

if TYPE_CHECKING:
    from mcp_score.bridge.base import CommandResult, NoteDuration

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

    # ── Reading ─────────────────────────────────────────────────────

    async def get_score(self) -> CommandResult:
        return await self.send_command(MuseScoreCommand.GET_SCORE)

    async def get_cursor_info(self) -> CommandResult:
        return await self.send_command(MuseScoreCommand.GET_CURSOR_INFO)

    async def get_properties(self) -> CommandResult:
        """The cursor position is the closest MuseScore has to selection properties."""
        return await self.get_cursor_info()

    # ── Navigation and selection ────────────────────────────────────

    async def go_to_measure(self, measure: int) -> CommandResult:
        return await self.send_command(
            MuseScoreCommand.GO_TO_MEASURE, {"measure": measure}
        )

    async def go_to_staff(self, staff: int) -> CommandResult:
        return await self.send_command(MuseScoreCommand.GO_TO_STAFF, {"staff": staff})

    async def select_measure(self) -> CommandResult:
        return await self.send_command(MuseScoreCommand.SELECT_CURRENT_MEASURE)

    async def select_range(
        self, start_measure: int, end_measure: int, start_staff: int, end_staff: int
    ) -> CommandResult:
        return await self.send_command(
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
        self, pitch: int, duration: NoteDuration, advance_cursor: bool = True
    ) -> CommandResult:
        return await self.send_command(
            MuseScoreCommand.ADD_NOTE,
            {
                "pitch": pitch,
                "duration": duration._asdict(),
                "advanceCursorAfterAction": advance_cursor,
            },
        )

    async def add_rehearsal_mark(self, text: str) -> CommandResult:
        return await self.send_command(
            MuseScoreCommand.ADD_REHEARSAL_MARK, {"text": text}
        )

    async def add_chord_symbol(self, text: str) -> CommandResult:
        return await self.send_command(
            MuseScoreCommand.ADD_CHORD_SYMBOL, {"text": text}
        )

    async def add_dynamic(self, dynamic: str) -> CommandResult:
        return await self.send_command(MuseScoreCommand.ADD_DYNAMIC, {"type": dynamic})

    async def set_barline(self, barline_type: str) -> CommandResult:
        return await self.send_command(
            MuseScoreCommand.SET_BARLINE, {"type": barline_type}
        )

    async def set_key_signature(self, fifths: int) -> CommandResult:
        return await self.send_command(
            MuseScoreCommand.SET_KEY_SIGNATURE, {"fifths": fifths}
        )

    async def set_time_signature(
        self, numerator: int, denominator: int
    ) -> CommandResult:
        return await self.send_command(
            MuseScoreCommand.SET_TIME_SIGNATURE,
            {"numerator": numerator, "denominator": denominator},
        )

    async def set_tempo(self, bpm: int, text: str | None = None) -> CommandResult:
        params: dict[str, Any] = {"bpm": bpm}
        if text is not None:
            params["text"] = text
        return await self.send_command(MuseScoreCommand.SET_TEMPO, params)

    async def append_measures(self, count: int) -> CommandResult:
        return await self.send_command(
            MuseScoreCommand.APPEND_MEASURES, {"count": count}
        )

    async def transpose(self, semitones: int) -> CommandResult:
        return await self.send_command(
            MuseScoreCommand.TRANSPOSE, {"semitones": semitones}
        )

    async def undo(self) -> CommandResult:
        return await self.send_command(MuseScoreCommand.UNDO)

    async def process_sequence(self, steps: list[dict[str, Any]]) -> CommandResult:
        """Run several plugin commands as one undo step.

        Each step is ``{"action": <command>, "params": {...}}``. If a step
        fails, the plugin rolls the score back to before the sequence.
        """
        return await self.send_command(
            MuseScoreCommand.PROCESS_SEQUENCE, {"sequence": steps}
        )
