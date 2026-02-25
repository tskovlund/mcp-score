# Architecture

> Explanation -- how mcp-score is structured and why.

## Overview

mcp-score is an MCP server that enables AI assistants (Claude, etc.) to generate and manipulate music scores. It operates in two modes:

1. **Generation** -- build scores in-memory using music21, export as MusicXML, open in any notation software
2. **Live manipulation** -- read from and write to a running MuseScore instance via a WebSocket bridge

The MCP server does not call LLMs. Claude is the musical intelligence -- it understands the user's intent and calls the right tools with the right parameters. The server provides construction, analysis, and manipulation primitives.

## System diagram

```
+---------------------------------------------+
|  Claude (or any LLM via MCP)                |
|  "Create a big band score, AABA, Bb..."     |
+------------------+--------------------------+
                   | MCP protocol (stdio)
+------------------v--------------------------+
|  Python MCP Server  (src/mcp_score/)        |
|                                             |
|  tools/generation.py   (9 tools)            |
|    Score construction via ScoreManager      |
|                                             |
|  tools/connection.py   (4 tools)            |
|    WebSocket bridge lifecycle               |
|                                             |
|  tools/analysis.py     (2 tools)            |
|    Read content from live MuseScore         |
|                                             |
|  tools/manipulation.py (7 tools)            |
|    Modify the live MuseScore score          |
|                                             |
|  Generation engine: music21 -> MusicXML     |
|  Live bridge: WebSocket <-> MuseScore       |
+------------------+--------------------------+
                   | WebSocket (ws://localhost:8765)
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
  __init__.py           Package root
  app.py                Shared FastMCP instance ("mcp-score")
  server.py             Entry point — imports tool modules, runs the server
  instruments.py        Friendly instrument name -> music21 Instrument resolution
  score_manager.py      In-memory score state (music21 Score construction)
  tools/
    __init__.py
    generation.py       9 tools: create, annotate, add notes, export
    connection.py       4 tools: connect, disconnect, ping, get live info
    analysis.py         2 tools: read_passage, get_measure_content
    manipulation.py     7 tools: live rehearsal marks, chords, barlines, keys, tempo, transpose, undo
  bridge/
    __init__.py         Singleton bridge accessor (get_bridge)
    client.py           MuseScoreBridge WebSocket client
  musescore/
    plugin.qml          MuseScore QML plugin (WebSocket server)

tests/                  pytest tests
docs/                   Documentation (Diataxis structure)
```

## Module responsibilities

### `app.py` -- shared FastMCP instance

Creates the single `FastMCP("mcp-score")` instance that all tool modules import. This avoids circular imports: tool modules import `mcp` from `app`, and `server.py` imports `mcp` from `app` plus triggers tool registration via side-effect imports of each tool module.

### `server.py` -- entry point

Imports all four tool modules (causing their `@mcp.tool()` decorators to register with the shared FastMCP instance), then exposes the `main()` function that runs the server. The `mcp-score` console script points here.

### `instruments.py` -- instrument resolution

Maps friendly instrument names to music21 instrument classes. Supports:

- Full names ("alto saxophone", "french horn", "double bass")
- Abbreviations ("alto sax", "bari sax")
- Common aliases ("bb trumpet" -> Trumpet, "bass" -> Contrabass)
- Numbered variants ("trumpet 1", "alto sax 2", "violin-3")

The number suffix becomes the part name (e.g., "Trumpet 1", "Alto Saxophone 2").

### `score_manager.py` -- in-memory score state

`ScoreManager` holds a `music21.stream.Score` across tool calls. It provides methods for:

- Creating a score with parts, key/time signatures, tempo, and empty measures
- Adding rehearsal marks, barlines, chord symbols, tempo markings
- Adding notes to specific parts and measures (replacing existing content)
- Getting score info (parts, measures, transpositions)
- Exporting to MusicXML
- Clearing the score

The generation tools in `tools/generation.py` are thin wrappers around `ScoreManager` methods. A module-level `_manager = ScoreManager()` instance persists across all tool calls in the same server session.

### `bridge/client.py` -- WebSocket client

`MuseScoreBridge` connects to the MuseScore QML plugin over WebSocket. Features:

- Auto-connect on first command if not already connected
- Automatic reconnect on connection loss (one retry)
- Typed convenience methods for common operations (add note, rehearsal mark, barline, chord symbol, key/time signature, tempo, transpose, undo)
- Raw `send_command(action, params)` for any plugin command

### `bridge/__init__.py` -- singleton accessor

`get_bridge()` returns a shared `MuseScoreBridge` instance, creating one on first access. All connection and live tools use this shared instance.

## Tool categories

### Generation (9 tools)

Build scores from scratch using music21. No MuseScore connection needed.

| Tool | Purpose |
|------|---------|
| `create_score` | Create a new score with instruments, key, time, tempo, measures |
| `add_rehearsal_mark` | Add a rehearsal mark at a measure |
| `set_barline` | Set a barline type at the end of a measure |
| `add_chord_symbol` | Add a chord symbol at a measure and beat |
| `add_tempo_marking` | Add a tempo marking at a measure |
| `add_notes` | Add notes to a specific part and measure |
| `get_score_info` | Get info about the current in-memory score |
| `export_score` | Export the score as MusicXML |
| `clear_score` | Clear the in-memory score |

### Connection (4 tools)

Manage the WebSocket bridge to a live MuseScore instance.

| Tool | Purpose |
|------|---------|
| `connect_to_musescore` | Connect to MuseScore (configurable host/port) |
| `disconnect_from_musescore` | Close the WebSocket connection |
| `get_live_score_info` | Get info about the open score in MuseScore |
| `ping_musescore` | Check if MuseScore is responsive |

### Analysis (2 tools)

Read musical content from a live MuseScore instance. Requires an active connection.

| Tool | Purpose |
|------|---------|
| `read_passage` | Read content from a range of measures (optionally a specific staff) |
| `get_measure_content` | Read the content of a specific measure and staff |

### Manipulation (7 tools)

Modify the live MuseScore score via the WebSocket bridge. Requires an active connection.

| Tool | Purpose |
|------|---------|
| `add_live_rehearsal_mark` | Add a rehearsal mark in the live score |
| `add_live_chord_symbol` | Add a chord symbol in the live score |
| `set_live_barline` | Set a barline in the live score |
| `set_live_key_signature` | Set the key signature in the live score |
| `set_live_tempo` | Set the tempo in the live score |
| `transpose_passage` | Transpose a passage by semitones |
| `undo_last_action` | Undo the last action in MuseScore |

## Key design decisions

### MusicXML as interchange format

MusicXML 4.0 is the standard interchange format for music notation. It supports all musical elements we need (rehearsal marks, barlines, key/time signatures, transposing instruments, chord symbols, dynamics) and is imported faithfully by MuseScore, Dorico, Sibelius, and 270+ other applications.

We do NOT generate `.mscz`/`.mscx` files directly -- the format is undocumented and version-fragile.

### music21 for score construction

music21 (MIT, Python) is the most capable library for programmatic score generation. It handles transposing instruments, voice leading, and MusicXML export natively.

### WebSocket bridge for live manipulation

The MuseScore 4 plugin API uses QML + JavaScript. A QML plugin runs inside MuseScore, opens a WebSocket server, and the Python MCP server connects to it as a client. This is the same proven pattern used by existing MuseScore MCP servers.

### Server does not call LLMs

The MCP server provides construction and analysis tools. The LLM (Claude) is the musical intelligence -- it understands the user's intent and calls the right tools with the right parameters. This keeps the server simple, testable, and free of API key requirements.

### Separate generation and live workflows

Generation tools operate on an in-memory music21 Score and export MusicXML. Live tools operate on a running MuseScore instance via the WebSocket bridge. These are independent workflows -- generation does not require MuseScore to be running, and live manipulation does not use the in-memory score.

## Dependencies

| Dependency | Purpose |
|-----------|---------|
| `mcp[cli]` | MCP SDK (FastMCP server framework) |
| `music21` | Music theory library, MusicXML generation |
| `websockets` | WebSocket client for MuseScore bridge |
