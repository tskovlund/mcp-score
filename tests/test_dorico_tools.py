"""Tests for Dorico connection tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestConnectToDorico:
    @pytest.mark.anyio()
    async def test_connect_success(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_dorico

        mock_bridge = AsyncMock()
        mock_bridge.connect = AsyncMock(return_value=True)
        mock_bridge.is_connected = False

        with (
            patch(
                "mcp_score.tools.connection.get_dorico_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=None,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await connect_to_dorico())

        # Assert
        assert result["success"] is True
        assert "Connected to Dorico" in result["message"]

    @pytest.mark.anyio()
    async def test_connect_failure(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_dorico

        mock_bridge = AsyncMock()
        mock_bridge.connect = AsyncMock(return_value=False)
        mock_bridge.is_connected = False

        with (
            patch(
                "mcp_score.tools.connection.get_dorico_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=None,
            ),
        ):
            # Act
            result = json.loads(await connect_to_dorico())

        # Assert
        assert "error" in result
        assert "Could not connect to Dorico" in result["error"]

    @pytest.mark.anyio()
    async def test_connect_with_custom_port(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_dorico

        mock_bridge = AsyncMock()
        mock_bridge.connect = AsyncMock(return_value=True)
        mock_bridge.is_connected = False

        with (
            patch(
                "mcp_score.tools.connection.get_dorico_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=None,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await connect_to_dorico(port=5555))

        # Assert
        assert result["success"] is True
        assert "5555" in result["message"]
        assert mock_bridge.port == 5555

    @pytest.mark.anyio()
    async def test_connect_disconnects_existing_bridge(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_dorico

        existing_bridge = AsyncMock()
        existing_bridge.is_connected = True

        new_bridge = AsyncMock()
        new_bridge.connect = AsyncMock(return_value=True)
        new_bridge.is_connected = False

        with (
            patch(
                "mcp_score.tools.connection.get_dorico_bridge",
                return_value=new_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=existing_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge") as mock_set,
        ):
            # Act
            await connect_to_dorico()

        # Assert
        existing_bridge.disconnect.assert_called_once()
        # set_active_bridge(None) then set_active_bridge(new_bridge)
        assert mock_set.call_count == 2


class TestDisconnectFromDorico:
    @pytest.mark.anyio()
    async def test_disconnect(self) -> None:
        # Arrange
        from mcp_score.tools.connection import disconnect_from_dorico

        mock_bridge = AsyncMock()

        with (
            patch(
                "mcp_score.tools.connection.get_dorico_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=mock_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await disconnect_from_dorico())

        # Assert
        assert result["success"] is True
        assert "Disconnected from Dorico" in result["message"]
        mock_bridge.disconnect.assert_called_once()

    @pytest.mark.anyio()
    async def test_disconnect_does_not_clear_other_bridge(self) -> None:
        # Arrange — active bridge is MuseScore, not Dorico
        from mcp_score.tools.connection import disconnect_from_dorico

        dorico_bridge = AsyncMock()
        other_bridge = AsyncMock()

        with (
            patch(
                "mcp_score.tools.connection.get_dorico_bridge",
                return_value=dorico_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=other_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge") as mock_set,
        ):
            # Act
            await disconnect_from_dorico()

        # Assert — should NOT clear active bridge since it's not the Dorico one
        mock_set.assert_not_called()


class TestBridgeSwitching:
    """Verify that connecting to one DAW disconnects the other."""

    @pytest.mark.anyio()
    async def test_connecting_musescore_disconnects_dorico(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_musescore

        dorico_bridge = AsyncMock()
        dorico_bridge.is_connected = True

        musescore_bridge = AsyncMock()
        musescore_bridge.connect = AsyncMock(return_value=True)

        with (
            patch(
                "mcp_score.tools.connection.get_musescore_bridge",
                return_value=musescore_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=dorico_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await connect_to_musescore())

        # Assert
        dorico_bridge.disconnect.assert_called_once()
        assert result["success"] is True

    @pytest.mark.anyio()
    async def test_connecting_dorico_disconnects_musescore(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_dorico

        musescore_bridge = AsyncMock()
        musescore_bridge.is_connected = True

        dorico_bridge = AsyncMock()
        dorico_bridge.connect = AsyncMock(return_value=True)

        with (
            patch(
                "mcp_score.tools.connection.get_dorico_bridge",
                return_value=dorico_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=musescore_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await connect_to_dorico())

        # Assert
        musescore_bridge.disconnect.assert_called_once()
        assert result["success"] is True
