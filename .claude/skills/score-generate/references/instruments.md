# Instrument Reference

music21 instrument classes and their properties. Use these exact class names.

## Woodwinds

| Name | Class | Transposition |
|---|---|---|
| Piccolo | `instrument.Piccolo()` | Octave up |
| Flute | `instrument.Flute()` | Concert pitch |
| Oboe | `instrument.Oboe()` | Concert pitch |
| English Horn | `instrument.EnglishHorn()` | F (down P5) |
| Clarinet (Bb) | `instrument.Clarinet()` | Bb (down M2) |
| Bass Clarinet | `instrument.BassClarinet()` | Bb (down M9) |
| Bassoon | `instrument.Bassoon()` | Concert pitch |
| Soprano Sax | `instrument.SopranoSaxophone()` | Bb (down M2) |
| Alto Sax | `instrument.AltoSaxophone()` | Eb (down M6) |
| Tenor Sax | `instrument.TenorSaxophone()` | Bb (down M9) |
| Baritone Sax | `instrument.BaritoneSaxophone()` | Eb (down M13) |

## Brass

| Name | Class | Transposition |
|---|---|---|
| Trumpet (Bb) | `instrument.Trumpet()` | Bb (down M2) |
| French Horn (F) | `instrument.Horn()` | F (down P5) |
| Trombone | `instrument.Trombone()` | Concert pitch |
| Bass Trombone | `instrument.BassTrombone()` | Concert pitch |
| Tuba | `instrument.Tuba()` | Concert pitch |

## Strings

| Name | Class | Transposition |
|---|---|---|
| Violin | `instrument.Violin()` | Concert pitch |
| Viola | `instrument.Viola()` | Concert pitch (alto clef) |
| Cello | `instrument.Violoncello()` | Concert pitch |
| Double Bass | `instrument.Contrabass()` | Octave down |

## Keyboards

| Name | Class | Transposition |
|---|---|---|
| Piano | `instrument.Piano()` | Concert pitch |
| Organ | `instrument.Organ()` | Concert pitch |
| Electric Piano | `instrument.ElectricPiano()` | Concert pitch |
| Harpsichord | `instrument.Harpsichord()` | Concert pitch |

## Guitar

| Name | Class | Transposition |
|---|---|---|
| Acoustic Guitar | `instrument.AcousticGuitar()` | Octave down |
| Electric Guitar | `instrument.ElectricGuitar()` | Octave down |
| Electric Bass | `instrument.ElectricBass()` | Octave down |

## Percussion

| Name | Class | Notes |
|---|---|---|
| Drums / Drum Set | `instrument.UnpitchedPercussion()` | Unpitched |

## Voices

| Name | Class | Range |
|---|---|---|
| Soprano | `instrument.Soprano()` | C4-C6 |
| Alto | `instrument.Alto()` | F3-F5 |
| Tenor | `instrument.Tenor()` | C3-C5 |
| Baritone | `instrument.Baritone()` | A2-A4 |

## Numbered Parts

For multiple instruments of the same type, set `partName` with a number:

```python
trumpet1 = instrument.Trumpet()
trumpet1.partName = "Trumpet 1"

trumpet2 = instrument.Trumpet()
trumpet2.partName = "Trumpet 2"
```

## Common Big Band Setup (17 parts)

```python
instruments_list = [
    ("Alto Sax 1", instrument.AltoSaxophone),
    ("Alto Sax 2", instrument.AltoSaxophone),
    ("Tenor Sax 1", instrument.TenorSaxophone),
    ("Tenor Sax 2", instrument.TenorSaxophone),
    ("Bari Sax", instrument.BaritoneSaxophone),
    ("Trumpet 1", instrument.Trumpet),
    ("Trumpet 2", instrument.Trumpet),
    ("Trumpet 3", instrument.Trumpet),
    ("Trumpet 4", instrument.Trumpet),
    ("Trombone 1", instrument.Trombone),
    ("Trombone 2", instrument.Trombone),
    ("Trombone 3", instrument.Trombone),
    ("Bass Trombone", instrument.BassTrombone),
    ("Piano", instrument.Piano),
    ("Guitar", instrument.AcousticGuitar),
    ("Bass", instrument.Contrabass),
    ("Drums", instrument.UnpitchedPercussion),
]

for part_name, inst_class in instruments_list:
    part = stream.Part()
    inst = inst_class()
    inst.partName = part_name
    part.partName = part_name
    part.insert(0, inst)
    # ... add measures ...
    score.insert(0, part)
```
