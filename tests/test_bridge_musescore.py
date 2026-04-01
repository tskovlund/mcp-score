"""Tests for the MuseScore WebSocket server bridge."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets.exceptions

from mcp_score.bridge.musescore import DEFAULT_PORT, MuseScoreBridge


class TestMuseScoreBridgeInitialState:
    def test_new_bridge_is_not_connected(self) -> None:
        bridge = MuseScoreBridge()

        assert bridge.is_connected is False

    def test_new_bridge_has_no_server(self) -> None:
        bridge = MuseScoreBridge()

        assert bridge._server is None
        assert bridge._connection is None


class TestMuseScoreBridgeConnect:
    @pytest.mark.anyio()
    async def test_connect_returns_false_on_timeout(self) -> None:
        """connect() returns False when no plugin connects within the timeout."""
        bridge = MuseScoreBridge(host="localhost", port=DEFAULT_PORT)
        mock_server = MagicMock()
        mock_server.close = MagicMock()
        mock_server.wait_closed = AsyncMock()

        with (
            patch(
                "websockets.asyncio.server.serve", new_callable=AsyncMock
            ) as mock_serve,
            patch("mcp_score.bridge.musescore._CONNECT_TIMEOUT", 0.01),
        ):
            mock_serve.return_value = mock_server
            result = await bridge.connect()

        assert result is False
        assert bridge._server is None
        assert bridge._connection is None

    @pytest.mark.anyio()
    async def test_connect_returns_true_when_plugin_connects(self) -> None:
        """connect() returns True and stores _connection when the plugin dials in."""
        bridge = MuseScoreBridge(host="localhost", port=DEFAULT_PORT)

        connection_closed = asyncio.Event()

        async def wait_until_closed() -> None:
            await connection_closed.wait()

        mock_connection = MagicMock()
        mock_connection.remote_address = ("127.0.0.1", 54321)
        mock_connection.wait_closed = wait_until_closed
        mock_connection.close = AsyncMock()

        mock_server = MagicMock()
        mock_server.close = MagicMock()
        mock_server.wait_closed = AsyncMock()

        async def fake_serve(handler: object, host: str, port: int) -> object:
            asyncio.ensure_future(handler(mock_connection))  # type: ignore[operator]
            return mock_server

        with patch("websockets.asyncio.server.serve", side_effect=fake_serve):
            result = await bridge.connect()

        assert result is True
        assert bridge._connection is mock_connection
        assert bridge._server is mock_server

        # Clean up background coroutine
        connection_closed.set()
        await asyncio.sleep(0)

    @pytest.mark.anyio()
    async def test_connect_returns_false_when_server_fails_to_start(self) -> None:
        """connect() returns False if the port is unavailable."""
        bridge = MuseScoreBridge(host="localhost", port=DEFAULT_PORT)

        with patch(
            "websockets.asyncio.server.serve",
            side_effect=OSError("Address already in use"),
        ):
            result = await bridge.connect()

        assert result is False
        assert bridge._server is None


class TestMuseScoreBridgeDisconnect:
    @pytest.mark.anyio()
    async def test_disconnect_closes_connection_and_stops_server(self) -> None:
        """disconnect() closes the active connection and stops the server."""
        bridge = MuseScoreBridge()

        mock_connection = MagicMock()
        mock_connection.close = AsyncMock()
        bridge._connection = mock_connection  # type: ignore[assignment]

        mock_server = MagicMock()
        mock_server.close = MagicMock()
        mock_server.wait_closed = AsyncMock()
        bridge._server = mock_server  # type: ignore[assignment]

        await bridge.disconnect()

        mock_connection.close.assert_called_once()
        mock_server.close.assert_called_once()
        assert bridge._connection is None
        assert bridge._server is None

    @pytest.mark.anyio()
    async def test_disconnect_when_not_connected_is_safe(self) -> None:
        """disconnect() with no server/connection does not raise."""
        bridge = MuseScoreBridge()
        await bridge.disconnect()  # should not raise


class TestMuseScoreBridgeSendCommand:
    @pytest.mark.anyio()
    async def test_send_command_with_active_connection(self) -> None:
        """send_command() sends JSON and parses the JSON response."""
        bridge = MuseScoreBridge()
        mock_connection = AsyncMock()
        mock_connection.send = AsyncMock()
        mock_connection.recv = AsyncMock(return_value='{"result": "pong"}')
        bridge._connection = mock_connection  # type: ignore[assignment]

        result = await bridge.send_command("ping")

        assert result == {"result": "pong"}
        mock_connection.send.assert_called_once()

    @pytest.mark.anyio()
    async def test_send_command_without_connection_returns_error(self) -> None:
        """send_command() returns an error when the server times out with no plugin."""
        bridge = MuseScoreBridge(host="localhost", port=DEFAULT_PORT)
        mock_server = MagicMock()
        mock_server.close = MagicMock()
        mock_server.wait_closed = AsyncMock()

        with (
            patch(
                "websockets.asyncio.server.serve", new_callable=AsyncMock
            ) as mock_serve,
            patch("mcp_score.bridge.musescore._CONNECT_TIMEOUT", 0.01),
        ):
            mock_serve.return_value = mock_server
            result = await bridge.send_command("ping")

        assert "error" in result
        assert "Cannot connect" in result["error"]

    @pytest.mark.anyio()
    async def test_send_command_reconnects_on_connection_closed(self) -> None:
        """send_command() returns an error when connection drops and retry times out."""
        bridge = MuseScoreBridge()
        mock_connection = AsyncMock()
        mock_connection.send = AsyncMock()
        mock_connection.recv = AsyncMock(
            side_effect=websockets.exceptions.ConnectionClosed(None, None)
        )
        mock_connection.close = AsyncMock()
        bridge._connection = mock_connection  # type: ignore[assignment]

        mock_server = MagicMock()
        mock_server.close = MagicMock()
        mock_server.wait_closed = AsyncMock()

        with (
            patch(
                "websockets.asyncio.server.serve", new_callable=AsyncMock
            ) as mock_serve,
            patch("mcp_score.bridge.musescore._CONNECT_TIMEOUT", 0.01),
        ):
            mock_serve.return_value = mock_server
            result = await bridge.send_command("ping")

        assert "error" in result
        assert bridge._connection is None

    @pytest.mark.anyio()
    async def test_non_text_response_returns_error(self) -> None:
        """Binary WebSocket response should produce an error."""
        bridge = MuseScoreBridge()
        mock_connection = AsyncMock()
        mock_connection.send = AsyncMock()
        mock_connection.recv = AsyncMock(return_value=b"binary data")
        bridge._connection = mock_connection  # type: ignore[assignment]

        result = await bridge._send_raw('{"command": "ping"}')

        assert "error" in result
        assert "non-text" in result["error"]
