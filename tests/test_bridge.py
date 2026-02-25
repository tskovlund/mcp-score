"""Tests for the MuseScore WebSocket bridge client."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from mcp_score.bridge.musescore import MuseScoreBridge


class TestMuseScoreBridgeInit:
    def test_default_host_and_port(self) -> None:
        # Arrange / Act
        bridge = MuseScoreBridge()

        # Assert
        assert bridge.host == "localhost"
        assert bridge.port == 8765

    def test_custom_host_and_port(self) -> None:
        # Arrange / Act
        bridge = MuseScoreBridge(host="192.168.1.10", port=9999)

        # Assert
        assert bridge.host == "192.168.1.10"
        assert bridge.port == 9999


class TestMuseScoreBridgeUri:
    def test_uri_default(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()

        # Act
        uri = bridge.uri

        # Assert
        assert uri == "ws://localhost:8765"

    def test_uri_custom(self) -> None:
        # Arrange
        bridge = MuseScoreBridge(host="example.com", port=1234)

        # Act
        uri = bridge.uri

        # Assert
        assert uri == "ws://example.com:1234"


class TestMuseScoreBridgeConnection:
    def test_is_connected_initially_false(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()

        # Act / Assert
        assert bridge.is_connected is False

    @pytest.mark.anyio()
    async def test_connect_fails_gracefully_when_no_server(self) -> None:
        # Arrange
        bridge = MuseScoreBridge(host="localhost", port=19999)

        # Act
        connected = await bridge.connect()

        # Assert
        assert connected is False
        assert bridge.is_connected is False

    @pytest.mark.anyio()
    async def test_send_command_returns_error_when_cannot_connect(self) -> None:
        # Arrange
        bridge = MuseScoreBridge(host="localhost", port=19999)

        # Act
        result = await bridge.send_command("ping")

        # Assert
        assert "error" in result
        assert "Cannot connect" in result["error"]

    @pytest.mark.anyio()
    async def test_ping_returns_false_when_not_connected(self) -> None:
        # Arrange
        bridge = MuseScoreBridge(host="localhost", port=19999)

        # Act
        alive = await bridge.ping()

        # Assert
        assert alive is False


class TestMuseScoreBridgeConvenienceMethods:
    """Test that convenience methods call send_command with correct arguments."""

    @pytest.mark.anyio()
    async def test_get_score_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.get_score()

        # Assert
        bridge.send_command.assert_called_once_with("getScore")

    @pytest.mark.anyio()
    async def test_get_cursor_info_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.get_cursor_info()

        # Assert
        bridge.send_command.assert_called_once_with("getCursorInfo")

    @pytest.mark.anyio()
    async def test_go_to_measure_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.go_to_measure(5)

        # Assert
        bridge.send_command.assert_called_once_with("goToMeasure", {"measure": 5})

    @pytest.mark.anyio()
    async def test_go_to_staff_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.go_to_staff(2)

        # Assert
        bridge.send_command.assert_called_once_with("goToStaff", {"staff": 2})

    @pytest.mark.anyio()
    async def test_add_note_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.add_note(pitch=60, duration={"numerator": 1, "denominator": 4})

        # Assert
        bridge.send_command.assert_called_once_with(
            "addNote",
            {
                "pitch": 60,
                "duration": {"numerator": 1, "denominator": 4},
                "advanceCursorAfterAction": True,
            },
        )

    @pytest.mark.anyio()
    async def test_add_rehearsal_mark_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.add_rehearsal_mark("A")

        # Assert
        bridge.send_command.assert_called_once_with("addRehearsalMark", {"text": "A"})

    @pytest.mark.anyio()
    async def test_set_barline_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.set_barline("double")

        # Assert
        bridge.send_command.assert_called_once_with("setBarline", {"type": "double"})

    @pytest.mark.anyio()
    async def test_set_key_signature_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.set_key_signature(-3)

        # Assert
        bridge.send_command.assert_called_once_with("setKeySignature", {"fifths": -3})

    @pytest.mark.anyio()
    async def test_set_time_signature_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.set_time_signature(3, 4)

        # Assert
        bridge.send_command.assert_called_once_with(
            "setTimeSignature",
            {"numerator": 3, "denominator": 4},
        )

    @pytest.mark.anyio()
    async def test_set_tempo_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.set_tempo(120)

        # Assert
        bridge.send_command.assert_called_once_with("setTempo", {"bpm": 120})

    @pytest.mark.anyio()
    async def test_set_tempo_with_text_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.set_tempo(80, text="Adagio")

        # Assert
        bridge.send_command.assert_called_once_with(
            "setTempo", {"bpm": 80, "text": "Adagio"}
        )

    @pytest.mark.anyio()
    async def test_add_chord_symbol_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.add_chord_symbol("Cmaj7")

        # Assert
        bridge.send_command.assert_called_once_with("addChordSymbol", {"text": "Cmaj7"})

    @pytest.mark.anyio()
    async def test_add_dynamic_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.add_dynamic("ff")

        # Assert
        bridge.send_command.assert_called_once_with("addDynamic", {"type": "ff"})

    @pytest.mark.anyio()
    async def test_append_measures_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.append_measures(4)

        # Assert
        bridge.send_command.assert_called_once_with("appendMeasures", {"count": 4})

    @pytest.mark.anyio()
    async def test_undo_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})

        # Act
        await bridge.undo()

        # Assert
        bridge.send_command.assert_called_once_with("undo")

    @pytest.mark.anyio()
    async def test_process_sequence_calls_send_command(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "ok"})
        commands: list[dict[str, Any]] = [
            {"action": "goToMeasure", "params": {"measure": 1}},
            {"action": "addNote", "params": {"pitch": 60}},
        ]

        # Act
        await bridge.process_sequence(commands)

        # Assert
        bridge.send_command.assert_called_once_with(
            "processSequence", {"sequence": commands}
        )

    @pytest.mark.anyio()
    async def test_ping_returns_true_on_pong(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "pong"})

        # Act
        alive = await bridge.ping()

        # Assert
        assert alive is True
        bridge.send_command.assert_called_once_with("ping")

    @pytest.mark.anyio()
    async def test_ping_returns_false_on_non_pong(self) -> None:
        # Arrange
        bridge = MuseScoreBridge()
        bridge.send_command = AsyncMock(return_value={"result": "error"})

        # Act
        alive = await bridge.ping()

        # Assert
        assert alive is False
