"""Tests for the MuseScore bridge: how it frames the plugin's commands.

Connection handling is tested in ``test_websocket_bridge.py``; here a
connected bridge sends to a mock connection and the tests check the
messages the plugin would receive, how its camelCase ``result`` payloads
become the result models, and how its refusals surface.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from mcp_score.bridge import BridgeError
from mcp_score.bridge.musescore import DEFAULT_PORT, MuseScoreBridge
from mcp_score.bridge.results import (
    BarlineSet,
    ChordSymbolAdded,
    CursorInfo,
    CursorPosition,
    Duration,
    DynamicAdded,
    Element,
    KeySignatureSet,
    MeasuresAppended,
    Note,
    NoteAdded,
    Part,
    RehearsalMarkAdded,
    SelectedRange,
    SelectionProperties,
    TempoSet,
    TimeSignature,
    TimeSignatureSet,
    Transposed,
)
from tests.fakes import WEBSOCKETS_CONNECT, fake_connection, sent_payloads

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

type BridgeOperation = Callable[[MuseScoreBridge], Awaitable[BaseModel]]

CHORD_ELEMENT_TYPE = 93
"""MuseScore's element type code for a chord."""

POSITION_REPLY: dict[str, Any] = {"result": {"measure": 3, "staff": 1}}
POSITION = CursorPosition(measure=3, staff=1)

CURSOR_REPLY: dict[str, Any] = {
    "result": {
        "measure": 2,
        "staff": 0,
        "voice": 0,
        "beat": 1,
        "tick": 1920,
        "element": {
            "type": CHORD_ELEMENT_TYPE,
            "notes": [{"pitch": 60, "tpc": 14, "name": "C4"}],
            "duration": {"numerator": 1, "denominator": 4},
        },
    }
}
CURSOR = CursorInfo(
    measure=2,
    staff=0,
    voice=0,
    beat=1,
    tick=1920,
    element=Element(
        type=CHORD_ELEMENT_TYPE,
        notes=[Note(pitch=60, tpc=14, name="C4")],
        duration=Duration(numerator=1, denominator=4),
    ),
)


async def _connected_bridge(*replies: Any) -> tuple[MuseScoreBridge, AsyncMock]:
    """A bridge connected to a mock plugin that answers with *replies*."""
    connection = fake_connection(*replies)
    bridge = MuseScoreBridge()
    with patch(WEBSOCKETS_CONNECT, AsyncMock(return_value=connection)):
        await bridge.connect()
    return bridge, connection


class TestMuseScoreBridgeDefaults:
    def test_default_uri_points_at_plugin_port(self) -> None:
        # Arrange / Act
        bridge = MuseScoreBridge()

        # Assert
        assert bridge.application_name == "MuseScore"
        assert bridge.uri == f"ws://localhost:{DEFAULT_PORT}"
        assert bridge.content_reading_limitation is None


class TestMuseScoreBridgeFraming:
    @pytest.mark.anyio()
    async def test_send_command_with_params_frames_command_and_params(self) -> None:
        # Arrange
        bridge, connection = await _connected_bridge(POSITION_REPLY)

        # Act
        reply = await bridge.send_command("goToMeasure", {"measure": 3})

        # Assert
        assert reply == POSITION_REPLY
        assert sent_payloads(connection) == [
            {"command": "goToMeasure", "params": {"measure": 3}}
        ]

    @pytest.mark.anyio()
    async def test_send_command_without_params_omits_params_key(self) -> None:
        # Arrange
        bridge, connection = await _connected_bridge(POSITION_REPLY)

        # Act
        await bridge.send_command("undo")

        # Assert
        assert sent_payloads(connection) == [{"command": "undo"}]

    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        ("operation", "expected_message", "plugin_result", "expected_result"),
        [
            pytest.param(
                MuseScoreBridge.get_cursor_info,
                {"command": "getCursorInfo"},
                CURSOR_REPLY["result"],
                CURSOR,
                id="get_cursor_info",
            ),
            pytest.param(
                MuseScoreBridge.get_properties,
                {"command": "getCursorInfo"},
                CURSOR_REPLY["result"],
                SelectionProperties(cursor=CURSOR),
                id="get_properties-is-cursor-info",
            ),
            pytest.param(
                partial(MuseScoreBridge.go_to_measure, measure=3),
                {"command": "goToMeasure", "params": {"measure": 3}},
                POSITION_REPLY["result"],
                POSITION,
                id="go_to_measure",
            ),
            pytest.param(
                partial(MuseScoreBridge.go_to_staff, staff=1),
                {"command": "goToStaff", "params": {"staff": 1}},
                POSITION_REPLY["result"],
                POSITION,
                id="go_to_staff",
            ),
            pytest.param(
                MuseScoreBridge.select_measure,
                {"command": "selectCurrentMeasure"},
                POSITION_REPLY["result"],
                POSITION,
                id="select_measure",
            ),
            pytest.param(
                partial(
                    MuseScoreBridge.select_range,
                    start_measure=1,
                    end_measure=8,
                    start_staff=0,
                    end_staff=1,
                ),
                {
                    "command": "selectCustomRange",
                    "params": {
                        "startMeasure": 1,
                        "endMeasure": 8,
                        "startStaff": 0,
                        "endStaff": 1,
                    },
                },
                {"startMeasure": 1, "endMeasure": 8, "startStaff": 0, "endStaff": 1},
                SelectedRange(
                    start_measure=1, end_measure=8, start_staff=0, end_staff=1
                ),
                id="select_range",
            ),
            pytest.param(
                partial(
                    MuseScoreBridge.add_note,
                    pitch=60,
                    duration=Duration(numerator=1, denominator=8),
                    advance_cursor=False,
                ),
                {
                    "command": "addNote",
                    "params": {
                        "pitch": 60,
                        "duration": {"numerator": 1, "denominator": 8},
                        "advanceCursorAfterAction": False,
                    },
                },
                {
                    "pitch": 60,
                    "duration": {"numerator": 1, "denominator": 8},
                    "measure": 3,
                    "staff": 1,
                },
                NoteAdded(
                    measure=3,
                    staff=1,
                    pitch=60,
                    duration=Duration(numerator=1, denominator=8),
                ),
                id="add_note",
            ),
            pytest.param(
                partial(MuseScoreBridge.add_rehearsal_mark, text="A"),
                {"command": "addRehearsalMark", "params": {"text": "A"}},
                {"text": "A", "measure": 3},
                RehearsalMarkAdded(text="A", measure=3),
                id="add_rehearsal_mark",
            ),
            pytest.param(
                partial(MuseScoreBridge.add_chord_symbol, text="Cmaj7"),
                {"command": "addChordSymbol", "params": {"text": "Cmaj7"}},
                {"text": "Cmaj7", "measure": 3},
                ChordSymbolAdded(text="Cmaj7", measure=3),
                id="add_chord_symbol",
            ),
            pytest.param(
                partial(MuseScoreBridge.add_dynamic, dynamic="mf"),
                {"command": "addDynamic", "params": {"type": "mf"}},
                {"dynamic": "mf", "measure": 3},
                DynamicAdded(dynamic="mf", measure=3),
                id="add_dynamic",
            ),
            pytest.param(
                partial(MuseScoreBridge.set_barline, barline_type="endRepeat"),
                {"command": "setBarline", "params": {"type": "endRepeat"}},
                {"barlineType": "endRepeat", "measure": 3},
                BarlineSet(barline_type="endRepeat", measure=3),
                id="set_barline",
            ),
            pytest.param(
                partial(MuseScoreBridge.set_key_signature, fifths=-2),
                {"command": "setKeySignature", "params": {"fifths": -2}},
                {"fifths": -2, "measure": 3},
                KeySignatureSet(fifths=-2, measure=3),
                id="set_key_signature",
            ),
            pytest.param(
                partial(MuseScoreBridge.set_time_signature, numerator=6, denominator=8),
                {
                    "command": "setTimeSignature",
                    "params": {"numerator": 6, "denominator": 8},
                },
                {"numerator": 6, "denominator": 8, "measure": 3},
                TimeSignatureSet(numerator=6, denominator=8, measure=3),
                id="set_time_signature",
            ),
            pytest.param(
                partial(MuseScoreBridge.set_tempo, bpm=120),
                {"command": "setTempo", "params": {"bpm": 120}},
                {"bpm": 120, "text": "Quarter = 120", "measure": 3},
                TempoSet(bpm=120, text="Quarter = 120", measure=3),
                id="set_tempo-without-text",
            ),
            pytest.param(
                partial(MuseScoreBridge.set_tempo, bpm=120, text="Allegro"),
                {"command": "setTempo", "params": {"bpm": 120, "text": "Allegro"}},
                {"bpm": 120, "text": "Allegro", "measure": 3},
                TempoSet(bpm=120, text="Allegro", measure=3),
                id="set_tempo-with-text",
            ),
            pytest.param(
                partial(MuseScoreBridge.append_measures, count=2),
                {"command": "appendMeasures", "params": {"count": 2}},
                {"count": 2, "totalMeasures": 10},
                MeasuresAppended(count=2, total_measures=10),
                id="append_measures",
            ),
            pytest.param(
                partial(MuseScoreBridge.transpose, semitones=-3),
                {"command": "transpose", "params": {"semitones": -3}},
                {"semitones": -3, "notes": 4},
                Transposed(semitones=-3, notes=4),
                id="transpose",
            ),
            pytest.param(
                MuseScoreBridge.undo,
                {"command": "undo"},
                POSITION_REPLY["result"],
                POSITION,
                id="undo",
            ),
        ],
    )
    async def test_operation_sends_plugin_command_and_reads_its_result(
        self,
        operation: BridgeOperation,
        expected_message: dict[str, Any],
        plugin_result: dict[str, Any],
        expected_result: BaseModel,
    ) -> None:
        # Arrange
        bridge, connection = await _connected_bridge({"result": plugin_result})

        # Act
        result = await operation(bridge)

        # Assert
        assert result == expected_result
        assert sent_payloads(connection) == [expected_message]

    @pytest.mark.anyio()
    async def test_get_score_converts_nested_camel_case_keys(self) -> None:
        # Arrange
        bridge, connection = await _connected_bridge(
            {
                "result": {
                    "title": "T",
                    "partCount": 2,
                    "parts": [
                        {"name": "Flute", "startStaff": 0, "endStaff": 0},
                        {"name": "Piano", "startStaff": 1, "endStaff": 2},
                    ],
                    "measureCount": 4,
                    "keySignature": 0,
                    "timeSignature": {"numerator": 4, "denominator": 4},
                }
            }
        )

        # Act
        score = await bridge.get_score()

        # Assert
        assert sent_payloads(connection) == [{"command": "getScore"}]
        assert score.title == "T"
        assert score.part_count == 2
        assert score.measure_count == 4
        assert score.parts == [
            Part(name="Flute", start_staff=0, end_staff=0),
            Part(name="Piano", start_staff=1, end_staff=2),
        ]
        assert score.time_signature == TimeSignature(numerator=4, denominator=4)

    @pytest.mark.anyio()
    async def test_get_score_without_signatures_reads_them_as_none(self) -> None:
        # Arrange: the plugin reports null when there is no cursor to read them from.
        bridge, _ = await _connected_bridge(
            {
                "result": {
                    "title": "",
                    "partCount": 0,
                    "parts": [],
                    "measureCount": 0,
                    "keySignature": None,
                    "timeSignature": None,
                }
            }
        )

        # Act
        score = await bridge.get_score()

        # Assert
        assert score.key_signature is None
        assert score.time_signature is None

    @pytest.mark.anyio()
    async def test_process_sequence_sends_steps_and_returns_raw_reply(self) -> None:
        # Arrange
        steps = [{"action": "goToMeasure", "params": {"measure": 1}}]
        reply = {"result": {"results": [POSITION_REPLY["result"]], "count": 1}}
        bridge, connection = await _connected_bridge(reply)

        # Act
        result = await bridge.process_sequence(steps)

        # Assert
        assert result == reply
        assert sent_payloads(connection) == [
            {"command": "processSequence", "params": {"sequence": steps}}
        ]


class TestMuseScoreBridgeResultContract:
    """The models are the plugin contract: a reply that does not fit is an error."""

    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        "plugin_result",
        [
            pytest.param({"measure": 3, "staff": 1, "voice": 0}, id="extra-field"),
            pytest.param({"measure": 3}, id="missing-field"),
            pytest.param("ok", id="not-an-object"),
        ],
    )
    async def test_reply_that_does_not_match_model_is_a_bridge_error(
        self, plugin_result: Any
    ) -> None:
        # Arrange
        bridge, _ = await _connected_bridge({"result": plugin_result})

        # Act / Assert
        with pytest.raises(BridgeError, match="answered undo with an unexpected reply"):
            await bridge.undo()

    @pytest.mark.anyio()
    async def test_cursor_without_element_reads_element_as_none(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge(
            {
                "result": {
                    "measure": 1,
                    "staff": 0,
                    "voice": 0,
                    "beat": None,
                    "tick": 0,
                    "element": None,
                }
            }
        )

        # Act
        cursor = await bridge.get_cursor_info()

        # Assert
        assert cursor.element is None
        assert cursor.beat is None


class TestMuseScoreBridgeErrors:
    @pytest.mark.anyio()
    async def test_error_reply_raises_with_other_fields_as_details(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge(
            {"error": "Step 3 failed", "failedIndex": 2, "failedAction": "goToMeasure"}
        )

        # Act
        with pytest.raises(BridgeError, match="Step 3 failed") as exc_info:
            await bridge.send_command("processSequence")

        # Assert
        assert exc_info.value.details == {
            "failedIndex": 2,
            "failedAction": "goToMeasure",
        }

    @pytest.mark.anyio()
    async def test_error_reply_to_operation_raises_before_reading_result(
        self,
    ) -> None:
        # Arrange
        bridge, _ = await _connected_bridge({"error": "Measure 9 out of range (1-4)"})

        # Act / Assert
        with pytest.raises(BridgeError, match="out of range"):
            await bridge.go_to_measure(9)


class TestMuseScoreBridgePing:
    @pytest.mark.anyio()
    async def test_ping_with_pong_returns_true(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge({"result": "pong"})

        # Act / Assert
        assert await bridge.ping() is True

    @pytest.mark.anyio()
    async def test_ping_with_unexpected_reply_returns_false(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge({"result": "hello"})

        # Act / Assert
        assert await bridge.ping() is False

    @pytest.mark.anyio()
    async def test_ping_with_error_reply_returns_false(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge({"error": "busy"})

        # Act / Assert
        assert await bridge.ping() is False
