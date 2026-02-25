"""Tests for MCP tool modules — validation, helpers, and tool behavior."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from mcp_score.tools import (
    NOT_CONNECTED,
    check_measure,
    connected_bridge,
    to_json,
)

# ── Helper tests ─────────────────────────────────────────────────────


class TestToJson:
    def test_serializes_dict(self) -> None:
        # Arrange
        data = {"success": True, "message": "ok"}

        # Act
        result = to_json(data)

        # Assert
        assert json.loads(result) == data

    def test_serializes_nested_dict(self) -> None:
        # Arrange
        data = {"result": {"measures": [1, 2, 3]}}

        # Act
        result = to_json(data)

        # Assert
        assert json.loads(result) == data


class TestCheckMeasure:
    def test_returns_none_for_valid_measure(self) -> None:
        # Act / Assert
        assert check_measure(1) is None
        assert check_measure(100) is None

    def test_returns_error_for_zero(self) -> None:
        # Act
        result = check_measure(0)

        # Assert
        assert result is not None
        assert "must be >= 1" in result

    def test_returns_error_for_negative(self) -> None:
        # Act
        result = check_measure(-5)

        # Assert
        assert result is not None
        assert "must be >= 1" in result

    def test_uses_custom_name_in_error(self) -> None:
        # Act
        result = check_measure(0, "start_measure")

        # Assert
        assert result is not None
        assert "start_measure" in result


class TestConnectedBridge:
    def test_returns_bridge_when_connected(self) -> None:
        # Arrange
        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = connected_bridge()

        # Assert
        assert result is mock_bridge

    def test_returns_none_when_disconnected(self) -> None:
        # Arrange
        mock_bridge = AsyncMock()
        mock_bridge.is_connected = False

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = connected_bridge()

        # Assert
        assert result is None

    def test_returns_none_when_no_active_bridge(self) -> None:
        # Arrange / Act
        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            result = connected_bridge()

        # Assert
        assert result is None


# ── Connection tool tests ────────────────────────────────────────────


class TestConnectToMusescore:
    @pytest.mark.anyio()
    async def test_connect_success(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_musescore

        mock_bridge = AsyncMock()
        mock_bridge.connect = AsyncMock(return_value=True)
        mock_bridge.is_connected = False

        with (
            patch(
                "mcp_score.tools.connection.get_musescore_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=None,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await connect_to_musescore())

        # Assert
        assert result["success"] is True
        assert "Connected" in result["message"]

    @pytest.mark.anyio()
    async def test_connect_failure(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_musescore

        mock_bridge = AsyncMock()
        mock_bridge.connect = AsyncMock(return_value=False)
        mock_bridge.is_connected = False

        with (
            patch(
                "mcp_score.tools.connection.get_musescore_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=None,
            ),
        ):
            # Act
            result = json.loads(await connect_to_musescore())

        # Assert
        assert "error" in result
        assert "Could not connect" in result["error"]


class TestDisconnectFromMusescore:
    @pytest.mark.anyio()
    async def test_disconnect(self) -> None:
        # Arrange
        from mcp_score.tools.connection import disconnect_from_musescore

        mock_bridge = AsyncMock()

        with (
            patch(
                "mcp_score.tools.connection.get_musescore_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=mock_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await disconnect_from_musescore())

        # Assert
        assert result["success"] is True
        mock_bridge.disconnect.assert_called_once()


class TestGetLiveScoreInfo:
    @pytest.mark.anyio()
    async def test_requires_connection(self) -> None:
        # Arrange
        from mcp_score.tools.connection import get_live_score_info

        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            # Act
            result = json.loads(await get_live_score_info())

        # Assert
        assert "error" in result
        assert NOT_CONNECTED in result["error"]

    @pytest.mark.anyio()
    async def test_returns_score_info(self) -> None:
        # Arrange
        from mcp_score.tools.connection import get_live_score_info

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.get_score = AsyncMock(
            return_value={"title": "Test Score", "measures": 32}
        )

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await get_live_score_info())

        # Assert
        assert result["title"] == "Test Score"


class TestPingMusescore:
    @pytest.mark.anyio()
    async def test_requires_connection(self) -> None:
        # Arrange
        from mcp_score.tools.connection import ping_score_app

        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            # Act
            result = json.loads(await ping_score_app())

        # Assert
        assert "error" in result

    @pytest.mark.anyio()
    async def test_returns_success_when_responsive(self) -> None:
        # Arrange
        from mcp_score.tools.connection import ping_score_app

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.ping = AsyncMock(return_value=True)
        mock_bridge.application_name = "MuseScore"

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await ping_score_app())

        # Assert
        assert result["success"] is True

    @pytest.mark.anyio()
    async def test_returns_error_when_unresponsive(self) -> None:
        # Arrange
        from mcp_score.tools.connection import ping_score_app

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.ping = AsyncMock(return_value=False)
        mock_bridge.application_name = "MuseScore"

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await ping_score_app())

        # Assert
        assert "error" in result


# ── Analysis tool tests ──────────────────────────────────────────────


class TestReadPassage:
    @pytest.mark.anyio()
    async def test_requires_connection(self) -> None:
        # Arrange
        from mcp_score.tools.analysis import read_passage

        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            # Act
            result = json.loads(await read_passage(1, 4))

        # Assert
        assert "error" in result

    @pytest.mark.anyio()
    async def test_rejects_invalid_start_measure(self) -> None:
        # Arrange
        from mcp_score.tools.analysis import read_passage

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await read_passage(0, 4))

        # Assert
        assert "must be >= 1" in result["error"]

    @pytest.mark.anyio()
    async def test_rejects_end_before_start(self) -> None:
        # Arrange
        from mcp_score.tools.analysis import read_passage

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await read_passage(5, 3))

        # Assert
        assert "end_measure" in result["error"]

    @pytest.mark.anyio()
    async def test_reads_range(self) -> None:
        # Arrange
        from mcp_score.tools.analysis import read_passage

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.get_cursor_info = AsyncMock(return_value={"beat": 1})

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await read_passage(1, 3))

        # Assert
        assert result["success"] is True
        assert len(result["elements"]) == 3
        assert mock_bridge.go_to_measure.call_count == 3


class TestReadPassageWithStaff:
    @pytest.mark.anyio()
    async def test_navigates_to_staff(self) -> None:
        # Arrange
        from mcp_score.tools.analysis import read_passage

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.get_cursor_info = AsyncMock(return_value={"beat": 1})

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            await read_passage(1, 2, staff=3)

        # Assert
        assert mock_bridge.go_to_staff.call_count == 2
        mock_bridge.go_to_staff.assert_called_with(3)

    @pytest.mark.anyio()
    async def test_omits_staff_navigation_when_none(self) -> None:
        # Arrange
        from mcp_score.tools.analysis import read_passage

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.get_cursor_info = AsyncMock(return_value={"beat": 1})

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            await read_passage(1, 2, staff=None)

        # Assert
        mock_bridge.go_to_staff.assert_not_called()


class TestGetMeasureContent:
    @pytest.mark.anyio()
    async def test_requires_connection(self) -> None:
        # Arrange
        from mcp_score.tools.analysis import get_measure_content

        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            # Act
            result = json.loads(await get_measure_content(1))

        # Assert
        assert "error" in result

    @pytest.mark.anyio()
    async def test_rejects_invalid_measure(self) -> None:
        # Arrange
        from mcp_score.tools.analysis import get_measure_content

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await get_measure_content(0))

        # Assert
        assert "must be >= 1" in result["error"]

    @pytest.mark.anyio()
    async def test_navigates_and_selects(self) -> None:
        # Arrange
        from mcp_score.tools.analysis import get_measure_content

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.send_command = AsyncMock(return_value={"notes": ["C4"]})

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await get_measure_content(3, staff=1))

        # Assert
        mock_bridge.go_to_measure.assert_called_once_with(3)
        mock_bridge.go_to_staff.assert_called_once_with(1)
        mock_bridge.send_command.assert_called_once_with("selectCurrentMeasure")
        assert result["notes"] == ["C4"]


class TestTransposePassageErrorBranch:
    @pytest.mark.anyio()
    async def test_returns_error_when_select_range_fails(self) -> None:
        # Arrange
        from mcp_score.tools.manipulation import transpose_passage

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.send_command = AsyncMock(return_value={"error": "Invalid range"})

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await transpose_passage(1, 4, 0, 5))

        # Assert — should return the error from selectCustomRange, not call transpose
        assert result["error"] == "Invalid range"
        assert mock_bridge.send_command.call_count == 1


# ── Manipulation tool tests ──────────────────────────────────────────


class TestManipulationToolsRequireConnection:
    """All manipulation tools must return an error when not connected."""

    @pytest.mark.anyio()
    async def test_add_live_rehearsal_mark(self) -> None:
        from mcp_score.tools.manipulation import add_live_rehearsal_mark

        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            result = json.loads(await add_live_rehearsal_mark(1, "A"))

        assert "error" in result

    @pytest.mark.anyio()
    async def test_add_live_chord_symbol(self) -> None:
        from mcp_score.tools.manipulation import add_live_chord_symbol

        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            result = json.loads(await add_live_chord_symbol(1, "Cmaj7"))

        assert "error" in result

    @pytest.mark.anyio()
    async def test_set_live_barline(self) -> None:
        from mcp_score.tools.manipulation import set_live_barline

        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            result = json.loads(await set_live_barline(1, "double"))

        assert "error" in result

    @pytest.mark.anyio()
    async def test_set_live_tempo(self) -> None:
        from mcp_score.tools.manipulation import set_live_tempo

        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            result = json.loads(await set_live_tempo(1, 120))

        assert "error" in result

    @pytest.mark.anyio()
    async def test_transpose_passage(self) -> None:
        from mcp_score.tools.manipulation import transpose_passage

        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            result = json.loads(await transpose_passage(1, 4, 0, 2))

        assert "error" in result

    @pytest.mark.anyio()
    async def test_undo_last_action(self) -> None:
        from mcp_score.tools.manipulation import undo_last_action

        with patch("mcp_score.tools.get_active_bridge", return_value=None):
            result = json.loads(await undo_last_action())

        assert "error" in result


class TestManipulationMeasureValidation:
    """Manipulation tools must reject invalid measure numbers."""

    @pytest.mark.anyio()
    async def test_rehearsal_mark_rejects_zero(self) -> None:
        from mcp_score.tools.manipulation import add_live_rehearsal_mark

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            result = json.loads(await add_live_rehearsal_mark(0, "A"))

        assert "must be >= 1" in result["error"]

    @pytest.mark.anyio()
    async def test_chord_symbol_rejects_negative(self) -> None:
        from mcp_score.tools.manipulation import add_live_chord_symbol

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            result = json.loads(await add_live_chord_symbol(-1, "Cmaj7"))

        assert "must be >= 1" in result["error"]

    @pytest.mark.anyio()
    async def test_transpose_rejects_end_before_start(self) -> None:
        from mcp_score.tools.manipulation import transpose_passage

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            result = json.loads(await transpose_passage(5, 3, 0, 2))

        assert "end_measure" in result["error"]


class TestManipulationHappyPaths:
    """Verify manipulation tools delegate correctly to the bridge."""

    @pytest.mark.anyio()
    async def test_add_rehearsal_mark_navigates_and_adds(self) -> None:
        # Arrange
        from mcp_score.tools.manipulation import add_live_rehearsal_mark

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.add_rehearsal_mark = AsyncMock(return_value={"result": "ok"})

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await add_live_rehearsal_mark(5, "B"))

        # Assert
        mock_bridge.go_to_measure.assert_called_once_with(5)
        mock_bridge.add_rehearsal_mark.assert_called_once_with("B")
        assert result["result"] == "ok"

    @pytest.mark.anyio()
    async def test_set_tempo_with_text(self) -> None:
        # Arrange
        from mcp_score.tools.manipulation import set_live_tempo

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.set_tempo = AsyncMock(return_value={"result": "ok"})

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await set_live_tempo(1, 66, "Slow Blues"))

        # Assert
        mock_bridge.set_tempo.assert_called_once_with(66, "Slow Blues")
        assert result["result"] == "ok"

    @pytest.mark.anyio()
    async def test_transpose_passage_selects_range_and_transposes(
        self,
    ) -> None:
        # Arrange
        from mcp_score.tools.manipulation import transpose_passage

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.send_command = AsyncMock(return_value={"result": "ok"})

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            await transpose_passage(1, 8, 0, 5)

        # Assert — two send_command calls: selectCustomRange + transpose
        assert mock_bridge.send_command.call_count == 2
        select_call = mock_bridge.send_command.call_args_list[0]
        assert select_call.args[0] == "selectCustomRange"
        assert select_call.args[1]["startStaff"] == 0
        assert select_call.args[1]["endStaff"] == 0
        transpose_call = mock_bridge.send_command.call_args_list[1]
        assert transpose_call.args[0] == "transpose"
        assert transpose_call.args[1]["semitones"] == 5

    @pytest.mark.anyio()
    async def test_undo_delegates_to_bridge(self) -> None:
        # Arrange
        from mcp_score.tools.manipulation import undo_last_action

        mock_bridge = AsyncMock()
        mock_bridge.is_connected = True
        mock_bridge.undo = AsyncMock(return_value={"result": "ok"})

        with patch("mcp_score.tools.get_active_bridge", return_value=mock_bridge):
            # Act
            result = json.loads(await undo_last_action())

        # Assert
        mock_bridge.undo.assert_called_once()
        assert result["result"] == "ok"
