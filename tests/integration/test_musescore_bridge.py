"""Integration tests: the WebSocket bridge against a live MuseScore plugin.

Requires ``MCP_SCORE_INTEGRATION=1`` and a running MuseScore Studio with
``tests/integration/fixtures/fixture.musicxml`` open and the bridge plugin
started (``scripts/musescore-headless.sh start <fixture>``).

Every mutating test calls ``undo`` afterwards and checks that it answers
without an error, but it does not rely on the score being restored: on
MuseScore Studio 4.7.5 the plugin's ``cmd("undo")`` is not a registered
action, so the change stays. Tests therefore compare measure counts
relative to what they find, and the read-only checks of the untouched
fixture run first.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest

from mcp_score.bridge.musescore import MuseScoreBridge

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

pytestmark = pytest.mark.integration

# What the committed fixture score contains.
_FIXTURE_TITLE = "Fixture"
_FIXTURE_PART_COUNT = 1
_FIXTURE_MEASURE_COUNT = 1

_QUARTER_NOTE: dict[str, int] = {"numerator": 1, "denominator": 4}
_MIDDLE_C = 60
_TEMPO_BPM = 96
_CHORD_SYMBOL = "Cmaj7"


@asynccontextmanager
async def _connected_bridge() -> AsyncGenerator[MuseScoreBridge]:
    """A bridge that auto-connects on first use and always disconnects."""
    bridge = MuseScoreBridge()
    try:
        yield bridge
    finally:
        await bridge.disconnect()


async def _measure_count(bridge: MuseScoreBridge) -> int:
    score = await bridge.get_score()
    return int(score["result"]["measureCount"])


class TestMuseScoreBridgeReadsFixture:
    """Read-only checks; run first because later tests modify the score."""

    @pytest.mark.anyio()
    async def test_ping_returns_true(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            # Act
            alive = await bridge.ping()

        # Assert
        assert alive is True

    @pytest.mark.anyio()
    async def test_get_score_returns_fixture_metadata(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            # Act
            score = await bridge.get_score()

        # Assert
        assert "error" not in score
        assert score["result"]["title"] == _FIXTURE_TITLE
        assert score["result"]["partCount"] == _FIXTURE_PART_COUNT
        assert score["result"]["measureCount"] == _FIXTURE_MEASURE_COUNT

    @pytest.mark.anyio()
    async def test_go_to_measure_out_of_range_returns_error(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            count = await _measure_count(bridge)

            # Act
            response = await bridge.go_to_measure(count + 1)

        # Assert
        assert "out of range" in response["error"]


class TestMuseScoreBridgeModifiesScore:
    @pytest.mark.anyio()
    async def test_append_measures_increases_measure_count(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            count_before = await _measure_count(bridge)

            # Act
            appended = await bridge.append_measures(2)
            count_after = await _measure_count(bridge)
            undone = await bridge.undo()

        # Assert
        assert appended["result"]["totalMeasures"] == count_before + 2
        assert count_after == count_before + 2
        assert "error" not in undone

    @pytest.mark.anyio()
    async def test_add_note_in_appended_measure_moves_cursor_there(self) -> None:
        # Arrange: add an empty measure to write into.
        async with _connected_bridge() as bridge:
            count_before = await _measure_count(bridge)
            await bridge.append_measures(1)
            new_measure = count_before + 1

            # Act
            moved = await bridge.go_to_measure(new_measure)
            added = await bridge.add_note(_MIDDLE_C, _QUARTER_NOTE)
            cursor = await bridge.get_cursor_info()
            undone = await bridge.undo()

        # Assert
        assert moved["result"]["measure"] == new_measure
        assert "error" not in added
        assert cursor["result"]["measure"] == new_measure
        assert "error" not in undone

    @pytest.mark.anyio()
    async def test_set_tempo_returns_bpm(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            await bridge.go_to_measure(1)

            # Act
            tempo = await bridge.set_tempo(_TEMPO_BPM)
            undone = await bridge.undo()

        # Assert
        assert tempo["result"]["bpm"] == _TEMPO_BPM
        assert "error" not in undone

    @pytest.mark.skip(
        reason="addChordSymbol crashes MuseScore Studio 4.7.5 (segmentation "
        "fault when the plugin adds an Element.HARMONY through the cursor), "
        "which would kill the bridge for every later test"
    )
    @pytest.mark.anyio()
    async def test_add_chord_symbol_returns_text(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            await bridge.go_to_measure(1)

            # Act
            chord = await bridge.add_chord_symbol(_CHORD_SYMBOL)
            undone = await bridge.undo()

        # Assert
        assert chord["result"]["text"] == _CHORD_SYMBOL
        assert "error" not in undone
