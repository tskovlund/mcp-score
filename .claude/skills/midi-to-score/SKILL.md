---
name: midi-to-score
description: >
  Convert a MIDI file to a clean MusicXML score using music21. Use when the
  user provides a .mid file and wants a notated score (piano grand staff,
  lead sheet, etc.). Complements score-generate — use this for MIDI input,
  score-generate for scores written from scratch.
allowed-tools: [Bash, Write, Read]
metadata:
  author: hnomichith
  version: "1.1"
---

# MIDI to Score Conversion

Convert a MIDI file into a clean MusicXML score via a music21 Python script.

**Dependencies — read these skills first:**
- `work-on-score` — project structure, metadata.md format and lifecycle
- `score-generate` — notation conventions, grand staff construction, barlines, output naming

This skill covers only what is specific to MIDI input.

## Workflow

### Step 1 — Gather musical context

Before inspecting the MIDI, gather context about the piece and the desired output.
This is separate from the structural inspection — it's about *what* to produce, not *what's in the file*.

**Check for a `metadata.md` file in the project directory first.** If it exists, read it.

If no metadata file exists, ask the user:
- **Output format** — grand staff piano, lead sheet, specific instrumentation?
- **Tempo** — fix to a single value, or follow the MIDI?
- **Any known facts about the piece** — style, era, original instrumentation, arrangement notes

The more context up front, the better the result. Don't skip this step.

Modify the metadata file to add the user answers under the `MIDI file description` section.

### Step 2 — Inspect the MIDI

Before writing anything, run an inspection script to understand the file structure:

```python
from music21 import converter, chord, note
from collections import Counter

raw = converter.parse("/path/to/file.mid")

print("Parts:", len(raw.parts))
for i, part in enumerate(raw.parts):
    instr = part.getInstrument()
    notes = list(part.flatten().notes)
    print(f"  Part {i}: {instr} | measures={len(part.getElementsByClass('Measure'))} | notes={len(notes)}")

print("Time signatures:", [str(ts) for ts in raw.flatten().getElementsByClass('TimeSignature')])
print("Key signatures:", [str(ks) for ks in raw.flatten().getElementsByClass('KeySignature')])
print("Tempos:", [str(t) for t in raw.flatten().getElementsByClass('MetronomeMark')])

# Note range and octave distribution
all_notes = [n for p in raw.parts for n in p.flatten().notes if hasattr(n, 'pitch')]
if all_notes:
    midi_vals = [n.pitch.midi for n in all_notes]
    print(f"Note range: midi {min(midi_vals)}–{max(midi_vals)}")
    dist = Counter(n.pitch.octave for n in all_notes)
    for oct in sorted(dist): print(f"  Octave {oct}: {dist[oct]} notes")

# Voice structure — check first few measures (critical, see pitfall below)
for m in raw.parts[0].getElementsByClass('Measure')[:3]:
    print(f"Measure {m.number} top-level types: {[type(el).__name__ for el in m]}")

# Chord vs single note count
chords  = [el for p in raw.parts for el in p.flatten() if isinstance(el, chord.Chord)]
singles = [el for p in raw.parts for el in p.flatten() if isinstance(el, note.Note)]
print(f"Single notes: {len(singles)}, Chords: {len(chords)}")
```

Save to `/tmp/inspect_midi.py` and run: `python /tmp/inspect_midi.py`

From the inspection, determine:
- How many parts to produce (one per MIDI track, or merged)
- Whether to split into a grand staff (treble + bass)
- The split pitch (default C4, MIDI 60 — adjust based on octave distribution)
- Whether to clean up humanized tempo fluctuations
- Which key/time signatures to carry over

Write down your findings in the metadata file, under the `MIDI inspection` section.

### Step 2b — Map findings to pitfalls before writing anything

After inspection, explicitly check each finding against the known pitfalls below and
decide how to handle it. Do not proceed to Step 3 until each item is resolved.

| Finding | Pitfall to address |
|---|---|
| Measures 2+ contain `Voice` objects | Must use `flatten().notesAndRests` when iterating notes — never bare `for el in measure` |
| Multiple key signatures | Carry **all** of them; count in script must match inspection count |
| Humanized tempo (multiple near-identical MetronomeMark) | Override with a single fixed tempo; do not copy from source |
| Chords spanning both staves at the split point | Split pitches per chord; don't drop either side |

If inspection reveals Voice objects, write the confirmation explicitly before
continuing: *"Measures 2+ use Voice objects — I will use `flatten().notesAndRests`."*
This forces the constraint into the generation step rather than leaving it implicit.

### Step 3 — Write and run the generation script

Save to `/tmp/generate_score.py` and run: `python /tmp/generate_score.py`

---

## Critical MIDI Pitfalls

### Voice objects hide notes in polyphonic MIDI

When music21 parses a MIDI file with complex rhythms or multiple simultaneous
voices, it wraps notes inside `Voice` objects within measures — often from
measure 2 onward. Iterating `for el in measure` only sees the `Voice` containers.

**Wrong:**
```python
for el in src_measure:
    if isinstance(el, note.Note): ...  # misses notes inside Voice objects!
```

**Correct — always flatten the measure first:**
```python
for el in src_measure.flatten().notesAndRests:
    if isinstance(el, note.Note): ...  # sees all notes regardless of Voice nesting
```

**Exception:** key signatures and time signatures live at the top level of the
measure, not inside voices. Fetch them separately before flattening:
```python
for ks in src_measure.getElementsByClass((key.KeySignature, key.Key)):
    ...
for ts in src_measure.getElementsByClass(meter.TimeSignature):
    ...
```

### Humanized tempo fluctuations

MIDI recordings often encode subtle tempo variations (e.g. 144, 145.96, 147.48…),
producing dozens of near-identical `MetronomeMark` objects. Ignore all of them
and set a single clean tempo manually on the first measure:

```python
# Don't copy MetronomeMark from source — set once:
first_measure.insert(0.0, tempo.MetronomeMark(number=144))
```

---

## Grand Staff Split Pattern

When splitting a single MIDI part into treble and bass staves, split notes at
the chosen MIDI threshold (typically C4 = 60). For chords that span both sides,
split the pitches:

```python
SPLIT_MIDI = 60  # C4 — adjust based on octave distribution

# Single note
elif isinstance(el, note.Note):
    target = t_m if el.pitch.midi >= SPLIT_MIDI else b_m
    target.insert(el.offset, copy.deepcopy(el))

# Chord spanning both staves
elif isinstance(el, chord.Chord):
    treble_pitches = [p for p in el.pitches if p.midi >= SPLIT_MIDI]
    bass_pitches   = [p for p in el.pitches if p.midi < SPLIT_MIDI]
    for pitches, target in [(treble_pitches, t_m), (bass_pitches, b_m)]:
        if not pitches:
            continue
        if len(pitches) == 1:
            n = note.Note(pitches[0])
            n.duration = copy.deepcopy(el.duration)
            target.insert(el.offset, n)
        else:
            c = chord.Chord(pitches)
            c.duration = copy.deepcopy(el.duration)
            target.insert(el.offset, c)

# Rests — don't copy; music21 fills gaps automatically on export
```

For `PartStaff`, `StaffGroup`, clef assignment, and barline copying, follow
the grand staff patterns in `score-generate`.
