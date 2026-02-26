"""Tests for Sibelius connection tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestConnectToSibelius:
    @pytest.mark.anyio()
    async def test_connect_returns_success(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_sibelius

        mock_bridge = AsyncMock()
        mock_bridge.connect = AsyncMock(return_value=True)
        mock_bridge.is_connected = False

        with (
            patch(
                "mcp_score.tools.connection.get_sibelius_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=None,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await connect_to_sibelius())

        # Assert
        assert result["success"] is True
        assert "Connected to Sibelius" in result["message"]

    @pytest.mark.anyio()
    async def test_connect_failure_returns_error(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_sibelius

        mock_bridge = AsyncMock()
        mock_bridge.connect = AsyncMock(return_value=False)
        mock_bridge.is_connected = False

        with (
            patch(
                "mcp_score.tools.connection.get_sibelius_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=None,
            ),
        ):
            # Act
            result = json.loads(await connect_to_sibelius())

        # Assert
        assert "error" in result
        assert "Could not connect to Sibelius" in result["error"]

    @pytest.mark.anyio()
    async def test_connect_with_custom_port_sets_port(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_sibelius

        mock_bridge = AsyncMock()
        mock_bridge.connect = AsyncMock(return_value=True)
        mock_bridge.is_connected = False

        with (
            patch(
                "mcp_score.tools.connection.get_sibelius_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=None,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await connect_to_sibelius(port=5555))

        # Assert
        assert result["success"] is True
        assert "5555" in result["message"]
        assert mock_bridge.port == 5555

    @pytest.mark.anyio()
    async def test_connect_disconnects_existing_bridge_first(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_sibelius

        existing_bridge = AsyncMock()
        existing_bridge.is_connected = True

        new_bridge = AsyncMock()
        new_bridge.connect = AsyncMock(return_value=True)
        new_bridge.is_connected = False

        with (
            patch(
                "mcp_score.tools.connection.get_sibelius_bridge",
                return_value=new_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=existing_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge") as mock_set,
        ):
            # Act
            await connect_to_sibelius()

        # Assert
        existing_bridge.disconnect.assert_called_once()
        # set_active_bridge(None) then set_active_bridge(new_bridge)
        assert mock_set.call_count == 2


class TestDisconnectFromSibelius:
    @pytest.mark.anyio()
    async def test_disconnect_returns_success(self) -> None:
        # Arrange
        from mcp_score.tools.connection import disconnect_from_sibelius

        mock_bridge = AsyncMock()

        with (
            patch(
                "mcp_score.tools.connection.get_sibelius_bridge",
                return_value=mock_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=mock_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await disconnect_from_sibelius())

        # Assert
        assert result["success"] is True
        assert "Disconnected from Sibelius" in result["message"]
        mock_bridge.disconnect.assert_called_once()

    @pytest.mark.anyio()
    async def test_disconnect_preserves_other_active_bridge(self) -> None:
        # Arrange -- active bridge is MuseScore, not Sibelius
        from mcp_score.tools.connection import disconnect_from_sibelius

        sibelius_bridge = AsyncMock()
        other_bridge = AsyncMock()

        with (
            patch(
                "mcp_score.tools.connection.get_sibelius_bridge",
                return_value=sibelius_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=other_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge") as mock_set,
        ):
            # Act
            await disconnect_from_sibelius()

        # Assert -- should NOT clear active bridge since it's not Sibelius
        mock_set.assert_not_called()


class TestBridgeSwitchingWithSibelius:
    """Verify that connecting to Sibelius disconnects other bridges."""

    @pytest.mark.anyio()
    async def test_connect_sibelius_disconnects_musescore(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_sibelius

        musescore_bridge = AsyncMock()
        musescore_bridge.is_connected = True

        sibelius_bridge = AsyncMock()
        sibelius_bridge.connect = AsyncMock(return_value=True)

        with (
            patch(
                "mcp_score.tools.connection.get_sibelius_bridge",
                return_value=sibelius_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=musescore_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await connect_to_sibelius())

        # Assert
        musescore_bridge.disconnect.assert_called_once()
        assert result["success"] is True

    @pytest.mark.anyio()
    async def test_connect_musescore_disconnects_sibelius(self) -> None:
        # Arrange
        from mcp_score.tools.connection import connect_to_musescore

        sibelius_bridge = AsyncMock()
        sibelius_bridge.is_connected = True

        musescore_bridge = AsyncMock()
        musescore_bridge.connect = AsyncMock(return_value=True)

        with (
            patch(
                "mcp_score.tools.connection.get_musescore_bridge",
                return_value=musescore_bridge,
            ),
            patch(
                "mcp_score.tools.connection.get_active_bridge",
                return_value=sibelius_bridge,
            ),
            patch("mcp_score.tools.connection.set_active_bridge"),
        ):
            # Act
            result = json.loads(await connect_to_musescore())

        # Assert
        sibelius_bridge.disconnect.assert_called_once()
        assert result["success"] is True
