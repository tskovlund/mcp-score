"""Tests for the WebSocket plumbing every bridge is built on.

``WebSocketTransport`` is tested against a mock connection;
``WebSocketBridge`` through ``MuseScoreBridge`` (the simplest concrete
bridge) with hooks that record when they run.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from websockets.exceptions import ConnectionClosed
from websockets.protocol import State

from mcp_score.bridge.musescore import MuseScoreBridge
from mcp_score.bridge.websocket import (
    TransportError,
    WebSocketTransport,
)
from tests.fakes import WEBSOCKETS_CONNECT, fake_connection, sent_payloads

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

URI = "ws://localhost:8765"
RECEIVE_TIMEOUT = 5.0
PAYLOAD: dict[str, Any] = {"command": "ping"}
PONG: dict[str, Any] = {"result": "pong"}


async def _never_replies() -> str:
    """A ``recv`` that hangs until the caller's timeout fires."""
    await asyncio.sleep(60)
    return "{}"


class _HookRecordingBridge(MuseScoreBridge):
    """Records the transports handed to the connection hooks."""

    def __init__(self) -> None:
        super().__init__()
        self.connected_with: list[WebSocketTransport] = []
        self.disconnecting_with: list[WebSocketTransport] = []
        self.connect_hook_error: TransportError | None = None

    async def _on_connected(self, transport: WebSocketTransport) -> None:
        self.connected_with.append(transport)
        if self.connect_hook_error is not None:
            raise self.connect_hook_error

    async def _on_disconnecting(self, transport: WebSocketTransport) -> None:
        self.disconnecting_with.append(transport)


@pytest.fixture
async def open_transport() -> AsyncIterator[tuple[WebSocketTransport, AsyncMock]]:
    """A transport opened on a mock connection that answers with PONG."""
    connection = fake_connection(PONG)
    transport = WebSocketTransport(URI, RECEIVE_TIMEOUT)
    with patch(WEBSOCKETS_CONNECT, AsyncMock(return_value=connection)):
        await transport.open()
    yield transport, connection


# ── Transport ────────────────────────────────────────────────────────


class TestWebSocketTransport:
    @pytest.mark.anyio()
    async def test_open_without_server_raises_transport_error(self) -> None:
        # Arrange
        transport = WebSocketTransport(URI, RECEIVE_TIMEOUT)

        with (
            patch(WEBSOCKETS_CONNECT, AsyncMock(side_effect=OSError("refused"))),
            pytest.raises(TransportError, match=f"cannot connect to {URI}"),
        ):
            # Act / Assert
            await transport.open()

        assert transport.is_open is False

    @pytest.mark.anyio()
    async def test_request_sends_json_and_returns_decoded_reply(
        self, open_transport: tuple[WebSocketTransport, AsyncMock]
    ) -> None:
        # Arrange
        transport, connection = open_transport

        # Act
        reply = await transport.request(PAYLOAD)

        # Assert
        assert reply == PONG
        assert sent_payloads(connection) == [PAYLOAD]

    @pytest.mark.anyio()
    async def test_request_with_binary_reply_raises_transport_error(self) -> None:
        # Arrange
        transport = WebSocketTransport(URI, RECEIVE_TIMEOUT)
        with patch(
            WEBSOCKETS_CONNECT, AsyncMock(return_value=fake_connection(b"\x00\x01"))
        ):
            await transport.open()

        # Act / Assert
        with pytest.raises(TransportError, match="binary message"):
            await transport.request(PAYLOAD)

    @pytest.mark.anyio()
    async def test_request_with_invalid_json_raises_transport_error(self) -> None:
        # Arrange
        transport = WebSocketTransport(URI, RECEIVE_TIMEOUT)
        with patch(
            WEBSOCKETS_CONNECT, AsyncMock(return_value=fake_connection("{not json"))
        ):
            await transport.open()

        # Act / Assert
        with pytest.raises(TransportError, match="invalid JSON"):
            await transport.request(PAYLOAD)

    @pytest.mark.anyio()
    async def test_request_when_reply_never_comes_raises_after_timeout(
        self,
    ) -> None:
        # Arrange
        connection = fake_connection()
        connection.recv = AsyncMock(side_effect=_never_replies)
        transport = WebSocketTransport(URI, receive_timeout=0.01)
        with patch(WEBSOCKETS_CONNECT, AsyncMock(return_value=connection)):
            await transport.open()

        # Act / Assert
        with pytest.raises(TransportError, match="exchange failed"):
            await transport.request(PAYLOAD)

    @pytest.mark.anyio()
    async def test_request_when_not_open_raises_transport_error(self) -> None:
        # Arrange
        transport = WebSocketTransport(URI, RECEIVE_TIMEOUT)

        # Act / Assert
        with pytest.raises(TransportError, match="not open"):
            await transport.request(PAYLOAD)

    @pytest.mark.anyio()
    async def test_is_open_reflects_connection_state(self) -> None:
        # Arrange
        transport = WebSocketTransport(URI, RECEIVE_TIMEOUT)
        connection = fake_connection(state=State.CLOSED)
        with patch(WEBSOCKETS_CONNECT, AsyncMock(return_value=connection)):
            await transport.open()

        # Act / Assert
        assert transport.is_open is False
        connection.state = State.OPEN
        assert transport.is_open is True

    @pytest.mark.anyio()
    async def test_close_closes_connection_and_forgets_it(
        self, open_transport: tuple[WebSocketTransport, AsyncMock]
    ) -> None:
        # Arrange
        transport, connection = open_transport

        # Act
        await transport.close()

        # Assert
        connection.close.assert_awaited_once()
        assert transport.is_open is False


# ── Bridge ───────────────────────────────────────────────────────────


class TestWebSocketBridgeConnection:
    @pytest.mark.anyio()
    async def test_connect_opens_transport_and_runs_hook(self) -> None:
        # Arrange
        bridge = _HookRecordingBridge()

        with patch(WEBSOCKETS_CONNECT, AsyncMock(return_value=fake_connection())):
            # Act
            connected = await bridge.connect()

        # Assert
        assert connected is True
        assert bridge.is_connected is True
        assert len(bridge.connected_with) == 1
        assert bridge.connected_with[0].uri == bridge.uri

    @pytest.mark.anyio()
    async def test_connect_without_server_returns_false(self) -> None:
        # Arrange
        bridge = _HookRecordingBridge()

        with patch(WEBSOCKETS_CONNECT, AsyncMock(side_effect=OSError("refused"))):
            # Act
            connected = await bridge.connect()

        # Assert
        assert connected is False
        assert bridge.is_connected is False
        assert bridge.connected_with == []

    @pytest.mark.anyio()
    async def test_connect_with_failing_hook_closes_connection(self) -> None:
        # Arrange
        bridge = _HookRecordingBridge()
        bridge.connect_hook_error = TransportError("handshake refused")
        connection = fake_connection()

        with patch(WEBSOCKETS_CONNECT, AsyncMock(return_value=connection)):
            # Act
            connected = await bridge.connect()

        # Assert
        assert connected is False
        assert bridge.is_connected is False
        connection.close.assert_awaited_once()

    @pytest.mark.anyio()
    async def test_disconnect_runs_hook_then_closes(self) -> None:
        # Arrange
        bridge = _HookRecordingBridge()
        connection = fake_connection()
        with patch(WEBSOCKETS_CONNECT, AsyncMock(return_value=connection)):
            await bridge.connect()

        # Act
        await bridge.disconnect()

        # Assert
        assert bridge.disconnecting_with == bridge.connected_with
        connection.close.assert_awaited_once()
        assert bridge.is_connected is False

    @pytest.mark.anyio()
    async def test_disconnect_when_not_connected_skips_hook(self) -> None:
        # Arrange
        bridge = _HookRecordingBridge()

        # Act
        await bridge.disconnect()

        # Assert
        assert bridge.disconnecting_with == []


class TestWebSocketBridgeExchange:
    @pytest.mark.anyio()
    async def test_exchange_connects_first_when_not_connected(self) -> None:
        # Arrange
        bridge = _HookRecordingBridge()
        connect = AsyncMock(return_value=fake_connection(PONG))

        with patch(WEBSOCKETS_CONNECT, connect):
            # Act
            reply = await bridge.send_command("ping")

        # Assert
        assert reply == PONG
        connect.assert_awaited_once_with(bridge.uri)
        assert len(bridge.connected_with) == 1

    @pytest.mark.anyio()
    async def test_exchange_without_server_returns_error_result(self) -> None:
        # Arrange
        bridge = _HookRecordingBridge()

        with patch(WEBSOCKETS_CONNECT, AsyncMock(side_effect=OSError("refused"))):
            # Act
            reply = await bridge.send_command("ping")

        # Assert
        assert reply == {"error": f"Cannot connect to MuseScore at {bridge.uri}"}

    @pytest.mark.anyio()
    async def test_exchange_reconnects_once_and_retries_when_connection_drops(
        self,
    ) -> None:
        # Arrange
        bridge = _HookRecordingBridge()
        dropped = fake_connection(ConnectionClosed(None, None))
        replacement = fake_connection(PONG)
        connect = AsyncMock(side_effect=[dropped, replacement])

        with patch(WEBSOCKETS_CONNECT, connect):
            # Act
            reply = await bridge.send_command("ping")

        # Assert
        assert reply == PONG
        assert connect.await_count == 2
        dropped.close.assert_awaited_once()
        assert sent_payloads(replacement) == [{"command": "ping"}]
        assert len(bridge.connected_with) == 2

    @pytest.mark.anyio()
    async def test_exchange_with_failed_reconnect_returns_error_result(self) -> None:
        # Arrange
        bridge = _HookRecordingBridge()
        dropped = fake_connection(ConnectionClosed(None, None))
        connect = AsyncMock(side_effect=[dropped, OSError("gone")])

        with patch(WEBSOCKETS_CONNECT, connect):
            # Act
            reply = await bridge.send_command("ping")

        # Assert
        assert reply == {
            "error": "Lost connection to MuseScore and could not reconnect"
        }
        assert bridge.is_connected is False

    @pytest.mark.anyio()
    async def test_exchange_with_failed_retry_returns_error_result(self) -> None:
        # Arrange
        bridge = _HookRecordingBridge()
        dropped = fake_connection(ConnectionClosed(None, None))
        dropped_again = fake_connection(ConnectionClosed(None, None))
        connect = AsyncMock(side_effect=[dropped, dropped_again])

        with patch(WEBSOCKETS_CONNECT, connect):
            # Act
            reply = await bridge.send_command("ping")

        # Assert
        assert "MuseScore request failed" in reply["error"]
        assert connect.await_count == 2
