"""Integration tests: the WebSocket bridge against a live MuseScore plugin.

Requires ``MCP_SCORE_INTEGRATION=1`` and a running MuseScore Studio with
``tests/integration/fixtures/fixture.musicxml`` open and the bridge plugin
started (``uv run scripts/musescore_harness.py start <fixture>``).

Every mutating test undoes its change and checks that the score is back
to what it found, so the tests do not depend on their order. The
read-only checks of the untouched fixture still run first. A command the
plugin refuses raises ``BridgeError``, and a reply that does not fit its
result model fails validation, so a step that must succeed needs no
assertion on its reply.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest

from mcp_score.bridge import BridgeError
from mcp_score.bridge.musescore import MuseScoreBridge
from mcp_score.bridge.results import BarlineSet, Duration, Note

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

pytestmark = pytest.mark.integration

# What the committed fixture score contains: four quarter notes C4 D4 E4 F4.
_FIXTURE_TITLE = "Fixture"
_FIXTURE_PART_COUNT = 1
_FIXTURE_MEASURE_COUNT = 1
_FIXTURE_FIRST_PITCH = 60
_FIXTURE_FIRST_TPC = 14  # C natural

_QUARTER_NOTE = Duration(numerator=1, denominator=4)
_MIDDLE_C = 60
_TEMPO_BPM = 96
_CHORD_SYMBOL = "Cmaj7"
_MINOR_THIRD_DOWN = -3
_A_NATURAL_TPC = 17
_DOUBLE_BARLINE_TYPE = 2
_FIRST_STAFF = 0


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
    return score.measure_count


async def _first_note(bridge: MuseScoreBridge) -> Note:
    """Pitch and spelling of the first note of the chord at the cursor."""
    cursor = await bridge.get_cursor_info()
    assert cursor.element is not None
    assert cursor.element.notes is not None
    return cursor.element.notes[0]


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
        assert score.title == _FIXTURE_TITLE
        assert score.part_count == _FIXTURE_PART_COUNT
        assert len(score.parts) == _FIXTURE_PART_COUNT
        assert score.measure_count == _FIXTURE_MEASURE_COUNT

    @pytest.mark.anyio()
    async def test_go_to_measure_out_of_range_raises(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            count = await _measure_count(bridge)

            # Act / Assert
            with pytest.raises(BridgeError, match="out of range"):
                await bridge.go_to_measure(count + 1)


class TestMuseScoreBridgeModifiesScore:
    @pytest.mark.anyio()
    async def test_append_measures_then_undo_restores_count(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            count_before = await _measure_count(bridge)

            # Act
            appended = await bridge.append_measures(2)
            count_after = await _measure_count(bridge)
            position = await bridge.undo()
            count_restored = await _measure_count(bridge)

        # Assert
        assert appended.total_measures == count_before + 2
        assert count_after == count_before + 2
        assert count_restored == count_before
        assert position.measure <= count_before

    @pytest.mark.anyio()
    async def test_add_note_in_appended_measure_moves_cursor_there(self) -> None:
        # Arrange: add an empty measure to write into.
        async with _connected_bridge() as bridge:
            count_before = await _measure_count(bridge)
            await bridge.append_measures(1)
            new_measure = count_before + 1

            # Act
            moved = await bridge.go_to_measure(new_measure)
            await bridge.add_note(_MIDDLE_C, _QUARTER_NOTE)
            cursor = await bridge.get_cursor_info()
            await bridge.undo()  # the note
            await bridge.undo()  # the measure
            count_restored = await _measure_count(bridge)

        # Assert
        assert moved.measure == new_measure
        assert cursor.measure == new_measure
        assert count_restored == count_before

    @pytest.mark.anyio()
    async def test_set_tempo_returns_bpm(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            await bridge.go_to_measure(1)

            # Act
            tempo = await bridge.set_tempo(_TEMPO_BPM)
            await bridge.undo()

        # Assert
        assert tempo.bpm == _TEMPO_BPM
        assert tempo.measure == 1

    @pytest.mark.anyio()
    async def test_add_chord_symbol_returns_text(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            await bridge.go_to_measure(1)

            # Act
            chord = await bridge.add_chord_symbol(_CHORD_SYMBOL)
            await bridge.undo()
            still_alive = await bridge.ping()

        # Assert
        assert chord.text == _CHORD_SYMBOL
        assert still_alive is True

    @pytest.mark.anyio()
    async def test_set_barline_changes_end_barline_and_undoes(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            await bridge.go_to_measure(1)

            # Act
            changed = await bridge.set_barline("double")
            await bridge.undo()
            still_alive = await bridge.ping()

        # Assert
        assert changed == BarlineSet(barline_type="double", measure=1)
        assert still_alive is True

    @pytest.mark.anyio()
    async def test_set_barline_rejects_unknown_type(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            await bridge.go_to_measure(1)

            # Act / Assert
            with pytest.raises(BridgeError, match="Unknown barline type"):
                await bridge.set_barline("wavy")

    @pytest.mark.anyio()
    async def test_transpose_shifts_pitch_and_spelling_then_undo_restores(
        self,
    ) -> None:
        # Arrange: select the fixture measure on its only staff.
        async with _connected_bridge() as bridge:
            await bridge.go_to_measure(1)
            await bridge.select_range(1, 1, _FIRST_STAFF, _FIRST_STAFF)

            # Act
            transposed = await bridge.transpose(_MINOR_THIRD_DOWN)
            note_after = await _first_note(bridge)
            await bridge.undo()
            note_restored = await _first_note(bridge)

        # Assert: C4 down a minor third is A3, spelled A (not Bbb).
        assert transposed.semitones == _MINOR_THIRD_DOWN
        assert note_after.pitch == _FIXTURE_FIRST_PITCH + _MINOR_THIRD_DOWN
        assert note_after.tpc == _A_NATURAL_TPC
        assert note_restored.pitch == _FIXTURE_FIRST_PITCH
        assert note_restored.tpc == _FIXTURE_FIRST_TPC


class TestMuseScoreBridgeSequences:
    @pytest.mark.anyio()
    async def test_failed_sequence_rolls_back_score_and_cursor(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            await bridge.go_to_measure(1)
            count_before = await _measure_count(bridge)

            # Act: the last step fails, so the appended measure must vanish.
            with pytest.raises(BridgeError) as exc_info:
                await bridge.process_sequence(
                    [
                        {"action": "appendMeasures", "params": {"count": 1}},
                        {
                            "action": "goToMeasure",
                            "params": {"measure": count_before + 1},
                        },
                        {"action": "goToMeasure", "params": {"measure": 999}},
                    ]
                )
            count_after = await _measure_count(bridge)
            cursor = await bridge.get_cursor_info()

        # Assert
        assert exc_info.value.details["failedIndex"] == 2
        assert exc_info.value.details["failedAction"] == "goToMeasure"
        assert count_after == count_before
        assert cursor.measure == 1

    @pytest.mark.anyio()
    async def test_sequence_commits_as_one_undo_step(self) -> None:
        # Arrange
        async with _connected_bridge() as bridge:
            count_before = await _measure_count(bridge)

            # Act
            response = await bridge.process_sequence(
                [
                    {"action": "appendMeasures", "params": {"count": 1}},
                    {"action": "goToMeasure", "params": {"measure": count_before + 1}},
                    {"action": "addNote", "params": {"pitch": _MIDDLE_C}},
                    {"action": "addChordSymbol", "params": {"text": _CHORD_SYMBOL}},
                ]
            )
            count_after = await _measure_count(bridge)
            await bridge.undo()
            count_restored = await _measure_count(bridge)

        # Assert
        assert response["result"]["count"] == 4
        assert count_after == count_before + 1
        assert count_restored == count_before
