"""Tests for the Dorico WebSocket bridge client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from mcp_score.bridge.dorico import (
    DEFAULT_CLIENT_NAME,
    HANDSHAKE_VERSION,
    DoricoBridge,
    HandshakeError,
)

# ── Init and properties ──────────────────────────────────────────────


class TestDoricoBridgeInit:
    def test_default_host_and_port(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge()

        # Assert
        assert bridge.host == "localhost"
        assert bridge.port == 4560

    def test_custom_host_and_port(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge(host="192.168.1.10", port=9999)

        # Assert
        assert bridge.host == "192.168.1.10"
        assert bridge.port == 9999

    def test_custom_client_name(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge(client_name="my-app")

        # Assert
        assert bridge.client_name == "my-app"

    def test_default_client_name(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge()

        # Assert
        assert bridge.client_name == DEFAULT_CLIENT_NAME


class TestDoricoBridgeUri:
    def test_uri_default(self) -> None:
        # Arrange
        bridge = DoricoBridge()

        # Act / Assert
        assert bridge.uri == "ws://localhost:4560"

    def test_uri_custom(self) -> None:
        # Arrange
        bridge = DoricoBridge(host="example.com", port=1234)

        # Act / Assert
        assert bridge.uri == "ws://example.com:1234"


class TestDoricoBridgeApplicationName:
    def test_application_name(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge()

        # Assert
        assert bridge.application_name == "Dorico"


class TestDoricoBridgeConnection:
    def test_is_connected_initially_false(self) -> None:
        # Arrange
        bridge = DoricoBridge()

        # Act / Assert
        assert bridge.is_connected is False

    @pytest.mark.anyio()
    async def test_connect_fails_gracefully_when_no_server(self) -> None:
        # Arrange
        bridge = DoricoBridge(host="localhost", port=19999)

        # Act
        connected = await bridge.connect()

        # Assert
        assert connected is False
        assert bridge.is_connected is False


# ── Handshake protocol ───────────────────────────────────────────────


class TestDoricoBridgeHandshake:
    @pytest.mark.anyio()
    async def test_handshake_without_session_token(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        mock_connection = AsyncMock()

        # Simulate: connect message -> sessiontoken response,
        #           acceptsessiontoken -> response with kConnected
        session_token_response = json.dumps(
            {"message": "sessiontoken", "sessionToken": "abc-123"}
        )
        accept_response = json.dumps({"message": "response", "code": "kConnected"})
        mock_connection.recv = AsyncMock(
            side_effect=[session_token_response, accept_response]
        )
        mock_connection.send = AsyncMock()

        with patch(
            "mcp_score.bridge.dorico.websockets.connect",
            new_callable=AsyncMock,
            return_value=mock_connection,
        ):
            # Act
            connected = await bridge.connect()

        # Assert
        assert connected is True
        assert bridge._session_token == "abc-123"
        assert mock_connection.send.call_count == 2

        # Verify connect message format
        first_call = mock_connection.send.call_args_list[0]
        connect_msg = json.loads(first_call.args[0])
        assert connect_msg["message"] == "connect"
        assert connect_msg["clientName"] == DEFAULT_CLIENT_NAME
        assert connect_msg["handshakeVersion"] == HANDSHAKE_VERSION

        # Verify accept message format
        second_call = mock_connection.send.call_args_list[1]
        accept_msg = json.loads(second_call.args[0])
        assert accept_msg["message"] == "acceptsessiontoken"
        assert accept_msg["sessionToken"] == "abc-123"

    @pytest.mark.anyio()
    async def test_handshake_with_cached_session_token(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge._session_token = "cached-token"
        mock_connection = AsyncMock()

        # Dorico responds with kConnected when token is still valid
        connected_response = json.dumps({"message": "response", "code": "kConnected"})
        mock_connection.recv = AsyncMock(return_value=connected_response)
        mock_connection.send = AsyncMock()

        with patch(
            "mcp_score.bridge.dorico.websockets.connect",
            new_callable=AsyncMock,
            return_value=mock_connection,
        ):
            # Act
            connected = await bridge.connect()

        # Assert
        assert connected is True
        assert mock_connection.send.call_count == 1

        # Verify the connect message includes the session token
        connect_msg = json.loads(mock_connection.send.call_args_list[0].args[0])
        assert connect_msg["sessionToken"] == "cached-token"

    @pytest.mark.anyio()
    async def test_handshake_with_expired_session_token(self) -> None:
        # Arrange — token expired, Dorico sends a new session token
        bridge = DoricoBridge()
        bridge._session_token = "expired-token"
        mock_connection = AsyncMock()

        new_token_response = json.dumps(
            {"message": "sessiontoken", "sessionToken": "new-token-456"}
        )
        accept_response = json.dumps({"message": "response", "code": "kConnected"})
        mock_connection.recv = AsyncMock(
            side_effect=[new_token_response, accept_response]
        )
        mock_connection.send = AsyncMock()

        with patch(
            "mcp_score.bridge.dorico.websockets.connect",
            new_callable=AsyncMock,
            return_value=mock_connection,
        ):
            # Act
            connected = await bridge.connect()

        # Assert
        assert connected is True
        assert bridge._session_token == "new-token-456"

    @pytest.mark.anyio()
    async def test_handshake_failure_returns_false(self) -> None:
        # Arrange — Dorico rejects the connection
        bridge = DoricoBridge()
        mock_connection = AsyncMock()

        error_response = json.dumps(
            {
                "message": "response",
                "code": "kError",
                "detail": "Connection refused",
            }
        )
        # sessiontoken first, then error on accept
        session_token_response = json.dumps(
            {"message": "sessiontoken", "sessionToken": "abc"}
        )
        mock_connection.recv = AsyncMock(
            side_effect=[session_token_response, error_response]
        )
        mock_connection.send = AsyncMock()
        mock_connection.close = AsyncMock()

        with patch(
            "mcp_score.bridge.dorico.websockets.connect",
            new_callable=AsyncMock,
            return_value=mock_connection,
        ):
            # Act
            connected = await bridge.connect()

        # Assert
        assert connected is False

    @pytest.mark.anyio()
    async def test_handshake_no_session_token_in_response(self) -> None:
        # Arrange — Dorico sends unexpected response
        bridge = DoricoBridge()
        mock_connection = AsyncMock()

        bad_response = json.dumps({"message": "sessiontoken"})
        mock_connection.recv = AsyncMock(return_value=bad_response)
        mock_connection.send = AsyncMock()
        mock_connection.close = AsyncMock()

        with patch(
            "mcp_score.bridge.dorico.websockets.connect",
            new_callable=AsyncMock,
            return_value=mock_connection,
        ):
            # Act
            connected = await bridge.connect()

        # Assert
        assert connected is False


# ── Command execution ────────────────────────────────────────────────


class TestDoricoBridgeCommands:
    @pytest.mark.anyio()
    async def test_send_command_formats_message_correctly(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge._connection = AsyncMock()
        bridge._connection.recv = AsyncMock(
            return_value=json.dumps({"message": "response", "code": "kOK"})
        )

        # Act
        await bridge.send_command("Edit.Undo")

        # Assert
        sent_json = json.loads(bridge._connection.send.call_args.args[0])
        assert sent_json["message"] == "command"
        assert sent_json["commandName"] == "Edit.Undo"
        assert "parameters" not in sent_json

    @pytest.mark.anyio()
    async def test_send_command_with_params(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge._connection = AsyncMock()
        bridge._connection.recv = AsyncMock(
            return_value=json.dumps({"message": "response", "code": "kOK"})
        )

        # Act
        await bridge.send_command("Edit.GoToBar", {"barNumber": "5"})

        # Assert
        sent_json = json.loads(bridge._connection.send.call_args.args[0])
        assert sent_json["parameters"] == {"barNumber": "5"}

    @pytest.mark.anyio()
    async def test_send_command_returns_error_when_not_connected(
        self,
    ) -> None:
        # Arrange
        bridge = DoricoBridge(host="localhost", port=19999)

        # Act
        result = await bridge.send_command("Edit.Undo")

        # Assert
        assert "error" in result
        assert "Cannot connect" in result["error"]

    @pytest.mark.anyio()
    async def test_undo_sends_edit_undo_command(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge.send_command = AsyncMock(
            return_value={"message": "response", "code": "kOK"}
        )

        # Act
        await bridge.undo()

        # Assert
        bridge.send_command.assert_called_once_with("Edit.Undo")

    @pytest.mark.anyio()
    async def test_go_to_measure_sends_edit_gotobar(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge.send_command = AsyncMock(
            return_value={"message": "response", "code": "kOK"}
        )

        # Act
        await bridge.go_to_measure(5)

        # Assert
        bridge.send_command.assert_called_once_with("Edit.GoToBar", {"barNumber": "5"})

    @pytest.mark.anyio()
    async def test_go_to_staff_returns_warning(self) -> None:
        # Arrange
        bridge = DoricoBridge()

        # Act
        result = await bridge.go_to_staff(2)

        # Assert
        assert "warning" in result
        assert "does not support" in result["warning"]


class TestDoricoBridgeBarlineMapping:
    @pytest.mark.anyio()
    async def test_set_barline_double(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge.send_command = AsyncMock(
            return_value={"message": "response", "code": "kOK"}
        )

        # Act
        await bridge.set_barline("double")

        # Assert
        bridge.send_command.assert_called_once_with("AddBarlineDouble")

    @pytest.mark.anyio()
    async def test_set_barline_final(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge.send_command = AsyncMock(
            return_value={"message": "response", "code": "kOK"}
        )

        # Act
        await bridge.set_barline("final")

        # Assert
        bridge.send_command.assert_called_once_with("AddBarlineFinal")

    @pytest.mark.anyio()
    async def test_set_barline_unknown_returns_error(self) -> None:
        # Arrange
        bridge = DoricoBridge()

        # Act
        result = await bridge.set_barline("nonexistent")

        # Assert
        assert "error" in result
        assert "Unknown barline type" in result["error"]


class TestDoricoBridgeLimitations:
    @pytest.mark.anyio()
    async def test_set_key_signature_returns_limitation(self) -> None:
        # Arrange
        bridge = DoricoBridge()

        # Act
        result = await bridge.set_key_signature(2)

        # Assert
        assert "error" in result
        assert "does not support" in result["error"]

    @pytest.mark.anyio()
    async def test_set_tempo_returns_limitation(self) -> None:
        # Arrange
        bridge = DoricoBridge()

        # Act
        result = await bridge.set_tempo(120)

        # Assert
        assert "error" in result
        assert "does not support" in result["error"]


class TestDoricoBridgePing:
    @pytest.mark.anyio()
    async def test_ping_true_when_app_info_succeeds(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge.get_app_info = AsyncMock(
            return_value={"variant": "Dorico Pro", "number": "5.1"}
        )

        # Act
        alive = await bridge.ping()

        # Assert
        assert alive is True

    @pytest.mark.anyio()
    async def test_ping_false_when_app_info_has_error(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge.get_app_info = AsyncMock(return_value={"error": "Connection failed"})

        # Act
        alive = await bridge.ping()

        # Assert
        assert alive is False


class TestDoricoBridgeDisconnect:
    @pytest.mark.anyio()
    async def test_disconnect_sends_message_and_closes(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        mock_connection = AsyncMock()
        bridge._connection = mock_connection

        # Act
        await bridge.disconnect()

        # Assert
        mock_connection.send.assert_called_once()
        sent_msg = json.loads(mock_connection.send.call_args.args[0])
        assert sent_msg["message"] == "disconnect"
        mock_connection.close.assert_called_once()
        assert bridge._connection is None

    @pytest.mark.anyio()
    async def test_disconnect_when_not_connected(self) -> None:
        # Arrange
        bridge = DoricoBridge()

        # Act — should not raise
        await bridge.disconnect()

        # Assert
        assert bridge._connection is None


class TestDoricoBridgeProtocolMessages:
    @pytest.mark.anyio()
    async def test_get_app_info(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge._send_message = AsyncMock(  # type: ignore[method-assign]
            return_value={"variant": "Dorico Pro", "number": "5.1"}
        )

        # Act
        result = await bridge.get_app_info()

        # Assert
        bridge._send_message.assert_called_once_with("getappinfo", {"info": "version"})
        assert result["variant"] == "Dorico Pro"

    @pytest.mark.anyio()
    async def test_get_commands(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge._send_message = AsyncMock(  # type: ignore[method-assign]
            return_value={"commands": []}
        )

        # Act
        result = await bridge.get_commands()

        # Assert
        bridge._send_message.assert_called_once_with("getcommands")
        assert result["commands"] == []

    @pytest.mark.anyio()
    async def test_get_status(self) -> None:
        # Arrange
        bridge = DoricoBridge()
        bridge._send_message = AsyncMock(  # type: ignore[method-assign]
            return_value={"hasScore": True}
        )

        # Act
        result = await bridge.get_status()

        # Assert
        bridge._send_message.assert_called_once_with("getstatus")
        assert result["hasScore"] is True


class TestHandshakeError:
    def test_handshake_error_is_exception(self) -> None:
        # Arrange / Act / Assert
        assert issubclass(HandshakeError, Exception)

    def test_handshake_error_message(self) -> None:
        # Arrange / Act
        error = HandshakeError("test message")

        # Assert
        assert str(error) == "test message"
