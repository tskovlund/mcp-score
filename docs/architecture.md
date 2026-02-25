# Architecture

> Explanation -- how mcp-score is structured and why.

## Overview

mcp-score provides two complementary approaches for AI-driven music notation:

1. **Score generation** via Claude Code skill -- Claude writes music21 Python scripts that export MusicXML, openable in any notation software
2. **Live manipulation** via MCP server -- read from and write to a running MuseScore instance through a WebSocket bridge

## System diagram

```
+---------------------------------------------+
|  Claude (or any LLM via MCP)                |
|  "Create a big band score, AABA, Bb..."     |
+--------+--------------------+---------------+
         |                    |
    Skill invocation     MCP protocol (stdio)
         |                    |
         v                    v
+----------------+   +----------------------------+
| score-generate |   | Python MCP Server          |
| Claude Skill   |   | (src/mcp_score/)           |
|                |   |                            |
| Writes music21 |   | tools/connection.py (4)    |
| Python script  |   | tools/analysis.py   (2)    |
| -> MusicXML    |   | tools/manipulation.py (7)  |
+----------------+   |                            |
                     | bridge/client.py           |
                     +-------------+--------------+
                                   | WebSocket (ws://localhost:8765)
                     +-------------v--------------+
                     | MuseScore QML Plugin        |
                     | (musescore/plugin.qml)      |
                     | 19 WebSocket commands       |
                     +-----------------------------+
```

## Why two approaches?

**Generation is best as a skill.** Claude writes a complete music21 script in one shot, giving it full access to the entire music21 API. This is faster (one script vs dozens of MCP tool calls) and more flexible (no API surface to limit). A skill that teaches Claude music21 patterns produces better results than a curated set of MCP tools.

**Manipulation is best as MCP.** Reading from and writing to a live MuseScore instance requires a persistent WebSocket connection and state management. MCP provides the right abstraction for this -- tools that Claude can call to inspect and modify the live score.

## Package structure

```
src/mcp_score/
  __init__.py           Package root
  app.py                Shared FastMCP instance ("mcp-score")
  cli.py                CLI entry point (serve, install-skill, install-plugin)
  server.py             MCP server — imports tool modules, runs FastMCP
  tools/
    __init__.py
    connection.py       4 tools: connect, disconnect, ping, get live info
    analysis.py         2 tools: read_passage, get_measure_content
    manipulation.py     7 tools: live rehearsal marks, chords, barlines, keys,
                                 tempo, transpose, undo
  bridge/
    __init__.py         Singleton bridge accessor (get_bridge)
    client.py           MuseScoreBridge WebSocket client
  musescore/
    plugin.qml          MuseScore QML plugin (WebSocket server)

.claude/skills/
  score-generate/       Claude Code skill for score generation
    SKILL.md            Skill instructions + music21 patterns
    references/         Instrument reference, etc.

tests/                  pytest tests
docs/                   Documentation (Diataxis structure)
```

## Module responsibilities

### `app.py` -- shared FastMCP instance

Creates the single `FastMCP("mcp-score")` instance that all tool modules import. Avoids circular imports: tool modules import `mcp` from `app`, and `server.py` imports `mcp` from `app` plus triggers tool registration via side-effect imports.

### `cli.py` -- CLI entry point

Provides subcommands: `serve` (default, runs MCP server), `run` (execute a Python script with music21 available), `install-skill` (copies skill to `~/.claude/skills/`), `install-plugin` (copies QML plugin to MuseScore plugins directory), `install` (both).

### `server.py` -- MCP server

Imports the three tool modules (connection, analysis, manipulation) to register their `@mcp.tool()` decorators, then exposes the `main()` function. Called by `cli.py serve`.

### `bridge/client.py` -- WebSocket client

`MuseScoreBridge` connects to the MuseScore QML plugin. Features auto-connect on first command, automatic reconnect on connection loss, and typed convenience methods for all plugin commands.

### `bridge/__init__.py` -- singleton accessor

`get_bridge()` returns a shared `MuseScoreBridge` instance. All tool modules use this.

## MCP tools (13 total)

### Connection (4 tools)

| Tool | Purpose |
|------|---------|
| `connect_to_musescore` | Connect to MuseScore (configurable host/port) |
| `disconnect_from_musescore` | Close the WebSocket connection |
| `get_live_score_info` | Get info about the open score |
| `ping_musescore` | Check if MuseScore is responsive |

### Analysis (2 tools)

| Tool | Purpose |
|------|---------|
| `read_passage` | Read content from a range of measures |
| `get_measure_content` | Read a specific measure and staff |

### Manipulation (7 tools)

| Tool | Purpose |
|------|---------|
| `add_live_rehearsal_mark` | Add a rehearsal mark |
| `add_live_chord_symbol` | Add a chord symbol |
| `set_live_barline` | Set a barline type |
| `set_live_key_signature` | Set the key signature |
| `set_live_tempo` | Set the tempo |
| `transpose_passage` | Transpose by semitones |
| `undo_last_action` | Undo the last action |

## Key design decisions

### MusicXML as interchange format

MusicXML 4.0 is the standard interchange format, supported by 270+ applications including MuseScore, Dorico, and Sibelius. We do NOT generate `.mscz`/`.mscx` -- undocumented and version-fragile.

### music21 for score generation

music21 (MIT, Python) handles transposing instruments, voice leading, and MusicXML export. Used by the score-generate skill.

### WebSocket bridge for live manipulation

The QML plugin runs inside MuseScore, opens a WebSocket server on port 8765, and the Python MCP server connects as a client. JSON messages with `command` and `params` fields. Same proven pattern as existing MuseScore MCP servers.

### Server does not call LLMs

The MCP server provides primitives. Claude is the musical intelligence.

## Dependencies

| Dependency | Purpose |
|-----------|---------|
| `mcp[cli]` | MCP SDK (FastMCP server framework) |
| `music21` | Music theory library, MusicXML generation |
| `websockets` | WebSocket client for MuseScore bridge |
