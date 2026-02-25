"""Instrument name resolution — map friendly names to music21 instruments."""

import re

from music21 import instrument

__all__ = ["resolve_instrument", "INSTRUMENT_ALIASES"]

# Map friendly names (lowercase) to music21 instrument classes.
# Includes common aliases and abbreviations.
INSTRUMENT_ALIASES: dict[str, type[instrument.Instrument]] = {
    # Woodwinds
    "flute": instrument.Flute,
    "piccolo": instrument.Piccolo,
    "oboe": instrument.Oboe,
    "english horn": instrument.EnglishHorn,
    "clarinet": instrument.Clarinet,
    "bb clarinet": instrument.Clarinet,
    "bass clarinet": instrument.BassClarinet,
    "bassoon": instrument.Bassoon,
    "soprano sax": instrument.SopranoSaxophone,
    "soprano saxophone": instrument.SopranoSaxophone,
    "alto sax": instrument.AltoSaxophone,
    "alto saxophone": instrument.AltoSaxophone,
    "tenor sax": instrument.TenorSaxophone,
    "tenor saxophone": instrument.TenorSaxophone,
    "baritone sax": instrument.BaritoneSaxophone,
    "baritone saxophone": instrument.BaritoneSaxophone,
    "bari sax": instrument.BaritoneSaxophone,
    # Brass
    "trumpet": instrument.Trumpet,
    "bb trumpet": instrument.Trumpet,
    "horn": instrument.Horn,
    "french horn": instrument.Horn,
    "trombone": instrument.Trombone,
    "bass trombone": instrument.BassTrombone,
    "tuba": instrument.Tuba,
    # Strings
    "violin": instrument.Violin,
    "viola": instrument.Viola,
    "cello": instrument.Violoncello,
    "violoncello": instrument.Violoncello,
    "double bass": instrument.Contrabass,
    "contrabass": instrument.Contrabass,
    "bass": instrument.Contrabass,
    "string bass": instrument.Contrabass,
    # Keyboards
    "piano": instrument.Piano,
    "organ": instrument.Organ,
    "harpsichord": instrument.Harpsichord,
    "electric piano": instrument.ElectricPiano,
    # Guitar
    "guitar": instrument.AcousticGuitar,
    "acoustic guitar": instrument.AcousticGuitar,
    "electric guitar": instrument.ElectricGuitar,
    "electric bass": instrument.ElectricBass,
    "bass guitar": instrument.ElectricBass,
    # Percussion
    "drums": instrument.UnpitchedPercussion,
    "drum set": instrument.UnpitchedPercussion,
    "percussion": instrument.UnpitchedPercussion,
    # Voices
    "soprano": instrument.Soprano,
    "alto": instrument.Alto,
    "tenor": instrument.Tenor,
    "baritone": instrument.Baritone,
    "voice": instrument.Soprano,
}


def resolve_instrument(name: str) -> instrument.Instrument:
    """Resolve a friendly instrument name to a music21 Instrument.

    Handles numbered variants like "trumpet 1", "alto sax 2",
    "violin-3". The number becomes the part name suffix.

    Args:
        name: Instrument name, optionally with a number suffix.
            Examples: "trumpet", "alto sax 1", "violin-2", "piano"

    Returns:
        A music21 Instrument instance with appropriate part name.

    Raises:
        ValueError: If the instrument name is not recognized.
    """
    original_name = name.strip()
    normalized = original_name.lower().strip()

    # Extract optional trailing number: "trumpet 1", "alto sax-2", "violin 3"
    number_match = re.match(r"^(.+?)[\s\-]+(\d+)$", normalized)
    part_number: int | None = None
    if number_match:
        normalized = number_match.group(1).strip()
        part_number = int(number_match.group(2))

    instrument_class = INSTRUMENT_ALIASES.get(normalized)
    if instrument_class is None:
        available = ", ".join(sorted(set(INSTRUMENT_ALIASES.keys())))
        msg = f"Unknown instrument: '{original_name}'. Available: {available}"
        raise ValueError(msg)

    inst = instrument_class()

    # Set a descriptive part name with the number if provided.
    base_name = inst.instrumentName or normalized.title()
    if part_number is not None:
        inst.partName = f"{base_name} {part_number}"
    else:
        inst.partName = base_name

    return inst
