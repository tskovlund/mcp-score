"""Tests for the ScoreManager — builds and modifies scores using music21."""

from pathlib import Path
from typing import Any

import pytest
from music21 import bar, expressions, harmony, note, stream, tempo

from mcp_score.score_manager import ScoreManager


@pytest.fixture()
def manager() -> ScoreManager:
    """Fresh ScoreManager for each test."""
    return ScoreManager()


@pytest.fixture()
def manager_with_score(manager: ScoreManager) -> ScoreManager:
    """ScoreManager with a simple one-instrument score already created."""
    manager.create_score(
        title="Test",
        instruments=["trumpet"],
        key_signature="C major",
        time_signature="4/4",
        tempo_bpm=120,
        num_measures=4,
    )
    return manager


class TestCreateScore:
    def test_create_score_returns_success(self, manager: ScoreManager) -> None:
        # Arrange / Act
        result = manager.create_score(
            title="My Score",
            instruments=["trumpet"],
        )

        # Assert
        assert result["success"] is True
        assert "My Score" in result["message"]

    def test_create_score_returns_parts_list(self, manager: ScoreManager) -> None:
        # Arrange / Act
        result = manager.create_score(
            title="Test",
            instruments=["trumpet"],
        )

        # Assert
        assert "parts" in result
        assert len(result["parts"]) == 1

    def test_create_score_returns_num_measures(self, manager: ScoreManager) -> None:
        # Arrange / Act
        result = manager.create_score(
            title="Test",
            instruments=["piano"],
            num_measures=16,
        )

        # Assert
        assert result["num_measures"] == 16

    def test_create_score_handles_multiple_instruments(
        self, manager: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager.create_score(
            title="Quartet",
            instruments=["violin 1", "violin 2", "viola", "cello"],
        )

        # Assert
        assert result["success"] is True
        assert len(result["parts"]) == 4

    def test_create_score_invalid_key_signature_returns_error(
        self, manager: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager.create_score(
            title="Bad Key",
            instruments=["trumpet"],
            key_signature="X nonsense",
        )

        # Assert
        assert "error" in result

    def test_create_score_invalid_time_signature_returns_error(
        self, manager: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager.create_score(
            title="Bad Time",
            instruments=["trumpet"],
            time_signature="abc",
        )

        # Assert
        assert "error" in result

    def test_create_score_requires_at_least_one_instrument(
        self, manager: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager.create_score(
            title="Empty",
            instruments=[],
        )

        # Assert
        assert "error" in result
        assert "At least one instrument" in result["error"]

    def test_create_score_sets_has_score(self, manager: ScoreManager) -> None:
        # Arrange
        assert not manager.has_score

        # Act
        manager.create_score(title="Test", instruments=["piano"])

        # Assert
        assert manager.has_score

    def test_create_score_with_flat_key(self, manager: ScoreManager) -> None:
        # Arrange / Act
        result = manager.create_score(
            title="Bb Piece",
            instruments=["trumpet"],
            key_signature="Bb major",
        )

        # Assert
        assert result["success"] is True

    def test_create_score_with_sharp_key(self, manager: ScoreManager) -> None:
        # Arrange / Act
        result = manager.create_score(
            title="F# Piece",
            instruments=["piano"],
            key_signature="F# minor",
        )

        # Assert
        assert result["success"] is True

    def test_create_score_with_waltz_time(self, manager: ScoreManager) -> None:
        # Arrange / Act
        result = manager.create_score(
            title="Waltz",
            instruments=["piano"],
            time_signature="3/4",
        )

        # Assert
        assert result["success"] is True


class TestAddNotes:
    def test_add_notes_returns_success(self, manager_with_score: ScoreManager) -> None:
        # Arrange
        notes: list[dict[str, str]] = [
            {"pitch": "C5", "duration": "quarter"},
            {"pitch": "D5", "duration": "quarter"},
            {"pitch": "E5", "duration": "quarter"},
            {"pitch": "F5", "duration": "quarter"},
        ]

        # Act
        result = manager_with_score.add_notes(
            part_index_or_name="0", measure=1, notes=notes
        )

        # Assert
        assert result["success"] is True

    def test_add_notes_replaces_existing_content(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange — first add notes
        first_notes: list[dict[str, str]] = [
            {"pitch": "C5", "duration": "whole"},
        ]
        manager_with_score.add_notes(
            part_index_or_name="0", measure=1, notes=first_notes
        )

        # Act — replace with different notes
        second_notes: list[dict[str, str]] = [
            {"pitch": "G5", "duration": "half"},
            {"pitch": "A5", "duration": "half"},
        ]
        result = manager_with_score.add_notes(
            part_index_or_name="0", measure=1, notes=second_notes
        )

        # Assert
        assert result["success"] is True
        score = manager_with_score._score  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        assert score is not None
        part = list(score.parts)[0]
        target_measure = part.measure(1)
        assert target_measure is not None
        actual_notes = list(target_measure.notesAndRests)
        assert len(actual_notes) == 2

    def test_add_notes_handles_rests(self, manager_with_score: ScoreManager) -> None:
        # Arrange
        notes: list[dict[str, str]] = [
            {"pitch": "C5", "duration": "quarter"},
            {"pitch": "rest", "duration": "quarter"},
            {"pitch": "E5", "duration": "half"},
        ]

        # Act
        result = manager_with_score.add_notes(
            part_index_or_name="0", measure=1, notes=notes
        )

        # Assert
        assert result["success"] is True
        score = manager_with_score._score  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        assert score is not None
        part = list(score.parts)[0]
        target_measure = part.measure(1)
        assert target_measure is not None
        elements = list(target_measure.notesAndRests)
        rest_elements = [e for e in elements if isinstance(e, note.Rest)]
        assert len(rest_elements) == 1

    def test_add_notes_handles_flats(self, manager_with_score: ScoreManager) -> None:
        # Arrange
        notes: list[dict[str, str]] = [
            {"pitch": "Bb4", "duration": "half"},
            {"pitch": "Eb5", "duration": "half"},
        ]

        # Act
        result = manager_with_score.add_notes(
            part_index_or_name="0", measure=1, notes=notes
        )

        # Assert
        assert result["success"] is True
        score = manager_with_score._score  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        assert score is not None
        part = list(score.parts)[0]
        target_measure = part.measure(1)
        assert target_measure is not None
        actual_notes = [
            e for e in target_measure.notesAndRests if isinstance(e, note.Note)
        ]
        assert len(actual_notes) == 2
        # B-flat should be stored as B-4 in music21
        assert actual_notes[0].pitch.name == "B-"
        assert actual_notes[1].pitch.name == "E-"

    def test_add_notes_rejects_invalid_pitch(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange
        notes: list[dict[str, str]] = [
            {"pitch": "ZZZ999", "duration": "quarter"},
        ]

        # Act
        result = manager_with_score.add_notes(
            part_index_or_name="0", measure=1, notes=notes
        )

        # Assert
        assert "error" in result

    def test_add_notes_rejects_invalid_duration(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange
        notes: list[dict[str, str]] = [
            {"pitch": "C5", "duration": "superlongvalue"},
        ]

        # Act
        result = manager_with_score.add_notes(
            part_index_or_name="0", measure=1, notes=notes
        )

        # Assert
        assert "error" in result
        assert "Unknown duration" in result["error"]

    def test_add_notes_find_part_by_name(self, manager: ScoreManager) -> None:
        # Arrange
        manager.create_score(
            title="Duo",
            instruments=["trumpet", "piano"],
            num_measures=4,
        )
        notes: list[dict[str, str]] = [
            {"pitch": "C4", "duration": "whole"},
        ]

        # Act
        result = manager.add_notes(part_index_or_name="piano", measure=1, notes=notes)

        # Assert
        assert result["success"] is True


class TestAddRehearsalMark:
    def test_add_rehearsal_mark_returns_success(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager_with_score.add_rehearsal_mark(measure=1, label="A")

        # Assert
        assert result["success"] is True
        assert "A" in result["message"]

    def test_add_rehearsal_mark_at_correct_measure(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        manager_with_score.add_rehearsal_mark(measure=2, label="B")

        # Assert
        score = manager_with_score._score  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        assert score is not None
        first_part = list(score.parts)[0]
        target_measure = first_part.measure(2)
        assert target_measure is not None
        marks = list(target_measure.getElementsByClass(expressions.RehearsalMark))
        assert len(marks) == 1
        assert marks[0].content == "B"


class TestSetBarline:
    def test_set_barline_returns_success(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager_with_score.set_barline(measure=4, barline_type="final")

        # Assert
        assert result["success"] is True

    def test_set_barline_sets_on_all_parts(self, manager: ScoreManager) -> None:
        # Arrange
        manager.create_score(
            title="Duo",
            instruments=["trumpet", "trombone"],
            num_measures=4,
        )

        # Act
        manager.set_barline(measure=4, barline_type="double")

        # Assert
        score = manager._score  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        assert score is not None
        for part in score.parts:
            target_measure = part.measure(4)
            assert target_measure is not None
            assert isinstance(target_measure, stream.Measure)
            assert target_measure.rightBarline is not None
            assert isinstance(target_measure.rightBarline, bar.Barline)

    def test_set_barline_rejects_invalid_type(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager_with_score.set_barline(measure=1, barline_type="nonexistent")

        # Assert
        assert "error" in result
        assert "Unknown barline type" in result["error"]


class TestAddChordSymbol:
    def test_add_chord_symbol_returns_success(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager_with_score.add_chord_symbol(
            part_index_or_name="0",
            measure=1,
            beat=1.0,
            symbol="Cmaj7",
        )

        # Assert
        assert result["success"] is True

    def test_add_chord_symbol_at_correct_beat_offset(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        manager_with_score.add_chord_symbol(
            part_index_or_name="0",
            measure=1,
            beat=3.0,
            symbol="G7",
        )

        # Assert
        score = manager_with_score._score  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        assert score is not None
        part = list(score.parts)[0]
        target_measure = part.measure(1)
        assert target_measure is not None
        chords = list(target_measure.getElementsByClass(harmony.ChordSymbol))
        assert len(chords) == 1
        # beat 3 means offset 2.0
        assert chords[0].offset == 2.0


class TestAddTempoMarking:
    def test_add_tempo_marking_returns_success(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager_with_score.add_tempo_marking(measure=1, bpm=140)

        # Assert
        assert result["success"] is True

    def test_add_tempo_marking_with_text(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager_with_score.add_tempo_marking(measure=2, bpm=80, text="Ballad")

        # Assert
        assert result["success"] is True
        assert "Ballad" in result["message"]

    def test_add_tempo_marking_adds_metronome_mark(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        manager_with_score.add_tempo_marking(measure=2, bpm=160)

        # Assert
        score = manager_with_score._score  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
        assert score is not None
        first_part = list(score.parts)[0]
        target_measure = first_part.measure(2)
        assert target_measure is not None
        marks = list(target_measure.getElementsByClass(tempo.MetronomeMark))
        assert len(marks) == 1
        assert marks[0].number == 160


class TestGetScoreInfo:
    def test_get_score_info_returns_correct_structure(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager_with_score.get_score_info()

        # Assert
        assert result["success"] is True
        assert "title" in result
        assert result["num_parts"] == 1
        assert result["num_measures"] == 4
        assert isinstance(result["parts"], list)

    def test_get_score_info_part_has_expected_fields(
        self, manager_with_score: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager_with_score.get_score_info()

        # Assert
        part_info: dict[str, Any] = result["parts"][0]
        assert "index" in part_info
        assert "name" in part_info
        assert "instrument" in part_info
        assert "transposition" in part_info


class TestExportMusicxml:
    def test_export_creates_file(
        self, manager_with_score: ScoreManager, tmp_path: Path
    ) -> None:
        # Arrange
        filepath = str(tmp_path / "test_export.musicxml")

        # Act
        result = manager_with_score.export_musicxml(filepath)

        # Assert
        assert result["success"] is True
        assert Path(filepath).exists()
        assert result["filepath"] == filepath

    def test_export_returns_filepath_in_result(
        self, manager_with_score: ScoreManager, tmp_path: Path
    ) -> None:
        # Arrange
        filepath = str(tmp_path / "output.musicxml")

        # Act
        result = manager_with_score.export_musicxml(filepath)

        # Assert
        assert result["filepath"] == filepath


class TestClear:
    def test_clear_removes_score(self, manager_with_score: ScoreManager) -> None:
        # Arrange
        assert manager_with_score.has_score

        # Act
        result = manager_with_score.clear()

        # Assert
        assert result["success"] is True
        assert not manager_with_score.has_score


class TestOperationsOnEmptyScore:
    def test_add_notes_on_empty_returns_error(self, manager: ScoreManager) -> None:
        # Arrange / Act
        result = manager.add_notes(
            part_index_or_name="0",
            measure=1,
            notes=[{"pitch": "C5", "duration": "quarter"}],
        )

        # Assert
        assert "error" in result

    def test_add_rehearsal_mark_on_empty_returns_error(
        self, manager: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager.add_rehearsal_mark(measure=1, label="A")

        # Assert
        assert "error" in result

    def test_set_barline_on_empty_returns_error(self, manager: ScoreManager) -> None:
        # Arrange / Act
        result = manager.set_barline(measure=1, barline_type="double")

        # Assert
        assert "error" in result

    def test_add_chord_symbol_on_empty_returns_error(
        self, manager: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager.add_chord_symbol(
            part_index_or_name="0",
            measure=1,
            beat=1.0,
            symbol="Cmaj7",
        )

        # Assert
        assert "error" in result

    def test_add_tempo_marking_on_empty_returns_error(
        self, manager: ScoreManager
    ) -> None:
        # Arrange / Act
        result = manager.add_tempo_marking(measure=1, bpm=120)

        # Assert
        assert "error" in result

    def test_get_score_info_on_empty_returns_error(self, manager: ScoreManager) -> None:
        # Arrange / Act
        result = manager.get_score_info()

        # Assert
        assert "error" in result

    def test_export_on_empty_returns_error(
        self, manager: ScoreManager, tmp_path: Path
    ) -> None:
        # Arrange
        filepath = str(tmp_path / "empty.musicxml")

        # Act
        result = manager.export_musicxml(filepath)

        # Assert
        assert "error" in result
