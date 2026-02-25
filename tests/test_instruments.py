"""Tests for instrument name resolution."""

import pytest
from music21 import instrument

from mcp_score.instruments import INSTRUMENT_ALIASES, resolve_instrument


class TestResolveInstrumentKnownNames:
    def test_resolve_flute_returns_flute(self) -> None:
        # Arrange
        name = "flute"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.Flute)

    def test_resolve_trumpet_returns_trumpet(self) -> None:
        # Arrange
        name = "trumpet"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.Trumpet)

    def test_resolve_piano_returns_piano(self) -> None:
        # Arrange
        name = "piano"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.Piano)

    def test_resolve_alto_sax_returns_alto_saxophone(self) -> None:
        # Arrange
        name = "alto sax"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.AltoSaxophone)

    def test_resolve_violin_returns_violin(self) -> None:
        # Arrange
        name = "violin"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.Violin)

    def test_resolve_cello_returns_violoncello(self) -> None:
        # Arrange
        name = "cello"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.Violoncello)

    def test_resolve_french_horn_returns_horn(self) -> None:
        # Arrange
        name = "french horn"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.Horn)


class TestResolveInstrumentCaseInsensitive:
    def test_resolve_uppercase_name(self) -> None:
        # Arrange
        name = "TRUMPET"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.Trumpet)

    def test_resolve_mixed_case_name(self) -> None:
        # Arrange
        name = "Alto Sax"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.AltoSaxophone)


class TestResolveInstrumentNumberedVariants:
    def test_resolve_trumpet_1_with_space(self) -> None:
        # Arrange
        name = "trumpet 1"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.Trumpet)
        assert result.partName == "Trumpet 1"

    def test_resolve_alto_sax_2_with_hyphen(self) -> None:
        # Arrange
        name = "alto sax-2"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.AltoSaxophone)
        assert result.partName == "Alto Saxophone 2"

    def test_resolve_violin_3_with_space(self) -> None:
        # Arrange
        name = "violin 3"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert isinstance(result, instrument.Violin)
        assert result.partName == "Violin 3"


class TestResolveInstrumentPartName:
    def test_resolve_sets_part_name_without_number(self) -> None:
        # Arrange
        name = "flute"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert result.partName == "Flute"

    def test_resolve_piano_sets_part_name(self) -> None:
        # Arrange
        name = "piano"

        # Act
        result = resolve_instrument(name)

        # Assert
        assert result.partName == "Piano"


class TestResolveInstrumentUnknown:
    def test_resolve_unknown_raises_value_error(self) -> None:
        # Arrange
        name = "kazoo"

        # Act / Assert
        with pytest.raises(ValueError, match="Unknown instrument: 'kazoo'"):
            resolve_instrument(name)

    def test_resolve_empty_string_raises_value_error(self) -> None:
        # Arrange
        name = ""

        # Act / Assert
        with pytest.raises(ValueError, match="Unknown instrument"):
            resolve_instrument(name)


class TestInstrumentAliases:
    def test_aliases_contains_woodwinds(self) -> None:
        # Arrange / Act / Assert
        assert "flute" in INSTRUMENT_ALIASES
        assert "clarinet" in INSTRUMENT_ALIASES
        assert "oboe" in INSTRUMENT_ALIASES
        assert "bassoon" in INSTRUMENT_ALIASES

    def test_aliases_contains_brass(self) -> None:
        # Arrange / Act / Assert
        assert "trumpet" in INSTRUMENT_ALIASES
        assert "trombone" in INSTRUMENT_ALIASES
        assert "tuba" in INSTRUMENT_ALIASES
        assert "french horn" in INSTRUMENT_ALIASES

    def test_aliases_contains_strings(self) -> None:
        # Arrange / Act / Assert
        assert "violin" in INSTRUMENT_ALIASES
        assert "viola" in INSTRUMENT_ALIASES
        assert "cello" in INSTRUMENT_ALIASES
        assert "contrabass" in INSTRUMENT_ALIASES

    def test_aliases_contains_keyboards(self) -> None:
        # Arrange / Act / Assert
        assert "piano" in INSTRUMENT_ALIASES
        assert "organ" in INSTRUMENT_ALIASES

    def test_aliases_contains_saxophone_variants(self) -> None:
        # Arrange / Act / Assert
        assert "alto sax" in INSTRUMENT_ALIASES
        assert "alto saxophone" in INSTRUMENT_ALIASES
        assert "tenor sax" in INSTRUMENT_ALIASES
        assert "bari sax" in INSTRUMENT_ALIASES

    def test_aliases_map_to_correct_classes(self) -> None:
        # Arrange / Act / Assert
        assert INSTRUMENT_ALIASES["bb trumpet"] is instrument.Trumpet
        assert INSTRUMENT_ALIASES["bb clarinet"] is instrument.Clarinet
        assert INSTRUMENT_ALIASES["double bass"] is instrument.Contrabass
        assert INSTRUMENT_ALIASES["string bass"] is instrument.Contrabass
