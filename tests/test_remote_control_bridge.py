"""Tests for the Remote Control protocol layer shared by Dorico-style bridges.

The handshake, message framing, error responses, the operations the
protocol cannot perform, the barline mapping and the position the bridge
tracks itself (the protocol cannot report one) are tested here once, on a
plain ``RemoteControlBridge``. Subclasses only supply defaults, tested in
their own files.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from mcp_score.bridge import BridgeError
from mcp_score.bridge.remote_control import (
    BARLINE_COMMANDS,
    HANDSHAKE_VERSION,
    RemoteControlBridge,
)
from mcp_score.bridge.results import (
    BarlineSet,
    CursorPosition,
    Duration,
)
from tests.fakes import (
    REMOTE_CONTROL_HANDSHAKE,
    SESSION_TOKEN,
    WEBSOCKETS_CONNECT,
    fake_connection,
    sent_payloads,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

type BridgeOperation = Callable[[RemoteControlBridge], Awaitable[object]]

APPLICATION_NAME = "TestApp"
CLIENT_NAME = "test-client"
PORT = 4560
CONNECTED: dict[str, Any] = {"message": "response", "code": "kConnected"}
ACCEPTED: dict[str, Any] = {"message": "response", "code": "kOK"}
REFUSED: dict[str, Any] = {"message": "response", "code": "kError"}


def _bridge() -> RemoteControlBridge:
    return RemoteControlBridge(APPLICATION_NAME, "localhost", PORT, CLIENT_NAME)


async def _connect(
    bridge: RemoteControlBridge, *replies: Any
) -> tuple[bool, AsyncMock]:
    """Connect *bridge* to a mock server that answers with *replies* in order."""
    connection = fake_connection(*replies)
    with patch(WEBSOCKETS_CONNECT, AsyncMock(return_value=connection)):
        connected = await bridge.connect()
    return connected, connection


async def _connected_bridge(
    *command_replies: Any,
) -> tuple[RemoteControlBridge, AsyncMock]:
    """A bridge past its handshake, whose next replies are *command_replies*."""
    bridge = _bridge()
    _, connection = await _connect(bridge, *REMOTE_CONTROL_HANDSHAKE, *command_replies)
    return bridge, connection


# ── Handshake ────────────────────────────────────────────────────────


class TestRemoteControlHandshake:
    @pytest.mark.anyio()
    async def test_fresh_handshake_accepts_offered_session_token(self) -> None:
        # Arrange
        bridge = _bridge()

        # Act
        connected, connection = await _connect(bridge, *REMOTE_CONTROL_HANDSHAKE)

        # Assert
        assert connected is True
        assert bridge.is_connected is True
        assert sent_payloads(connection) == [
            {
                "message": "connect",
                "clientName": CLIENT_NAME,
                "handshakeVersion": HANDSHAKE_VERSION,
            },
            {"message": "acceptsessiontoken", "sessionToken": SESSION_TOKEN},
        ]

    @pytest.mark.anyio()
    async def test_reconnect_offers_cached_token_and_skips_accept(self) -> None:
        # Arrange
        bridge = _bridge()
        await _connect(bridge, *REMOTE_CONTROL_HANDSHAKE)
        await bridge.disconnect()

        # Act
        connected, connection = await _connect(bridge, CONNECTED)

        # Assert
        assert connected is True
        assert sent_payloads(connection) == [
            {
                "message": "connect",
                "clientName": CLIENT_NAME,
                "handshakeVersion": HANDSHAKE_VERSION,
                "sessionToken": SESSION_TOKEN,
            }
        ]

    @pytest.mark.anyio()
    async def test_reconnect_with_expired_token_accepts_new_token(self) -> None:
        # Arrange
        bridge = _bridge()
        await _connect(bridge, *REMOTE_CONTROL_HANDSHAKE)
        await bridge.disconnect()
        new_token = {"message": "sessiontoken", "sessionToken": "new-token"}

        # Act
        connected, connection = await _connect(bridge, new_token, CONNECTED)

        # Assert
        assert connected is True
        assert sent_payloads(connection)[1] == {
            "message": "acceptsessiontoken",
            "sessionToken": "new-token",
        }

    @pytest.mark.anyio()
    async def test_unexpected_reply_to_connect_fails_and_drops_cached_token(
        self,
    ) -> None:
        # Arrange
        bridge = _bridge()
        await _connect(bridge, *REMOTE_CONTROL_HANDSHAKE)
        await bridge.disconnect()

        # Act
        connected, _ = await _connect(bridge, {"message": "response", "code": "kBusy"})
        _, retry_connection = await _connect(bridge, *REMOTE_CONTROL_HANDSHAKE)

        # Assert
        assert connected is False
        assert "sessionToken" not in sent_payloads(retry_connection)[0]

    @pytest.mark.anyio()
    async def test_rejected_token_fails_connection(self) -> None:
        # Arrange
        bridge = _bridge()
        rejection = {"message": "response", "code": "kError", "detail": "Declined"}

        # Act
        connected, connection = await _connect(
            bridge, REMOTE_CONTROL_HANDSHAKE[0], rejection
        )

        # Assert
        assert connected is False
        assert bridge.is_connected is False
        connection.close.assert_awaited_once()

    @pytest.mark.anyio()
    async def test_unexpected_code_after_accept_fails_connection(self) -> None:
        # Arrange
        bridge = _bridge()
        pending = {"message": "response", "code": "kPending"}

        # Act
        connected, _ = await _connect(bridge, REMOTE_CONTROL_HANDSHAKE[0], pending)

        # Assert
        assert connected is False

    @pytest.mark.anyio()
    async def test_session_token_reply_without_token_fails_connection(self) -> None:
        # Arrange
        bridge = _bridge()

        # Act
        connected, connection = await _connect(bridge, {"message": "sessiontoken"})

        # Assert
        assert connected is False
        assert len(sent_payloads(connection)) == 1


# ── Messages ─────────────────────────────────────────────────────────


class TestRemoteControlMessages:
    @pytest.mark.anyio()
    async def test_disconnect_sends_disconnect_message_before_closing(self) -> None:
        # Arrange
        bridge, connection = await _connected_bridge()

        # Act
        await bridge.disconnect()

        # Assert
        assert sent_payloads(connection)[-1] == {"message": "disconnect"}
        connection.close.assert_awaited_once()

    @pytest.mark.anyio()
    async def test_send_command_with_params_frames_command_message(self) -> None:
        # Arrange
        bridge, connection = await _connected_bridge(ACCEPTED)

        # Act
        reply = await bridge.send_command("Edit.GoToBar", {"barNumber": "5"})

        # Assert
        assert reply == ACCEPTED
        assert sent_payloads(connection)[-1] == {
            "message": "command",
            "commandName": "Edit.GoToBar",
            "parameters": {"barNumber": "5"},
        }

    @pytest.mark.anyio()
    async def test_send_command_without_params_omits_parameters(self) -> None:
        # Arrange
        bridge, connection = await _connected_bridge(ACCEPTED)

        # Act
        await bridge.send_command("Edit.Undo")

        # Assert
        assert sent_payloads(connection)[-1] == {
            "message": "command",
            "commandName": "Edit.Undo",
        }

    @pytest.mark.anyio()
    async def test_send_message_merges_fields_into_message(self) -> None:
        # Arrange
        bridge, connection = await _connected_bridge({"message": "appinfo"})

        # Act
        await bridge.send_message("getappinfo", {"info": "version"})

        # Assert
        assert sent_payloads(connection)[-1] == {
            "message": "getappinfo",
            "info": "version",
        }

    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        ("operation", "expected_message"),
        [
            pytest.param(
                partial(RemoteControlBridge.go_to_measure, measure=5),
                {
                    "message": "command",
                    "commandName": "Edit.GoToBar",
                    "parameters": {"barNumber": "5"},
                },
                id="go_to_measure",
            ),
            pytest.param(
                RemoteControlBridge.undo,
                {"message": "command", "commandName": "Edit.Undo"},
                id="undo",
            ),
            pytest.param(
                RemoteControlBridge.get_properties,
                {"message": "getproperties"},
                id="get_properties",
            ),
            pytest.param(
                RemoteControlBridge.get_status,
                {"message": "getstatus"},
                id="get_status",
            ),
            pytest.param(
                RemoteControlBridge.get_flows,
                {"message": "getflows"},
                id="get_flows",
            ),
        ],
    )
    async def test_operation_sends_protocol_message(
        self, operation: BridgeOperation, expected_message: dict[str, Any]
    ) -> None:
        # Arrange
        bridge, connection = await _connected_bridge(ACCEPTED)

        # Act
        await operation(bridge)

        # Assert
        assert sent_payloads(connection)[-1] == expected_message

    @pytest.mark.anyio()
    async def test_get_properties_wraps_reply_as_application_reply(self) -> None:
        # Arrange
        reply: dict[str, Any] = {
            "message": "properties",
            "Properties": [{"Name": "kNoteHideStem", "Value": "false"}],
        }
        bridge, _ = await _connected_bridge(reply)

        # Act
        properties = await bridge.get_properties()

        # Assert: the protocol envelope is dropped, the application's data kept
        assert properties.cursor is None
        assert properties.properties is not None
        assert properties.properties.model_dump() == {"Properties": reply["Properties"]}

    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        ("reply", "expected_message"),
        [
            pytest.param(
                {**REFUSED, "detail": "No selection"},
                "No selection",
                id="with-detail",
            ),
            pytest.param(REFUSED, "the application reported an error", id="bare"),
        ],
    )
    async def test_error_response_raises_with_its_detail(
        self, reply: dict[str, Any], expected_message: str
    ) -> None:
        # Arrange
        bridge, _ = await _connected_bridge(reply)

        # Act / Assert
        with pytest.raises(BridgeError, match=expected_message):
            await bridge.send_command("Edit.Undo")


# ── Operations the protocol cannot perform ───────────────────────────


class TestRemoteControlUnsupportedOperations:
    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        ("operation", "expected_fragment"),
        [
            pytest.param(
                RemoteControlBridge.get_score,
                "cannot describe the score: the API triggers commands",
                id="get_score",
            ),
            pytest.param(
                RemoteControlBridge.get_cursor_info,
                "cannot report the cursor: the API triggers commands",
                id="get_cursor_info",
            ),
            pytest.param(
                partial(RemoteControlBridge.go_to_staff, staff=2),
                "cannot move to staff 2: the API acts on the current selection",
                id="go_to_staff",
            ),
            pytest.param(
                RemoteControlBridge.select_measure,
                "cannot select a measure",
                id="select_measure",
            ),
            pytest.param(
                partial(
                    RemoteControlBridge.select_range,
                    start_measure=1,
                    end_measure=2,
                    start_staff=0,
                    end_staff=0,
                ),
                "cannot select a range",
                id="select_range",
            ),
            pytest.param(
                partial(
                    RemoteControlBridge.add_note,
                    pitch=60,
                    duration=Duration(numerator=1, denominator=4),
                ),
                "cannot add notes: it is entered through a popover",
                id="add_note",
            ),
            pytest.param(
                partial(RemoteControlBridge.add_chord_symbol, text="Cmaj7"),
                "cannot set chord symbol text 'Cmaj7'",
                id="add_chord_symbol",
            ),
            pytest.param(
                partial(RemoteControlBridge.add_dynamic, dynamic="mf"),
                "cannot add the dynamic 'mf'",
                id="add_dynamic",
            ),
            pytest.param(
                partial(RemoteControlBridge.set_key_signature, fifths=2),
                "cannot set a key signature",
                id="set_key_signature",
            ),
            pytest.param(
                partial(
                    RemoteControlBridge.set_time_signature, numerator=3, denominator=4
                ),
                "cannot set a time signature",
                id="set_time_signature",
            ),
            pytest.param(
                partial(RemoteControlBridge.set_tempo, bpm=120),
                "cannot set a tempo",
                id="set_tempo",
            ),
            pytest.param(
                partial(RemoteControlBridge.append_measures, count=2),
                "cannot append measures",
                id="append_measures",
            ),
            pytest.param(
                partial(RemoteControlBridge.transpose, semitones=2),
                "cannot transpose a selection",
                id="transpose",
            ),
        ],
    )
    async def test_operation_raises_explanatory_error_without_sending(
        self, operation: BridgeOperation, expected_fragment: str
    ) -> None:
        # Arrange
        bridge, connection = await _connected_bridge()
        sent_before = len(sent_payloads(connection))

        # Act
        with pytest.raises(BridgeError) as exc_info:
            await operation(bridge)

        # Assert
        message = str(exc_info.value)
        assert message.startswith(f"{APPLICATION_NAME}'s Remote Control API ")
        assert expected_fragment in message
        assert len(sent_payloads(connection)) == sent_before

    def test_content_reading_limitation_names_application(self) -> None:
        # Arrange / Act
        limitation = _bridge().content_reading_limitation

        # Assert
        assert limitation.startswith(f"{APPLICATION_NAME}'s Remote Control API")
        assert "not note content" in limitation


# ── Position tracking ────────────────────────────────────────────────


class TestRemoteControlPosition:
    """The protocol cannot report a position, so the bridge remembers its own."""

    @pytest.mark.anyio()
    async def test_go_to_measure_reports_the_measure_moved_to(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge(ACCEPTED)

        # Act
        position = await bridge.go_to_measure(5)

        # Assert
        assert position == CursorPosition(measure=5, staff=0)

    @pytest.mark.anyio()
    async def test_undo_before_navigating_reports_first_measure(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge(ACCEPTED)

        # Act
        position = await bridge.undo()

        # Assert
        assert position == CursorPosition(measure=1, staff=0)

    @pytest.mark.anyio()
    async def test_undo_reports_last_measure_navigated_to(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge(ACCEPTED, ACCEPTED)
        await bridge.go_to_measure(7)

        # Act
        position = await bridge.undo()

        # Assert
        assert position.measure == 7

    @pytest.mark.anyio()
    async def test_refused_navigation_keeps_previous_measure(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge(
            ACCEPTED, {**REFUSED, "detail": "No such bar"}, ACCEPTED
        )
        await bridge.go_to_measure(4)

        # Act
        with pytest.raises(BridgeError, match="No such bar"):
            await bridge.go_to_measure(99)
        position = await bridge.undo()

        # Assert
        assert position.measure == 4

    @pytest.mark.anyio()
    async def test_add_rehearsal_mark_reports_measure_and_warns_text_ignored(
        self,
    ) -> None:
        # Arrange
        bridge, connection = await _connected_bridge(ACCEPTED, ACCEPTED)
        await bridge.go_to_measure(9)

        # Act
        result = await bridge.add_rehearsal_mark("B")

        # Assert
        assert sent_payloads(connection)[-1] == {
            "message": "command",
            "commandName": "AddRehearsalMark",
        }
        assert (result.text, result.measure) == ("B", 9)
        assert result.warning is not None
        assert "'B' was ignored" in result.warning


# ── Barlines ─────────────────────────────────────────────────────────


class TestRemoteControlBarlines:
    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        ("barline_type", "expected_command"),
        [
            pytest.param("double", "AddBarlineDouble", id="double"),
            pytest.param("final", "AddBarlineFinal", id="final"),
            pytest.param("startRepeat", "AddBarlineStartRepeat", id="startRepeat"),
            pytest.param("endRepeat", "AddBarlineEndRepeat", id="endRepeat"),
        ],
    )
    async def test_set_barline_sends_mapped_command(
        self, barline_type: str, expected_command: str
    ) -> None:
        # Arrange
        bridge, connection = await _connected_bridge(ACCEPTED, ACCEPTED)
        await bridge.go_to_measure(3)

        # Act
        result = await bridge.set_barline(barline_type)

        # Assert
        assert sent_payloads(connection)[-1] == {
            "message": "command",
            "commandName": expected_command,
        }
        assert result == BarlineSet(barline_type=barline_type, measure=3)

    @pytest.mark.anyio()
    async def test_set_barline_with_unknown_type_lists_supported_types(self) -> None:
        # Arrange
        bridge, connection = await _connected_bridge()
        sent_before = len(sent_payloads(connection))

        # Act
        with pytest.raises(BridgeError, match="Unknown barline type 'dashed'") as exc:
            await bridge.set_barline("dashed")

        # Assert
        for supported in BARLINE_COMMANDS:
            assert supported in str(exc.value)
        assert len(sent_payloads(connection)) == sent_before


# ── Ping ─────────────────────────────────────────────────────────────


class TestRemoteControlPing:
    @pytest.mark.anyio()
    async def test_ping_with_app_info_returns_true(self) -> None:
        # Arrange
        bridge, connection = await _connected_bridge({"variant": "Pro", "number": "5"})

        # Act
        alive = await bridge.ping()

        # Assert
        assert alive is True
        assert sent_payloads(connection)[-1] == {
            "message": "getappinfo",
            "info": "version",
        }

    @pytest.mark.anyio()
    async def test_ping_with_error_response_returns_false(self) -> None:
        # Arrange
        bridge, _ = await _connected_bridge({**REFUSED, "detail": "busy"})

        # Act / Assert
        assert await bridge.ping() is False
