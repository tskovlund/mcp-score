---
name: work-on-score
description: >
  Living document pattern for score projects. Read this skill whenever starting
  work on a score project — it defines the metadata.md format and lifecycle.
  Referenced by midi-to-score, score-generate, and MCP score tools.
allowed-tools: [Read, Write, Edit]
metadata:
  author: hnomichith
  version: "1.0"
---

# Score Project Living Document

Every score project lives under a given folder `<project-name>/` and contains
a `metadata.md` file that accumulates knowledge about the piece across sessions.

**Always read `metadata.md` before starting any work on a project.**
**Always update the relevant section(s) after completing work.**

This file is the shared memory between the user, Claude, and score tools (MCP).

---

## Project structure

```
<project-name>/
  metadata.md                  ← living document (this skill)
  <source>.mid                 ← source MIDI file(s), if any
  <Title>.musicxml             ← score(s)
```

---

## metadata.md format

```markdown
---
title: <Title>
composer: <Composer>
---

## MIDI file description

source_midi: <filename.mid>

<Plain-language description of what the user hears when listening to the MIDI.
Use timestamps (e.g. 5', 29') rather than bar numbers — the user listens, not reads.
Use full note duration names (quarter note, eighth note) to avoid ambiguity.>

## MIDI inspection

<Filled in by Claude after running the inspection script. Covers:
- Number of parts and note counts
- Note range (MIDI values and octave distribution)
- Voice structure (top-level vs Voice-nested elements)
- Tempo marks found in the file
- Key and time signatures>

## Score description

<Filled in by Claude after generating or significantly modifying the score. Covers:
- Output format (grand staff piano, lead sheet, etc.)
- Instrumentation and clef assignments
- Tempo and key used
- Arrangement decisions made (split point, transpositions, simplifications)
- Known issues or open questions>
```

---

## Section lifecycle

| Section | Created by | When |
|---|---|---|
| YAML frontmatter | User | At project creation |
| `## MIDI file description` | User + Claude | Before MIDI work; Claude adds answers from the user |
| `## MIDI inspection` | Claude | After running the inspection script |
| `## Score description` | Claude | After generating or meaningfully revising the score |

**If `metadata.md` does not exist**, create it with the frontmatter and any
sections you can fill in. Ask the user for title and composer if missing.

---

## Why this matters for MCP work

When manipulating a live score via MuseScore/Dorico/Sibelius, the `## Score description`
section gives Claude immediate context — what was built, why, and what's open —
without needing to re-derive it from the score. Keep it current.
