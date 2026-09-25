"""Tests for the MuseScore bridge: how it frames the plugin's commands.

Connection handling is tested in ``test_websocket_bridge.py``; here a
connected bridge sends to a mock connection and the tests check the
messages the plugin would receive.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from mcp_score.bridge import NoteDuration
from mcp_score.bridge.musescore import DEFAULT_PORT, MuseScoreBridge
from tests.fakes import WEBSOCKETS_CONNECT, fake_connection, sent_payloads

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from mcp_score.bridge import CommandResult

type BridgeOperation = Callable[[MuseScoreBridge], Awaitable[CommandResult]]

OK: dict[str, Any] = {"result": "ok"}


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
        bridge, connection = await _connected_bridge(OK)

        # Act
        reply = await bridge.send_command("goToMeasure", {"measure": 3})

        # Assert
        assert reply == OK
        assert sent_payloads(connection) == [
            {"command": "goToMeasure", "params": {"measure": 3}}
        ]

    @pytest.mark.anyio()
    async def test_send_command_without_params_omits_params_key(self) -> None:
        # Arrange
        bridge, connection = await _connected_bridge(OK)

        # Act
        await bridge.send_command("undo")

        # Assert
        assert sent_payloads(connection) == [{"command": "undo"}]

    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        ("operation", "expected_message"),
        [
            pytest.param(
                MuseScoreBridge.get_score,
                {"command": "getScore"},
                id="get_score",
            ),
            pytest.param(
                MuseScoreBridge.get_properties,
                {"command": "getCursorInfo"},
                id="get_properties-is-cursor-info",
            ),
            pytest.param(
                partial(MuseScoreBridge.go_to_staff, staff=2),
                {"command": "goToStaff", "params": {"staff": 2}},
                id="go_to_staff",
            ),
            pytest.param(
                MuseScoreBridge.select_measure,
                {"command": "selectCurrentMeasure"},
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
                id="select_range",
            ),
            pytest.param(
                partial(
                    MuseScoreBridge.add_note,
                    pitch=60,
                    duration=NoteDuration(1, 8),
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
                id="add_note",
            ),
            pytest.param(
                partial(MuseScoreBridge.add_dynamic, dynamic="mf"),
                {"command": "addDynamic", "params": {"type": "mf"}},
                id="add_dynamic",
            ),
            pytest.param(
                partial(MuseScoreBridge.set_barline, barline_type="endRepeat"),
                {"command": "setBarline", "params": {"type": "endRepeat"}},
                id="set_barline",
            ),
            pytest.param(
                partial(MuseScoreBridge.set_time_signature, numerator=6, denominator=8),
                {
                    "command": "setTimeSignature",
                    "params": {"numerator": 6, "denominator": 8},
                },
                id="set_time_signature",
            ),
            pytest.param(
                partial(MuseScoreBridge.set_tempo, bpm=120),
                {"command": "setTempo", "params": {"bpm": 120}},
                id="set_tempo-without-text",
            ),
            pytest.param(
                partial(MuseScoreBridge.set_tempo, bpm=120, text="Allegro"),
                {"command": "setTempo", "params": {"bpm": 120, "text": "Allegro"}},
                id="set_tempo-with-text",
            ),
            pytest.param(
                partial(MuseScoreBridge.transpose, semitones=-3),
                {"command": "transpose", "params": {"semitones": -3}},
                id="transpose",
            ),
            pytest.param(
                partial(
                    MuseScoreBridge.process_sequence,
                    steps=[{"action": "goToMeasure", "params": {"measure": 1}}],
                ),
                {
                    "command": "processSequence",
                    "params": {
                        "sequence": [
                            {"action": "goToMeasure", "params": {"measure": 1}}
                        ]
                    },
                },
                id="process_sequence",
            ),
        ],
    )
    async def test_operation_sends_plugin_command(
        self, operation: BridgeOperation, expected_message: dict[str, Any]
    ) -> None:
        # Arrange
        bridge, connection = await _connected_bridge(OK)

        # Act
        reply = await operation(bridge)

        # Assert
        assert reply == OK
        assert sent_payloads(connection) == [expected_message]


class TestMuseScoreBridgePing:
    @pytest.mark.anyio()
    async def test_ping_with_pong_returns_true(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge({"result": "pong"})

        # Act / Assert
        assert await bridge.ping() is True

    @pytest.mark.anyio()
    async def test_ping_with_error_reply_returns_false(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge({"error": "no score open"})

        # Act / Assert
        assert await bridge.ping() is False
