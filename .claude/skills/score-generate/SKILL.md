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
  version: "1.3"
---

# Score Generation

Generate music scores by writing and executing music21 Python scripts that export MusicXML.

**Dependency: read the `work-on-score` skill first** — it defines the project structure,
`metadata.md` format, and output location convention. After generating, update the
`## Score description` section of the project's `metadata.md`.

## Instructions

1. **Read `metadata.md`** if working inside a score project — it may already answer questions about instrumentation, tempo, and arrangement intent.
2. **Understand the request** — identify: instrumentation, key, time signature, tempo, form/structure, chord progressions, specific notation elements.
3. **Gather missing metadata** — if the user hasn't specified title, composer, arranger, or other relevant details, **ask them** before generating. Only skip asking if the user explicitly says to use defaults or not to ask. Relevant metadata includes:
   - **Title** (required — ask if not provided)
   - **Composer** (ask if not provided)
   - **Arranger** (ask if applicable, e.g. arrangements, charts)
   - **Subtitle** (ask if the piece has a descriptive subtitle, genre, or dedication)
   - **Copyright** (ask if the user wants a copyright notice)
4. **Assess size** — for large scores (many parts × many bars), use the strategies below to avoid losing work to session rate limits.
5. **Write the script to the project directory** (not `/tmp/`) so it survives a session ending:
   - Small scores: `<project-dir>/generate_score.py`
   - Multi-section scores: `<project-dir>/generate_section1.py`, `generate_section2.py`, etc.
6. **Confirm the script is complete** before running. If the session hits a limit mid-write, the partial file is on disk — start a new session, read the file, and continue from where it left off.
7. **Execute** the script:
   ```bash
   mcp-score run <project-dir>/generate_score.py
   ```
8. **Report** the output file path. The user opens it in MuseScore.

## Large score strategy

A large score (e.g. full concert band × 4 minutes) produces a script too long to write in a single session. Two complementary strategies:

### Generate one section at a time

Break the piece into sections and generate a separate MusicXML file per section:

```
generate_section1.py  →  section1-opening.xml
generate_section2.py  →  section2-battle.xml
...
```

Each section script includes its **outgoing transition bars** (the last few bars that bridge into the next section), so files are self-contained and can be paste-joined in MuseScore without hard cuts.

Document the transitions in `metadata.md` before generating — each section script can then reference the transition design.

Final assembly: import all section files into MuseScore and copy-paste into a single combined score.

**Rule of thumb:** if the piece has more than ~20 parts OR more than ~60 bars, split by section.

### Write to disk before running

Always write the script to a named file in the project directory rather than to `/tmp/` or inline. This means:
- The script is saved to disk as it is written — even a partial file survives a session ending.
- If generation is interrupted, start a new session, read the file with `Read`, and ask Claude to complete it from where it left off.
- Once the script looks complete, run it with `mcp-score run`.

Never write large scripts directly to `/tmp/generate_score.py` for large pieces — that file is ephemeral and lost if the session ends.

Default output location: `~/Desktop/<Title>.musicxml`
If the output location already exists, add a numeric suffix before the extension: `Title-2.musicxml`, `Title-3.musicxml`, etc.

## Critical Conventions

### Flat and Sharp Notation

music21 uses `-` for flats in note names, key names, and chord symbol **roots**. This is the most common source of bugs:

```python
# WRONG — "Bb7" is parsed as B root with a b7 alteration, NOT Bb dominant 7th
harmony.ChordSymbol("Bb7")   # B major + flat-7 — wrong!

# CORRECT — use '-' for flats in the root
harmony.ChordSymbol("B-7")   # Bb dominant 7th
harmony.ChordSymbol("E-7")   # Eb dominant 7th
harmony.ChordSymbol("A-maj7") # Ab major 7th
harmony.ChordSymbol("D-9")   # Db dominant 9th

# Sharps use '#' as expected in roots
harmony.ChordSymbol("F#m7")  # F# minor 7th
harmony.ChordSymbol("C#7")   # C# dominant 7th

# In extensions/alterations, 'b' and '#' work normally
harmony.ChordSymbol("Cm7b5")    # C half-diminished
harmony.ChordSymbol("Cmaj7#11") # C major 7 sharp 11
harmony.ChordSymbol("G7b9")     # G dominant 7 flat 9
harmony.ChordSymbol("C7#5")     # C augmented dominant 7
```

**Rule:** `-` for flats in the **root/bass** only. `b`/`#` for alterations in **extensions**.

The same `-` convention applies to note names and keys:

```python
note.Note("B-4")    # Bb4
key.Key("B-")       # Bb major
key.Key("e-")       # Eb minor (lowercase = minor)
key.Key("F#")       # F# major
key.Key("f#")       # F# minor
```

### Chord Repetition

When the same chord spans multiple consecutive bars, do NOT notate it every bar:

- **Notate at every chord change** — always.
- **Re-notate at section boundaries** — rehearsal marks, repeat signs.
- **Re-notate at contextually appropriate intervals** — choose an interval that divides the phrase length evenly. For an 8- or 16-bar phrase, every 4 bars. For a 9-bar phrase, every 3 bars. For a 6-bar phrase, every 3 or 2 bars. The goal is orientation, not clutter.
- **Never write the same chord on consecutive bars** unless it's a section boundary.

Example — 12-bar blues in Bb, each `|` is a bar:

```
Bb7 |    |    |    | Eb7 |    | Bb7 |    | F7  | Eb7 | Bb7 | F7
```

Chord symbols appear on bars 1, 5, 6, 7, 9, 10, 11, 12 — NOT every bar.

### Score Metadata

Always set title and any provided metadata using `metadata.Metadata`:

```python
from music21 import metadata

score.metadata = metadata.Metadata()
score.metadata.title = "Score Title"
score.metadata.composer = "Composer Name"       # if provided
score.metadata.movementName = "Subtitle Here"   # subtitle (shows below title in MusicXML)

# Arranger and copyright are set via Contributor and Copyright objects:
from music21 import metadata as md
score.metadata.addContributor(md.Contributor(role="arranger", name="Arranger Name"))
score.metadata.copyright = md.Copyright("© 2026 Author Name")
```

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

### 1st/2nd Endings (Volta Brackets)

Use `spanner.RepeatBracket` for volta brackets. Spanners must be appended to the **Part**, not the Measure.

```python
from music21 import spanner

# After building all measures and adding parts to score:
for part in score.parts:
    m_first = part.measure(15)   # 1st ending measure
    m_second = part.measure(16)  # 2nd ending measure
    part.append(spanner.RepeatBracket(m_first, number=1))
    part.append(spanner.RepeatBracket(m_second, number=2))
```

Volta brackets work with repeat barlines:

- The **last measure of the 1st ending** gets `rightBarline = bar.Repeat(direction='end')` (player repeats back)
- The **last measure of the 2nd ending** gets a regular barline (player continues)

For multi-measure endings, pass a list of measures:

```python
part.append(spanner.RepeatBracket([m13, m14, m15], number=1))
```

**Important:** Add volta brackets to **all parts**, not just the first part. Standard MusicXML — works in MuseScore, Dorico, and Sibelius.

### Multi-Part Scores

Each part needs its own key signature and time signature on measure 1:

```python
for part in all_parts:
    first_measure = part.measure(1)
    first_measure.insert(0.0, key.Key("B-"))
    first_measure.insert(0.0, meter.TimeSignature("4/4"))
```

Tempo marks and rehearsal marks go on the **first part only** — they apply to the full score.

### Transposing Instruments

music21 handles transposition automatically when using the correct instrument class.
A `Trumpet()` is in Bb — music21 will write concert pitch internally and produce
the correct transposed part in MusicXML. Write notes at **concert pitch** in the script.

For the full instrument list with transposition details, read:
`references/instruments.md` (relative to this skill directory).

## Score Building Template

See `references/template.py` for a complete, runnable template. Key patterns:

- Create score with `stream.Score()`, set metadata
- Create parts with `stream.Part()`, assign instrument classes
- Build measures in a loop, inserting key/time sig on measure 1
- Add chords via helper: `part.measure(n).insert(offset, harmony.ChordSymbol(...))`
- Add rehearsal marks: `part.measure(n).insert(0.0, expressions.RehearsalMark(...))`
- Export: `score.write("musicxml", fp=output_path)`

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
- Key/time signature on every part's first measure
- Rehearsal marks: A (m1), A2 (m9), B (m17), A3 (m25)
- Chord symbols on first part only, at change points
- Double barlines at section boundaries
- Repeat signs where the chart calls for them
- Tempo: MetronomeMark(number=66, text="Slow Blues")
- Export to `~/Desktop/Big Band Chart.musicxml`

## Troubleshooting

**Flat chords showing wrong extension (e.g. B(b7) instead of Bb7)**
Cause: Using `"Bb7"` instead of `"B-7"`. Fix: always use `-` for flats in roots.

**Title not showing in MuseScore**
Cause: Metadata not set properly. Fix: use `metadata.Metadata()` directly.

**Subtitle or arranger not showing in MuseScore**
Cause: music21 correctly exports `<movement-title>` and `<creator type="arranger">` in the MusicXML, but MuseScore 4 doesn't display them visually. This is a known MuseScore limitation — it expects `<credit>` elements for visual layout, which music21 doesn't generate from metadata. The data is in the file; the user can add subtitle/arranger text manually in MuseScore after import. Dorico and Sibelius may handle these fields better.

**Repeat barlines not appearing**
Cause: Using `bar.Barline('repeat-start')`. Fix: use `bar.Repeat(direction='start')`.

**music21 not found**
Cause: Wrong Python. Fix: use `mcp-score run` which uses the bundled interpreter.

**Notes sound wrong for transposing instruments**
Cause: Writing transposed pitch instead of concert pitch. Fix: always write concert pitch — music21 transposes automatically based on the instrument class.
