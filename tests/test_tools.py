"""Tests for the MCP tools: the error wrapper, connection, analysis, manipulation.

Behaviour shared by every application (validation, the not-connected
error, navigation, what the bridge is asked to do) is tested here once,
against a ``FakeBridge`` behind the context a tool receives from the
server. A tool that cannot do what was asked raises ``ToolError``; an
application's refusal (``BridgeError``) reaches the model the same way.
Dorico-specific behaviour lives in ``test_dorico_tools.py``.
"""

from __future__ import annotations

import inspect
import re
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from mcp_score.bridge import BridgeError, CommandResult, NoteDuration
from mcp_score.tools import NOT_CONNECTED, ToolError, score_tool
from mcp_score.tools.analysis import (
    get_measure_content,
    get_selection_properties,
    read_passage,
)
from mcp_score.tools.connection import (
    connect_to_musescore,
    disconnect_from_musescore,
    get_live_score_info,
    ping_score_app,
)
from mcp_score.tools.manipulation import (
    add_live_chord_symbol,
    add_live_dynamic,
    add_live_note,
    add_live_rehearsal_mark,
    append_live_measures,
    set_live_barline,
    set_live_key_signature,
    set_live_tempo,
    set_live_time_signature,
    transpose_passage,
    undo_last_action,
)
from tests.fakes import WEBSOCKETS_CONNECT, BridgeCall, FakeBridge, fake_connection

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Concatenate

    from mcp_score.bridge import BridgeRegistry
    from mcp_score.context import ScoreContext

type ToolCall = Callable[[ScoreContext], Awaitable[CommandResult]]
"""A tool with its arguments bound, ready to run against a context."""


def bind_arguments[**P](
    tool: Callable[Concatenate[ScoreContext, P], Awaitable[CommandResult]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> ToolCall:
    """Bind a tool's arguments, leaving the context for the test to supply."""

    def call(context: ScoreContext) -> Awaitable[CommandResult]:
        return tool(context, *args, **kwargs)

    return call


NAVIGATION_ERROR = "Measure 99 is beyond the end of the score"


# ── score_tool ────────────────────────────────────────────────────────


class TestScoreTool:
    @pytest.mark.anyio()
    async def test_bridge_error_becomes_tool_error_with_same_message(self) -> None:
        # Arrange
        refusal = BridgeError("Measure 99 out of range", measure=99)

        @score_tool
        async def refused() -> CommandResult:
            raise refusal

        # Act
        with pytest.raises(ToolError) as exc_info:
            await refused()

        # Assert
        assert str(exc_info.value) == "Measure 99 out of range"
        assert exc_info.value.__cause__ is refusal

    @pytest.mark.anyio()
    async def test_result_passes_through(self) -> None:
        # Arrange
        @score_tool
        async def succeeding(value: str) -> CommandResult:
            return {"success": True, "value": value}

        # Act
        result = await succeeding("x")

        # Assert
        assert result == {"success": True, "value": "x"}

    def test_wrapper_keeps_parameters(self) -> None:
        # Arrange
        async def original(measure: int, text: str = "A") -> CommandResult:
            return {}

        # Act
        wrapped = score_tool(original)

        # Assert
        assert (
            inspect.signature(wrapped).parameters
            == inspect.signature(original).parameters
        )
        assert wrapped.__name__ == "original"


# ── Not connected ────────────────────────────────────────────────────


class TestToolsWithoutConnection:
    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        "call",
        [
            pytest.param(get_live_score_info, id="get_live_score_info"),
            pytest.param(ping_score_app, id="ping_score_app"),
            pytest.param(bind_arguments(read_passage, 1, 4), id="read_passage"),
            pytest.param(
                bind_arguments(get_measure_content, 1),
                id="get_measure_content",
            ),
            pytest.param(get_selection_properties, id="get_selection_properties"),
            pytest.param(bind_arguments(add_live_note, 1, 60), id="add_live_note"),
            pytest.param(
                bind_arguments(add_live_rehearsal_mark, 1, "A"),
                id="add_live_rehearsal_mark",
            ),
            pytest.param(
                bind_arguments(add_live_chord_symbol, 1, "Cmaj7"),
                id="add_live_chord_symbol",
            ),
            pytest.param(
                bind_arguments(add_live_dynamic, 1, "mf"),
                id="add_live_dynamic",
            ),
            pytest.param(
                bind_arguments(set_live_barline, 1, "double"),
                id="set_live_barline",
            ),
            pytest.param(
                bind_arguments(set_live_key_signature, 1, 2),
                id="set_live_key_signature",
            ),
            pytest.param(
                bind_arguments(set_live_time_signature, 1, 3, 4),
                id="set_live_time_signature",
            ),
            pytest.param(bind_arguments(set_live_tempo, 1, 120), id="set_live_tempo"),
            pytest.param(
                bind_arguments(append_live_measures, 2),
                id="append_live_measures",
            ),
            pytest.param(
                bind_arguments(transpose_passage, 1, 4, 0, 2),
                id="transpose_passage",
            ),
            pytest.param(undo_last_action, id="undo_last_action"),
        ],
    )
    async def test_tool_without_connection_raises_not_connected(
        self, context: ScoreContext, call: ToolCall
    ) -> None:
        # Arrange: the fresh registry behind the context has nothing active.
        # Act / Assert
        with pytest.raises(ToolError, match=re.escape(NOT_CONNECTED)):
            await call(context)

    @pytest.mark.anyio()
    async def test_tool_with_disconnected_active_bridge_raises_not_connected(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange
        registry.active = FakeBridge(is_connected=False)

        # Act / Assert
        with pytest.raises(ToolError, match=re.escape(NOT_CONNECTED)):
            await undo_last_action(context)


# ── Connection tools ─────────────────────────────────────────────────


class TestConnectToMusescore:
    @pytest.mark.anyio()
    async def test_connect_activates_musescore_at_given_address(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange
        connect = AsyncMock(return_value=fake_connection())

        with patch(WEBSOCKETS_CONNECT, connect):
            # Act
            result = await connect_to_musescore(context, host="10.0.0.5", port=9000)

        # Assert
        assert result["success"] is True
        assert "ws://10.0.0.5:9000" in result["message"]
        assert registry.active is registry.musescore
        assert registry.musescore.is_connected is True
        connect.assert_awaited_once_with("ws://10.0.0.5:9000")

    @pytest.mark.anyio()
    async def test_connect_failure_raises_with_plugin_hint(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange
        with (
            patch(WEBSOCKETS_CONNECT, AsyncMock(side_effect=OSError("refused"))),
            pytest.raises(
                ToolError, match="Could not connect to MuseScore"
            ) as exc_info,
        ):
            # Act
            await connect_to_musescore(context)

        # Assert
        assert "plugin" in str(exc_info.value)
        assert registry.active is None

    @pytest.mark.anyio()
    async def test_disconnect_closes_connection_and_deactivates(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange
        connection = fake_connection()
        with patch(WEBSOCKETS_CONNECT, AsyncMock(return_value=connection)):
            await connect_to_musescore(context)

        # Act
        result = await disconnect_from_musescore(context)

        # Assert
        assert result["success"] is True
        assert "Disconnected from MuseScore" in result["message"]
        assert registry.active is None
        connection.close.assert_awaited_once()


class TestGetLiveScoreInfo:
    @pytest.mark.anyio()
    async def test_get_info_returns_bridge_score(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Arrange
        connected_bridge.reply("get_score", {"result": {"title": "Test Score"}})

        # Act
        result = await get_live_score_info(context)

        # Assert
        assert result == {"result": {"title": "Test Score"}}


class TestPingScoreApp:
    @pytest.mark.anyio()
    async def test_ping_responsive_app_returns_success(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Arrange
        connected_bridge.ping_succeeds = True

        # Act
        result = await ping_score_app(context)

        # Assert
        assert result["success"] is True
        assert "FakeApp is responsive" in result["message"]

    @pytest.mark.anyio()
    async def test_ping_unresponsive_app_raises(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Arrange
        connected_bridge.ping_succeeds = False

        # Act / Assert
        with pytest.raises(ToolError, match="FakeApp is not responding"):
            await ping_score_app(context)


# ── Analysis tools ───────────────────────────────────────────────────


class TestReadPassage:
    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        ("start_measure", "end_measure", "expected_error"),
        [
            pytest.param(0, 4, "start_measure must be >= 1.", id="start-below-one"),
            pytest.param(5, 3, "end_measure must be >= start_measure.", id="empty"),
        ],
    )
    async def test_read_passage_with_invalid_range_raises_without_reading(
        self,
        connected_bridge: FakeBridge,
        context: ScoreContext,
        start_measure: int,
        end_measure: int,
        expected_error: str,
    ) -> None:
        # Act
        with pytest.raises(ToolError, match=re.escape(expected_error)):
            await read_passage(context, start_measure, end_measure)

        # Assert
        assert connected_bridge.calls == []

    @pytest.mark.anyio()
    async def test_read_passage_reads_cursor_in_every_measure(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Arrange
        connected_bridge.reply("get_cursor_info", {"result": {"beat": 1}})

        # Act
        result = await read_passage(context, 2, 3)

        # Assert
        assert result["success"] is True
        assert result["staff"] is None
        assert result["elements"] == [
            {"measure": 2, "content": {"result": {"beat": 1}}},
            {"measure": 3, "content": {"result": {"beat": 1}}},
        ]
        assert connected_bridge.calls == [
            BridgeCall("go_to_measure", (2,)),
            BridgeCall("get_cursor_info", ()),
            BridgeCall("go_to_measure", (3,)),
            BridgeCall("get_cursor_info", ()),
        ]

    @pytest.mark.anyio()
    async def test_read_passage_with_staff_moves_to_staff_in_every_measure(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Act
        await read_passage(context, 1, 2, staff=3)

        # Assert
        assert connected_bridge.calls_to("go_to_staff") == [
            BridgeCall("go_to_staff", (3,)),
            BridgeCall("go_to_staff", (3,)),
        ]

    @pytest.mark.anyio()
    async def test_read_passage_with_navigation_error_stops_reading(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Arrange
        connected_bridge.fail("go_to_measure", NAVIGATION_ERROR)

        # Act
        with pytest.raises(ToolError, match=NAVIGATION_ERROR):
            await read_passage(context, 99, 100)

        # Assert
        assert connected_bridge.calls == [BridgeCall("go_to_measure", (99,))]

    @pytest.mark.anyio()
    async def test_read_passage_attaches_content_reading_limitation(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange
        registry.active = FakeBridge(
            content_reading_limitation="Only status is available."
        )

        # Act
        result = await read_passage(context, 1, 1)

        # Assert
        assert result["warning"] == "Only status is available."

    @pytest.mark.anyio()
    async def test_read_passage_without_limitation_has_no_warning(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Act
        result = await read_passage(context, 1, 1)

        # Assert
        assert "warning" not in result


class TestGetMeasureContent:
    @pytest.mark.anyio()
    async def test_get_measure_with_invalid_number_raises_without_navigating(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Act
        with pytest.raises(ToolError, match="measure must be >= 1"):
            await get_measure_content(context, 0)

        # Assert
        assert connected_bridge.calls == []

    @pytest.mark.anyio()
    async def test_get_measure_navigates_then_selects(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Arrange
        connected_bridge.reply("select_measure", {"result": {"notes": ["C4"]}})

        # Act
        result = await get_measure_content(context, 3, staff=1)

        # Assert
        assert result == {"result": {"notes": ["C4"]}}
        assert connected_bridge.calls == [
            BridgeCall("go_to_measure", (3,)),
            BridgeCall("go_to_staff", (1,)),
            BridgeCall("select_measure", ()),
        ]

    @pytest.mark.anyio()
    async def test_get_measure_with_staff_error_does_not_select(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Arrange
        connected_bridge.fail("go_to_staff", "No staff 7")

        # Act
        with pytest.raises(ToolError, match="No staff 7"):
            await get_measure_content(context, 1, staff=7)

        # Assert
        assert connected_bridge.calls_to("select_measure") == []

    @pytest.mark.anyio()
    async def test_get_measure_attaches_content_reading_limitation(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange
        registry.active = FakeBridge(
            content_reading_limitation="Only status is available."
        )

        # Act
        result = await get_measure_content(context, 1)

        # Assert
        assert result["warning"] == "Only status is available."


class TestGetSelectionProperties:
    @pytest.mark.anyio()
    async def test_get_properties_returns_bridge_properties(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Arrange
        connected_bridge.reply(
            "get_properties", {"Properties": [{"Name": "kNoteHideStem"}]}
        )

        # Act
        result = await get_selection_properties(context)

        # Assert
        assert result == {"Properties": [{"Name": "kNoteHideStem"}]}


# ── Manipulation tools ───────────────────────────────────────────────


class TestManipulationValidation:
    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        ("call", "expected_error"),
        [
            pytest.param(
                bind_arguments(add_live_note, 0, 60),
                "measure must be >= 1.",
                id="note-measure-zero",
            ),
            pytest.param(
                bind_arguments(add_live_note, 1, 128),
                "pitch must be between 0 and 127.",
                id="note-pitch-too-high",
            ),
            pytest.param(
                bind_arguments(add_live_note, 1, -1),
                "pitch must be between 0 and 127.",
                id="note-pitch-negative",
            ),
            pytest.param(
                bind_arguments(add_live_note, 1, 60, numerator=0),
                "numerator and denominator must be >= 1.",
                id="note-zero-numerator",
            ),
            pytest.param(
                bind_arguments(add_live_note, 1, 60, denominator=0),
                "numerator and denominator must be >= 1.",
                id="note-zero-denominator",
            ),
            pytest.param(
                bind_arguments(add_live_rehearsal_mark, 0, "A"),
                "measure must be >= 1.",
                id="rehearsal-mark-measure-zero",
            ),
            pytest.param(
                bind_arguments(add_live_chord_symbol, -1, "Cmaj7"),
                "measure must be >= 1.",
                id="chord-symbol-negative-measure",
            ),
            pytest.param(
                bind_arguments(add_live_dynamic, 0, "mf"),
                "measure must be >= 1.",
                id="dynamic-measure-zero",
            ),
            pytest.param(
                bind_arguments(set_live_barline, 0, "double"),
                "measure must be >= 1.",
                id="barline-measure-zero",
            ),
            pytest.param(
                bind_arguments(set_live_key_signature, 0, 2),
                "measure must be >= 1.",
                id="key-signature-measure-zero",
            ),
            pytest.param(
                bind_arguments(set_live_time_signature, 1, 3, 0),
                "numerator and denominator must be >= 1.",
                id="time-signature-zero-denominator",
            ),
            pytest.param(
                bind_arguments(set_live_tempo, 1, 0),
                "bpm must be >= 1.",
                id="tempo-zero-bpm",
            ),
            pytest.param(
                bind_arguments(append_live_measures, 0),
                "count must be >= 1.",
                id="append-zero-measures",
            ),
            pytest.param(
                bind_arguments(transpose_passage, 5, 3, 0, 2),
                "end_measure must be >= start_measure.",
                id="transpose-empty-range",
            ),
            pytest.param(
                bind_arguments(transpose_passage, 0, 3, 0, 2),
                "start_measure must be >= 1.",
                id="transpose-start-zero",
            ),
        ],
    )
    async def test_tool_with_invalid_argument_raises_without_touching_score(
        self,
        connected_bridge: FakeBridge,
        context: ScoreContext,
        call: ToolCall,
        expected_error: str,
    ) -> None:
        # Act
        with pytest.raises(ToolError, match=re.escape(expected_error)):
            await call(context)

        # Assert
        assert connected_bridge.calls == []


class TestManipulationHappyPaths:
    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        ("call", "expected_calls"),
        [
            pytest.param(
                bind_arguments(add_live_note, 5, 60, 1, 8, staff=1),
                [
                    BridgeCall("go_to_measure", (5,)),
                    BridgeCall("go_to_staff", (1,)),
                    BridgeCall("add_note", (60, NoteDuration(1, 8), True)),
                ],
                id="add_live_note",
            ),
            pytest.param(
                bind_arguments(add_live_rehearsal_mark, 5, "B"),
                [
                    BridgeCall("go_to_measure", (5,)),
                    BridgeCall("add_rehearsal_mark", ("B",)),
                ],
                id="add_live_rehearsal_mark",
            ),
            pytest.param(
                bind_arguments(add_live_chord_symbol, 2, "Dm7"),
                [
                    BridgeCall("go_to_measure", (2,)),
                    BridgeCall("add_chord_symbol", ("Dm7",)),
                ],
                id="add_live_chord_symbol",
            ),
            pytest.param(
                bind_arguments(add_live_dynamic, 4, "ff", staff=2),
                [
                    BridgeCall("go_to_measure", (4,)),
                    BridgeCall("go_to_staff", (2,)),
                    BridgeCall("add_dynamic", ("ff",)),
                ],
                id="add_live_dynamic",
            ),
            pytest.param(
                bind_arguments(set_live_barline, 3, "double"),
                [
                    BridgeCall("go_to_measure", (3,)),
                    BridgeCall("set_barline", ("double",)),
                ],
                id="set_live_barline",
            ),
            pytest.param(
                bind_arguments(set_live_key_signature, 1, -3),
                [
                    BridgeCall("go_to_measure", (1,)),
                    BridgeCall("set_key_signature", (-3,)),
                ],
                id="set_live_key_signature",
            ),
            pytest.param(
                bind_arguments(set_live_time_signature, 9, 6, 8),
                [
                    BridgeCall("go_to_measure", (9,)),
                    BridgeCall("set_time_signature", (6, 8)),
                ],
                id="set_live_time_signature",
            ),
            pytest.param(
                bind_arguments(set_live_tempo, 1, 66, "Slow Blues"),
                [
                    BridgeCall("go_to_measure", (1,)),
                    BridgeCall("set_tempo", (66, "Slow Blues")),
                ],
                id="set_live_tempo-with-text",
            ),
            pytest.param(
                bind_arguments(set_live_tempo, 1, 120),
                [
                    BridgeCall("go_to_measure", (1,)),
                    BridgeCall("set_tempo", (120, None)),
                ],
                id="set_live_tempo-without-text",
            ),
            pytest.param(
                bind_arguments(append_live_measures, 4),
                [BridgeCall("append_measures", (4,))],
                id="append_live_measures",
            ),
            pytest.param(
                bind_arguments(transpose_passage, 1, 8, 2, 5),
                [
                    BridgeCall("go_to_measure", (1,)),
                    BridgeCall("go_to_staff", (2,)),
                    BridgeCall("select_range", (1, 8, 2, 2)),
                    BridgeCall("transpose", (5,)),
                ],
                id="transpose_passage",
            ),
            pytest.param(
                undo_last_action,
                [BridgeCall("undo", ())],
                id="undo_last_action",
            ),
        ],
    )
    async def test_tool_asks_bridge_in_order_and_returns_its_reply(
        self,
        connected_bridge: FakeBridge,
        context: ScoreContext,
        call: ToolCall,
        expected_calls: list[BridgeCall],
    ) -> None:
        # Arrange
        final_method = expected_calls[-1].method
        connected_bridge.reply(final_method, {"result": {"done": final_method}})

        # Act
        result = await call(context)

        # Assert
        assert result == {"result": {"done": final_method}}
        assert connected_bridge.calls == expected_calls

    @pytest.mark.anyio()
    async def test_append_measures_defaults_to_one(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Act
        await append_live_measures(context)

        # Assert
        assert connected_bridge.calls == [BridgeCall("append_measures", (1,))]


class TestManipulationNavigationErrors:
    """A tool that cannot reach its measure must not change anything."""

    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        "call",
        [
            pytest.param(bind_arguments(add_live_note, 99, 60), id="add_live_note"),
            pytest.param(
                bind_arguments(add_live_rehearsal_mark, 99, "A"),
                id="add_live_rehearsal_mark",
            ),
            pytest.param(
                bind_arguments(add_live_chord_symbol, 99, "C7"),
                id="add_live_chord_symbol",
            ),
            pytest.param(
                bind_arguments(add_live_dynamic, 99, "p"),
                id="add_live_dynamic",
            ),
            pytest.param(
                bind_arguments(set_live_barline, 99, "final"),
                id="set_live_barline",
            ),
            pytest.param(
                bind_arguments(set_live_key_signature, 99, 1),
                id="set_live_key_signature",
            ),
            pytest.param(
                bind_arguments(set_live_time_signature, 99, 3, 4),
                id="set_live_time_signature",
            ),
            pytest.param(bind_arguments(set_live_tempo, 99, 100), id="set_live_tempo"),
            pytest.param(
                bind_arguments(transpose_passage, 99, 100, 0, 2),
                id="transpose_passage",
            ),
        ],
    )
    async def test_tool_with_measure_error_raises_it_and_writes_nothing(
        self, connected_bridge: FakeBridge, context: ScoreContext, call: ToolCall
    ) -> None:
        # Arrange
        connected_bridge.fail("go_to_measure", NAVIGATION_ERROR)

        # Act
        with pytest.raises(ToolError, match=NAVIGATION_ERROR):
            await call(context)

        # Assert
        assert connected_bridge.calls == [BridgeCall("go_to_measure", (99,))]

    @pytest.mark.anyio()
    async def test_tool_with_staff_error_raises_it_and_writes_nothing(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Arrange
        connected_bridge.fail("go_to_staff", "No staff 7")

        # Act
        with pytest.raises(ToolError, match="No staff 7"):
            await add_live_dynamic(context, 1, "mf", staff=7)

        # Assert
        assert connected_bridge.calls == [
            BridgeCall("go_to_measure", (1,)),
            BridgeCall("go_to_staff", (7,)),
        ]


class TestTransposePassage:
    @pytest.mark.anyio()
    async def test_transpose_with_failed_selection_raises_without_transposing(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Arrange
        connected_bridge.fail("select_range", "Invalid range")

        # Act
        with pytest.raises(ToolError, match="Invalid range"):
            await transpose_passage(context, 1, 4, 0, 5)

        # Assert
        assert connected_bridge.calls_to("transpose") == []

    @pytest.mark.anyio()
    async def test_transpose_single_measure_selects_that_measure(
        self, connected_bridge: FakeBridge, context: ScoreContext
    ) -> None:
        # Act
        await transpose_passage(context, 5, 5, 0, 2)

        # Assert
        assert connected_bridge.calls_to("select_range") == [
            BridgeCall("select_range", (5, 5, 0, 0))
        ]
