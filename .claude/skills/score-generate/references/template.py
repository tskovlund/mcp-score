#!/usr/bin/env python3
"""Generate a music score using music21 — starter template.

Usage:
    mcp-score run /tmp/generate_score.py
"""

from pathlib import Path

from music21 import (  # noqa: F401
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
OUTPUT = Path.home() / "Desktop" / f"{TITLE}.musicxml"

# ── Create score ──────────────────────────────────────────────
score = stream.Score()
score.metadata = metadata.Metadata()
score.metadata.title = TITLE
# score.metadata.composer = "Composer Name"
# score.metadata.movementName = "Subtitle"  # shows below title
# score.metadata.addContributor(
#     metadata.Contributor(role="arranger", name="Arranger Name")
# )
# score.metadata.copyright = metadata.Copyright("© 2026 Author Name")

# ── Create parts ──────────────────────────────────────────────
# See instruments.md for full instrument list.
trumpet_part = stream.Part()
trumpet = instrument.Trumpet()
trumpet.partName = "Trumpet 1"
trumpet_part.insert(0, trumpet)

# ── Build measures ────────────────────────────────────────────
NUM_MEASURES = 32
KEY_SIG = key.Key("B-")  # Bb major
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


def add_chord(part: stream.Part, measure_num: int, beat: float, symbol: str) -> None:
    """Add a chord symbol to a specific beat in a measure."""
    target = part.measure(measure_num)
    offset = beat - 1.0
    target.insert(offset, harmony.ChordSymbol(symbol))


# Example: 12-bar blues changes
# add_chord(trumpet_part, 1, 1, "B-7")
# add_chord(trumpet_part, 5, 1, "E-7")


# ── Rehearsal marks ───────────────────────────────────────────
def add_rehearsal(part: stream.Part, measure_num: int, label: str) -> None:
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
score.write("musicxml", fp=str(OUTPUT))
print(f"Exported: {OUTPUT}")
