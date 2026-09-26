"""Tests for what the tools do differently when Dorico is connected.

Everything the tools share between applications is tested in
``test_tools.py``. These tests connect the ``DoricoBridge`` in the
context's registry to a mock WebSocket and check that Dorico's defaults
and Remote Control limitations reach the model through the tools.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from mcp_score.bridge.dorico import DEFAULT_PORT
from mcp_score.tools import ToolError
from mcp_score.tools.analysis import read_passage
from mcp_score.tools.connection import connect_to_dorico, disconnect_from_dorico
from mcp_score.tools.manipulation import add_live_note, set_live_tempo
from tests.fakes import (
    REMOTE_CONTROL_HANDSHAKE,
    WEBSOCKETS_CONNECT,
    fake_connection,
    sent_payloads,
)

if TYPE_CHECKING:
    from mcp_score.bridge import BridgeRegistry
    from mcp_score.context import ScoreContext

COMMAND_ACCEPTED: dict[str, Any] = {"message": "response", "code": "kOK"}


async def _connect_dorico(
    context: ScoreContext, *command_replies: dict[str, Any]
) -> AsyncMock:
    """Connect the Dorico bridge behind *context* to a mock server.

    The mock completes the handshake and then answers each command with
    the next of *command_replies*.
    """
    connection = fake_connection(*REMOTE_CONTROL_HANDSHAKE, *command_replies)
    with patch(WEBSOCKETS_CONNECT, AsyncMock(return_value=connection)):
        await connect_to_dorico(context)
    return connection


class TestConnectToDorico:
    @pytest.mark.anyio()
    async def test_connect_activates_dorico_on_its_default_port(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange
        connection = fake_connection(*REMOTE_CONTROL_HANDSHAKE)
        connect = AsyncMock(return_value=connection)

        with patch(WEBSOCKETS_CONNECT, connect):
            # Act
            result = await connect_to_dorico(context)

        # Assert
        assert result["success"] is True
        assert (
            f"Connected to Dorico at ws://localhost:{DEFAULT_PORT}"
            in (result["message"])
        )
        assert registry.active is registry.dorico
        connect.assert_awaited_once_with(f"ws://localhost:{DEFAULT_PORT}")

    @pytest.mark.anyio()
    async def test_connect_with_custom_port_uses_it(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange
        connect = AsyncMock(return_value=fake_connection(*REMOTE_CONTROL_HANDSHAKE))

        with patch(WEBSOCKETS_CONNECT, connect):
            # Act
            result = await connect_to_dorico(context, port=5555)

        # Assert
        assert "ws://localhost:5555" in result["message"]
        assert registry.dorico.port == 5555
        connect.assert_awaited_once_with("ws://localhost:5555")

    @pytest.mark.anyio()
    async def test_connect_failure_raises_with_remote_control_hint(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange
        with (
            patch(WEBSOCKETS_CONNECT, AsyncMock(side_effect=OSError("refused"))),
            pytest.raises(ToolError, match="Could not connect to Dorico") as exc_info,
        ):
            # Act
            await connect_to_dorico(context)

        # Assert
        assert "Remote Control" in str(exc_info.value)
        assert registry.active is None

    @pytest.mark.anyio()
    async def test_disconnect_says_goodbye_and_deactivates(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange
        connection = await _connect_dorico(context)

        # Act
        result = await disconnect_from_dorico(context)

        # Assert
        assert result["success"] is True
        assert "Disconnected from Dorico" in result["message"]
        assert sent_payloads(connection)[-1] == {"message": "disconnect"}
        assert registry.active is None


class TestDoricoLimitationsThroughTools:
    @pytest.mark.anyio()
    async def test_read_passage_warns_that_dorico_reports_status_only(
        self, context: ScoreContext
    ) -> None:
        # Arrange
        status: dict[str, Any] = {"message": "status", "playbackPosition": "1"}
        await _connect_dorico(context, COMMAND_ACCEPTED, status)

        # Act
        result = await read_passage(context, 1, 1)

        # Assert
        assert result["elements"] == [{"measure": 1, "content": status}]
        assert "Dorico's Remote Control API" in result["warning"]
        assert "not note content" in result["warning"]

    @pytest.mark.anyio()
    async def test_set_tempo_raises_dorico_popover_limitation(
        self, context: ScoreContext
    ) -> None:
        # Arrange
        connection = await _connect_dorico(context, COMMAND_ACCEPTED)

        # Act
        with pytest.raises(
            ToolError, match="^Dorico's Remote Control API cannot set a tempo"
        ):
            await set_live_tempo(context, 3, 120)

        # Assert
        assert sent_payloads(connection)[-1] == {
            "message": "command",
            "commandName": "Edit.GoToBar",
            "parameters": {"barNumber": "3"},
        }

    @pytest.mark.anyio()
    async def test_add_note_stops_at_staff_navigation_dorico_cannot_do(
        self, context: ScoreContext
    ) -> None:
        # Arrange
        connection = await _connect_dorico(context, COMMAND_ACCEPTED)

        # Act
        with pytest.raises(ToolError, match="cannot move to staff 1"):
            await add_live_note(context, 1, 60, staff=1)

        # Assert
        assert sent_payloads(connection)[-1]["commandName"] == "Edit.GoToBar"
