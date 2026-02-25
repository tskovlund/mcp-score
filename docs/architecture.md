# Architecture

> Reference documentation — describes how mcp-score is structured and why.

## Overview

mcp-score is an MCP server that enables AI assistants (Claude, etc.) to generate and manipulate music scores. It operates in two modes:

1. **Generate** — build scores from scratch using music21, export as MusicXML, open in MuseScore (or any notation software)
2. **Manipulate** — read from and write to a live MuseScore instance via a WebSocket bridge

## System diagram

```
+---------------------------------------------+
|  Claude (or any LLM via MCP)                |
|  "Create a big band score, AABA, Bb..."     |
+------------------+--------------------------+
                   | MCP protocol
+------------------v--------------------------+
|  Python MCP Server  (src/mcp_score/)        |
|                                             |
|  tools/generation.py                        |
|    Score construction from descriptions     |
|                                             |
|  tools/analysis.py                          |
|    Read and understand musical content      |
|                                             |
|  tools/manipulation.py                      |
|    Modify scores in a live instance         |
|                                             |
|  Generation engine: music21 -> MusicXML     |
|  Live bridge: WebSocket <-> MuseScore       |
+------------------+--------------------------+
                   | WebSocket
+------------------v--------------------------+
|  MuseScore QML Plugin                       |
|  (src/mcp_score/musescore/plugin.qml)       |
|                                             |
|  Score reading (notes, chords, keys...)     |
|  Score writing (all element types)          |
|  WebSocket server on localhost:8765         |
+---------------------------------------------+
```

## Package structure

```
src/mcp_score/
  __init__.py         Package root
  server.py           MCP server entry point (FastMCP)
  tools/
    __init__.py
    generation.py     Score generation tools (create_score, add_section, ...)
    analysis.py       Score analysis tools (read_passage, analyze_harmony, ...)
    manipulation.py   Score manipulation tools (arrange_for, transpose, ...)
  bridge/
    __init__.py
    client.py         WebSocket client to MuseScore plugin
  musescore/
    plugin.qml        MuseScore QML plugin (WebSocket server)

tests/                pytest tests, one file per module
docs/                 Documentation (Diataxis structure)
```

## Tool tiers

Tools are organized by abstraction level:

### Generation (create from nothing)

High-level tools that build scores via music21 and export MusicXML:

- `create_score` — create a score from a description (instrumentation, form, key, time signature)
- `add_section` — add a labeled section with rehearsal marks, barlines, measures
- `set_chord_symbols` — add chord symbols to measures

### Analysis (read and understand)

Tools that read musical content from a live MuseScore instance:

- `read_passage` — extract notes, rhythms, and articulations from a range of bars/parts
- `analyze_harmony` — identify the chord progression in a passage
- `identify_pattern` — extract a rhythmic or melodic pattern

### Manipulation (transform and write back)

High-level tools that combine reading, musical intelligence, and writing:

- `arrange_for` — take a passage and arrange it for different instruments
- `harmonize` — add harmony parts following a chord progression and voicing style
- `transpose_passage` — musically transpose a passage (respecting key, not just pitch-shifting)

## Key design decisions

### MusicXML as interchange format

MusicXML 4.0 is the standard interchange format for music notation. It supports all musical elements we need (rehearsal marks, barlines, key/time signatures, transposing instruments, chord symbols, dynamics) and is imported faithfully by MuseScore, Dorico, Sibelius, and 270+ other applications.

We do NOT generate `.mscz`/`.mscx` files directly — the format is undocumented and version-fragile.

### music21 for score construction

music21 (MIT, Python) is the most capable library for programmatic score generation. It handles transposing instruments, voice leading, and MusicXML export natively.

### WebSocket bridge for live manipulation

The MuseScore 4 plugin API uses QML + JavaScript. A QML plugin runs inside MuseScore, opens a WebSocket server, and the Python MCP server connects to it. This is the same proven pattern used by existing MuseScore MCP servers.

### Server does not call LLMs

The MCP server provides construction and analysis tools. The LLM (Claude) is the musical intelligence — it understands the user's intent and calls the right tools with the right parameters. This keeps the server simple, testable, and free of API key requirements.

## Dependencies

| Dependency | Purpose |
|-----------|---------|
| `mcp[cli]` | MCP SDK (FastMCP server framework) |
| `music21` | Music theory library, MusicXML generation |
| `websockets` | WebSocket client for MuseScore bridge |
