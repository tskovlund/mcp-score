# Architecture

> Explanation -- how mcp-score is structured and why.

## Overview

mcp-score provides two complementary approaches for AI-driven music notation:

1. **Score generation** via Claude Code skill -- Claude writes music21 Python scripts that export MusicXML, openable in any notation software
2. **Live manipulation** via MCP server -- read from and write to a running score application (MuseScore or Dorico) through a WebSocket bridge

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
| Writes music21 |   | tools/connection.py (6)    |
| Python script  |   | tools/analysis.py   (2)    |
| -> MusicXML    |   | tools/manipulation.py (7)  |
+----------------+   |                            |
                     | bridge/                    |
                     |   base.py (ScoreBridge)    |
                     |   musescore.py             |
                     |   dorico.py                |
                     +--------+----------+--------+
                              |          |
                  WebSocket   |          | WebSocket
             (ws://:8765)     |          | (ws://:4560)
                              |          |
              +---------------v--+  +----v-------------------+
              | MuseScore QML    |  | Dorico Remote Control  |
              | Plugin           |  | (built-in server)      |
              | (plugin.qml)     |  | ~994 commands          |
              +------------------+  +------------------------+
```

## Multi-bridge design

mcp-score supports multiple score notation applications through a common bridge abstraction. Only one bridge is active at a time -- connecting to a new application automatically disconnects the previous one.

### Bridge abstraction

`ScoreBridge` (in `bridge/base.py`) defines the common interface that all MCP tools depend on. Each concrete bridge implements this interface for its target application:

- `MuseScoreBridge` -- connects to the MuseScore QML plugin's WebSocket server
- `DoricoBridge` -- connects to Dorico's built-in Remote Control API

### Bridge registry

`bridge/__init__.py` manages the active bridge:

- `get_active_bridge()` -- returns the currently connected bridge (or None)
- `set_active_bridge()` -- sets which bridge is active
- Tools call `connected_bridge()` from `tools/__init__.py`, which returns the active bridge only if it's connected

### Dorico Remote Control protocol

Dorico 4+ has a built-in WebSocket server (default port 4560, configurable in preferences). No plugin needed -- Dorico IS the server.

**Handshake protocol:**

1. Client opens WebSocket to `ws://localhost:4560`
2. Client sends connect message with `clientName` and `handshakeVersion`
3. Dorico shows a dialog asking the user to allow the connection
4. Dorico responds with a session token
5. Client sends `acceptsessiontoken` with the received token
6. Dorico responds with `{"code": "kConnected"}`

Session tokens can be cached and reused for reconnection (Dorico skips the user dialog when a valid cached token is provided).

**Known limitations:**

- Cannot query arbitrary score content (notes/measures) -- only read properties of current selection
- No MusicXML export via API
- Good for score manipulation commands, limited for analysis
- Some operations (key signatures, tempo) not available through the command API

## Why two approaches?

**Generation is best as a skill.** Claude writes a complete music21 script in one shot, giving it full access to the entire music21 API. This is faster (one script vs dozens of MCP tool calls) and more flexible (no API surface to limit). A skill that teaches Claude music21 patterns produces better results than a curated set of MCP tools.

**Manipulation is best as MCP.** Reading from and writing to a live score application requires a persistent WebSocket connection and state management. MCP provides the right abstraction for this -- tools that Claude can call to inspect and modify the live score.

## Package structure

```
src/mcp_score/
  __init__.py           Package root
  app.py                Shared FastMCP instance ("mcp-score")
  cli.py                CLI entry point (serve, install-skill, install-plugin)
  server.py             MCP server -- imports tool modules, runs FastMCP
  tools/
    __init__.py         Shared helpers: connected_bridge(), to_json(), etc.
    connection.py       6 tools: connect/disconnect MuseScore & Dorico, ping, info
    analysis.py         2 tools: read_passage, get_measure_content
    manipulation.py     7 tools: live rehearsal marks, chords, barlines, keys,
                                 tempo, transpose, undo
  bridge/
    __init__.py         Bridge registry (get_active_bridge, set_active_bridge)
    base.py             ScoreBridge abstract base class
    musescore.py        MuseScoreBridge -- WebSocket client for MuseScore plugin
    dorico.py           DoricoBridge -- WebSocket client for Dorico Remote Control
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

### `bridge/base.py` -- abstract interface

`ScoreBridge` defines the common interface: `connect()`, `disconnect()`, `send_command()`, `ping()`, `get_score()`, `go_to_measure()`, etc. Concrete bridges implement this for each application.

### `bridge/musescore.py` -- MuseScore bridge

`MuseScoreBridge(ScoreBridge)` connects to the MuseScore QML plugin. Features auto-connect on first command, automatic reconnect on connection loss, and typed convenience methods for all plugin commands.

### `bridge/dorico.py` -- Dorico bridge

`DoricoBridge(ScoreBridge)` connects to Dorico's built-in Remote Control API. Handles the two-step handshake protocol, session token caching for reconnection, and maps common bridge operations to Dorico commands. Returns clear limitation messages for unsupported operations.

### `bridge/__init__.py` -- bridge registry

Manages which bridge is active. `get_active_bridge()` returns the current bridge; `set_active_bridge()` switches it. Connection tools call these to manage the active bridge lifecycle.

## MCP tools (15 total)

### Connection (6 tools)

| Tool | Purpose |
|------|---------|
| `connect_to_musescore` | Connect to MuseScore (configurable host/port) |
| `disconnect_from_musescore` | Close the MuseScore connection |
| `connect_to_dorico` | Connect to Dorico Remote Control API |
| `disconnect_from_dorico` | Close the Dorico connection |
| `get_live_score_info` | Get info about the open score (any app) |
| `ping_musescore` | Check if connected app is responsive (any app) |

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

### Single server, multiple bridges

One MCP server supports multiple score applications through the bridge abstraction. Only one bridge is active at a time -- this avoids confusion about which application a tool operates on. Connecting to a new application automatically disconnects the previous one.

### MusicXML as interchange format

MusicXML 4.0 is the standard interchange format, supported by 270+ applications including MuseScore, Dorico, and Sibelius. We do NOT generate `.mscz`/`.mscx` -- undocumented and version-fragile.

### music21 for score generation

music21 (MIT, Python) handles transposing instruments, voice leading, and MusicXML export. Used by the score-generate skill.

### WebSocket bridges for live manipulation

Both MuseScore and Dorico use WebSocket for communication, but the protocols differ:

- **MuseScore**: QML plugin runs inside MuseScore, opens a WebSocket server on port 8765. JSON messages with `command` and `params` fields.
- **Dorico**: Built-in WebSocket server on port 4560. JSON messages with `message` field for protocol-level operations and `commandName` for score commands. Requires a handshake protocol with session tokens.

### Server does not call LLMs

The MCP server provides primitives. Claude is the musical intelligence.

## Dependencies

| Dependency | Purpose |
|-----------|---------|
| `mcp[cli]` | MCP SDK (FastMCP server framework) |
| `music21` | Music theory library, MusicXML generation |
| `websockets` | WebSocket client for bridge connections |
