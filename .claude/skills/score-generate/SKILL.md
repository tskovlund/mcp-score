---
name: score-generate
description: >
  Generate music scores as MusicXML using music21 Python scripts. Use when the
  user says "create a score", "generate a chart", "write a lead sheet",
  "make an arrangement", "write out parts", or describes a musical piece to notate.
  Do NOT use for live MuseScore manipulation (use the mcp-score MCP bridge tools).
allowed-tools: [Bash, Write, Read]
metadata:
  author: tskovlund
  version: "1.0"
---

# Score Generation

Generate music scores by writing and executing music21 Python scripts that export MusicXML.

## Instructions

1. **Understand the request** — identify: instrumentation, key, time signature, tempo, form/structure, chord progressions, specific notation elements.
2. **Write a complete Python script** using music21 that builds the entire score. Save to `/tmp/generate_score.py`.
3. **Execute** the script:
   ```bash
   /Users/thomas/repos/mcp-score/.venv/bin/python /tmp/generate_score.py
   ```
4. **Report** the output file path. The user opens it in MuseScore.

Default output location: `~/Desktop/<Title>.musicxml`

## Critical Conventions

### Chord Symbols — Flat Notation

music21 uses `-` for flats in chord symbol roots, NOT `b`. This is the most common source of bugs:

```python
# WRONG — "Bb7" is parsed as B with b7 extension
harmony.ChordSymbol("Bb7")   # produces B(b7), NOT Bb7!

# CORRECT — use '-' for flats in the root
harmony.ChordSymbol("B-7")   # Bb dominant 7th
harmony.ChordSymbol("E-7")   # Eb dominant 7th
harmony.ChordSymbol("A-maj7") # Ab major 7th
harmony.ChordSymbol("D-9")   # Db dominant 9th

# Sharps use '#' as expected
harmony.ChordSymbol("F#m7")  # F# minor 7th
harmony.ChordSymbol("C#7")   # C# dominant 7th
```

### Chord Repetition

When the same chord spans multiple consecutive bars, do NOT notate it every bar:

- **Notate at every chord change** — always.
- **Re-notate at section boundaries** — rehearsal marks, repeat signs.
- **For 4+ bars of the same chord** — re-notate every 4 bars.
- **Never write the same chord on consecutive bars** unless it's a section boundary.

Example — 12-bar blues in Bb, each `|` is a bar:
```
Bb7 |    |    |    | Eb7 |    | Bb7 |    | F7  | Eb7 | Bb7 | F7
```
Chord symbols appear on bars 1, 5, 6, 7, 9, 10, 11, 12 — NOT every bar.

For an 8-bar stretch of the same chord, notate at bar 1 and bar 5.

### Score Metadata

Always set title (and composer if known) using `metadata.Metadata`:

```python
from music21 import metadata

score.metadata = metadata.Metadata()
score.metadata.title = "Score Title"
score.metadata.composer = "Composer Name"  # if provided
```

Do NOT use `stream.Score().metadata` — that creates a throwaway score.

### Barlines Including Repeats

```python
from music21 import bar

# Repeat signs — use bar.Repeat, NOT bar.Barline
measure.leftBarline = bar.Repeat(direction='start')
measure.rightBarline = bar.Repeat(direction='end')

# Standard barlines
measure.rightBarline = bar.Barline('double')
measure.rightBarline = bar.Barline('final')
```

### Key Signatures with Flats

Same as chord symbols — use `-` for flats:

```python
from music21 import key

key.Key('B-')   # Bb major
key.Key('e-')   # Eb minor (lowercase = minor)
key.Key('F')    # F major
key.Key('f#')   # F# minor
```

## Score Building Template

```python
#!/usr/bin/env python3
"""Generate a music score using music21."""

from music21 import (
    bar,
    expressions,
    harmony,
    instrument,
    key,
    metadata,
    meter,
    note,
    stream,
    tempo,
)

TITLE = "Score Title"
OUTPUT = f"/Users/thomas/Desktop/{TITLE}.musicxml"

# ── Create score ──────────────────────────────────────────────
score = stream.Score()
score.metadata = metadata.Metadata()
score.metadata.title = TITLE

# ── Create parts ──────────────────────────────────────────────
# See references/instruments.md for full instrument list.
trumpet_part = stream.Part()
trumpet = instrument.Trumpet()
trumpet.partName = "Trumpet 1"
trumpet_part.insert(0, trumpet)

# ── Build measures ────────────────────────────────────────────
NUM_MEASURES = 32
KEY_SIG = key.Key("B-")       # Bb major
TIME_SIG = meter.TimeSignature("4/4")
TEMPO_BPM = 120

for m_num in range(1, NUM_MEASURES + 1):
    m = stream.Measure(number=m_num)

    # Key and time signature on first measure only.
    if m_num == 1:
        m.insert(0.0, KEY_SIG)
        m.insert(0.0, TIME_SIG)

    # Fill with whole rest (adjust quarterLength to match time sig).
    rest = note.Rest()
    rest.quarterLength = TIME_SIG.barDuration.quarterLength
    m.append(rest)

    trumpet_part.append(m)

# ── Add parts to score ────────────────────────────────────────
score.insert(0, trumpet_part)

# ── Tempo marking on first measure of first part ──────────────
first_part = list(score.parts)[0]
first_measure = list(first_part.getElementsByClass(stream.Measure))[0]
first_measure.insert(0.0, tempo.MetronomeMark(number=TEMPO_BPM))

# ── Chord symbols (on first part, at beat offsets) ────────────
# Beat 1 = offset 0.0, beat 3 = offset 2.0, etc.
def add_chord(part, measure_num, beat, symbol):
    """Add a chord symbol to a specific beat in a measure."""
    target = part.measure(measure_num)
    offset = beat - 1.0
    target.insert(offset, harmony.ChordSymbol(symbol))

# Example: 12-bar blues changes
# add_chord(trumpet_part, 1, 1, "B-7")
# add_chord(trumpet_part, 5, 1, "E-7")

# ── Rehearsal marks ───────────────────────────────────────────
def add_rehearsal(part, measure_num, label):
    """Add a rehearsal mark to a measure."""
    target = part.measure(measure_num)
    target.insert(0.0, expressions.RehearsalMark(label))

# add_rehearsal(trumpet_part, 1, "A")

# ── Barlines ─────────────────────────────────────────────────
# Double barline at section boundaries:
# part.measure(12).rightBarline = bar.Barline('double')
#
# Repeat signs:
# part.measure(1).leftBarline = bar.Repeat(direction='start')
# part.measure(12).rightBarline = bar.Repeat(direction='end')
#
# Final barline on last measure:
# part.measure(NUM_MEASURES).rightBarline = bar.Barline('final')

# ── Notes (replacing rests) ──────────────────────────────────
# To write notes in a measure, clear existing content first:
# m = trumpet_part.measure(1)
# for el in list(m.notesAndRests):
#     m.remove(el)
# m.insert(0.0, note.Note("B-4", quarterLength=2.0))   # Bb4 half note
# m.insert(2.0, note.Note("C5", quarterLength=2.0))     # C5 half note

# ── Export ────────────────────────────────────────────────────
score.write("musicxml", fp=OUTPUT)
print(f"Exported: {OUTPUT}")
```

## Transposing Instruments

music21 handles transposition automatically when using the correct instrument class.
A `Trumpet()` is in Bb — music21 will write concert pitch internally and produce
the correct transposed part in MusicXML. Write notes at **concert pitch** in the script.

For the full instrument list with transposition details, read:
`/Users/thomas/repos/mcp-score/.claude/skills/score-generate/references/instruments.md`

## Examples

### "Write me a 12-bar blues lead sheet in Bb"

Script creates:
- Single part (Piano or lead instrument)
- Key: B- major, Time: 4/4, Tempo: ~120 BPM
- 12 measures with whole rests
- Chord symbols at change points only: B-7 (m1), E-7 (m5), B-7 (m7), F7 (m9), E-7 (m10), B-7 (m11), F7 (m12)
- Final barline on m12
- Export to `~/Desktop/Blues in Bb.musicxml`

### "Create a big band chart — 32-bar AABA, Bb major, slow blues at 66 BPM"

Script creates:
- 17 parts: Alto Sax 1-2, Tenor Sax 1-2, Bari Sax, Trumpet 1-4, Trombone 1-3, Bass Trombone, Piano, Guitar, Bass, Drums
- Uses correct instrument classes (AltoSaxophone, TenorSaxophone, etc.)
- Rehearsal marks: A (m1), A2 (m9), B (m17), A3 (m25)
- Chord symbols on first part only, at change points
- Double barlines at section boundaries
- Repeat signs where the chart calls for them
- Tempo: MetronomeMark(number=66, text="Slow Blues")
- Export to `~/Desktop/Big Band Chart.musicxml`

## Troubleshooting

**Flat chords showing wrong extension (e.g. B(b7) instead of Bb7)**
Cause: Using `"Bb7"` instead of `"B-7"`. Fix: always use `-` for flats.

**Title not showing in MuseScore**
Cause: Metadata not set properly. Fix: use `metadata.Metadata()` directly.

**Repeat barlines not appearing**
Cause: Using `bar.Barline('repeat-start')`. Fix: use `bar.Repeat(direction='start')`.

**music21 import error**
Cause: Wrong Python. Fix: use `/Users/thomas/repos/mcp-score/.venv/bin/python`.

**Notes sound wrong for transposing instruments**
Cause: Writing transposed pitch instead of concert pitch. Fix: always write concert pitch — music21 transposes automatically based on the instrument class.
