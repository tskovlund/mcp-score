# Architecture

> Explanation -- how mcp-score is structured and why.

## Overview

mcp-score does three things for an AI assistant:

1. **Score generation** -- the assistant writes a music21 Python script that exports MusicXML, openable in any notation software. In Claude Code the bundled `score-generate` skill drives this. In any other MCP client the `generate_score` tool runs the script and `score_generation_guide` (also served as the `score-generate` MCP prompt) supplies the same instructions
2. **Live manipulation** via MCP server -- read from and write to a running score application (MuseScore Studio 4.4.2+, or experimentally Dorico) through a WebSocket bridge
3. **Rendering** -- the `render_score` tool exports PDF, PNG, MIDI, audio or MusicXML from a score file through the MuseScore command line; MuseScore must be installed but not running

## System diagram

```
+------------------------------------------------------------+
|  AI assistant (Claude Code, or any MCP client)             |
|  "Create a big band score, AABA, Bb..."                    |
+---------+--------------------------+-----------------------+
          |                          |
   Skill invocation           MCP protocol (stdio)
   (Claude Code only)                |
          |                          v
          |         +-------------------------------------+
          |         | Python MCP Server (src/mcp_score/)  |
          |         |                                     |
          |         | tools/generate.py      music21 ---> MusicXML file
          |         | tools/render.py        mscore CLI -> PDF/MIDI/audio
          |         | tools/connection.py                 |
          |         | tools/analysis.py                   |
          |         | tools/manipulation.py               |
          |         |                                     |
          |         | bridge/                             |
          |         |   base.py (ScoreBridge) registry.py |
          |         |   websocket.py (transport)          |
          |         |   musescore.py   remote_control.py  |
          |         |                  dorico.py          |
          |         | musescore/headless.py  mscore CLI   |
          |         +--------+---------------+------------+
          v                  |               |
+----------------+  WebSocket|               |WebSocket
| score-generate |  ws://:8765               |ws://:4560
| Claude skill   |           |               |
| writes music21 |  +--------v--------+  +---v---------------+
| -> MusicXML    |  | MuseScore QML   |  | Dorico Remote     |
+----------------+  | plugin          |  | Control (built-in,|
                    | (plugin.qml)    |  | experimental)     |
                    +-----------------+  +-------------------+
```

The server registers the tool modules: connection, analysis, manipulation, generation and rendering. Generation and rendering work on files and need no live connection.

## Multi-bridge design

mcp-score supports multiple score notation applications through a common bridge abstraction. Only one bridge is active at a time -- connecting to a new application automatically disconnects the previous one.

### Bridge abstraction

`ScoreBridge` (in `bridge/base.py`) defines the common interface that all MCP tools depend on. The bridge hierarchy:

```
ScoreBridge (ABC)             -- the operations every tool needs
└── WebSocketBridge           -- connection lifecycle over a WebSocketTransport, one reconnect
    ├── MuseScoreBridge       -- the MuseScore QML plugin's command/params protocol
    └── RemoteControlBridge   -- Remote Control handshake/command protocol
        └── DoricoBridge      -- Dorico defaults (port 4560)
```

- `ScoreBridge` -- the abstract interface: connection, navigation, reading, and every edit the tools offer, each returning a `CommandResult` dict (`{"error": ...}` when the application cannot do it)
- `WebSocketTransport` -- owns the socket: open, close, send, and one request/reply exchange
- `WebSocketBridge` -- connects a transport, auto-connects on the first command, reconnects once on a lost connection, and gives subclasses two hooks (`_on_connected`, `_on_disconnecting`) for their protocol's handshake
- `MuseScoreBridge` -- frames commands for the MuseScore plugin and maps the interface to plugin commands
- `RemoteControlBridge` -- Remote Control protocol logic, kept separate from application defaults: handshake with session tokens, command formatting, barline mapping, and limitation messages
- `DoricoBridge` -- thin subclass providing Dorico-specific defaults

### Bridge registry

`bridge/registry.py` holds one bridge per application and tracks the active one. `BridgeRegistry.activate(bridge)` disconnects whichever bridge was active, then connects the new one, so a failed connection leaves nothing active; `deactivate(bridge)` disconnects it; `connected()` returns the active bridge only while it is connected. There is no module-level registry: `server.py` creates one per server and hands it to the tools as `AppState` through the SDK's context injection (`context.py`). `require_bridge(context)` in `tools/__init__.py` reads the connected bridge from it and raises `ToolError` when nothing is connected.

### Remote Control protocol (Dorico)

Dorico 4+ implements a "Remote Control" WebSocket protocol. The protocol logic lives in `bridge/remote_control.py`, separate from Dorico's defaults in `bridge/dorico.py`.

Dorico support is experimental: it uses Dorico's undocumented Remote Control WebSocket API, is command-only (it cannot read note content), and has not been verified against a running Dorico instance.

**Handshake protocol:**

1. Client opens WebSocket to the application's port (Dorico: 4560)
2. Client sends connect message with `clientName` and `handshakeVersion`
3. Application shows a dialog asking the user to approve the connection
4. Application responds with a session token
5. Client sends `acceptsessiontoken` with the received token
6. Application responds with `{"code": "kConnected"}`

Session tokens can be cached and reused for reconnection (the application skips the approval dialog when a valid cached token is provided).

**Dorico-specific notes:**

- Default port 4560, configurable in Dorico preferences
- No plugin needed -- Dorico IS the server

## Capabilities and limitations

Dorico's Remote Control WebSocket API is fundamentally a **command execution and UI state observation** layer. It can trigger any action the application can perform (equivalent to pressing menu items or key commands) and read the UI state. But it cannot read musical content or perform operations that require text input through popovers.

### What the WebSocket API can do

| Capability                                                     |         MuseScore          |  Dorico (experimental)   |
| -------------------------------------------------------------- | :------------------------: | :----------------------: |
| Execute commands (undo, navigation, barlines, rehearsal marks) |            Yes             |           Yes            |
| Get application status                                         |            Yes             |           Yes            |
| Get selection properties                                       |            Yes             |           Yes            |
| Set barlines                                                   |            Yes             |           Yes            |
| Add rehearsal marks                                            |   Yes (with custom text)   | Yes (auto-numbered only) |
| Navigate to measure                                            |            Yes             |           Yes            |
| Read the element at the cursor                                 |    Yes (via QML plugin)    |            No            |
| Read cursor position                                           | Yes (measure, beat, staff) | Limited (UI state only)  |

### What Dorico's API cannot do

These are constraints of Dorico's Remote Control API, not of mcp-score:

- **Chord symbols, key signatures, time signatures, tempo marks, notes, dynamics** are entered through popovers, which the API cannot type into.
- **Score content** is not readable; the API reports UI state and selection properties.
- **Staff navigation and range selection** do not exist; the API acts on the current selection.
- **MusicXML export** is not exposed by either application's WebSocket API; `render_score` covers files on disk.

## Why a skill and tools for generation, MCP for manipulation?

**Generation is best done as one script.** The assistant writes a complete music21 script in one shot, with full access to the entire music21 API. This is faster (one script vs dozens of MCP tool calls) and more flexible (no API surface to limit). Instructions that teach the assistant music21 patterns produce better results than a curated set of note-by-note tools.

In Claude Code the `score-generate` skill does exactly that, with no MCP server involved. Other MCP clients cannot load skills, so the server offers the same workflow as tools: `score_generation_guide` returns the skill files (instructions, instrument reference, template) and `generate_score` runs the script the assistant writes. The tools read the skill files from the package, so there is one source of truth for the instructions.

**Manipulation is best as MCP.** Reading from and writing to a live score application requires a persistent WebSocket connection and state management. MCP provides the right abstraction for this -- tools the assistant can call to inspect and modify the live score.

## Package structure

Each module's docstring says what it is responsible for; the tools themselves are listed in the generated [tool reference](reference.md).

```
src/mcp_score/
  __init__.py           Package root
  cli.py                CLI entry point (serve, run, install, install-skill, install-plugin)
  resources.py          Locate bundled files (skill directory, plugin.qml)
  server.py             create_server() builds the MCPServer and registers every tool module
  context.py            AppState and ScoreContext: what the server hands every tool
  guide.py              The score-generate skill assembled into one document for MCP clients
  tools/
    base.py             Shared tool plumbing: ToolError, score_tool, require_bridge(), navigate()
    connection.py       Connect/disconnect MuseScore & Dorico, ping, score info
    analysis.py         read_passage, get_measure_content, get_selection_properties
    generate.py         generate_score, score_generation_guide (+ score-generate prompt)
    manipulation.py     Live notes, dynamics, rehearsal marks, chords, barlines, keys, time, tempo, measures, transpose, undo
    render.py           render_score (export through the MuseScore command line)
  bridge/
    base.py             ScoreBridge abstract interface, CommandResult, NoteDuration
    websocket.py        WebSocketTransport and WebSocketBridge -- connection lifecycle, reconnect
    remote_control.py   RemoteControlBridge -- Remote Control protocol layer
    musescore.py        MuseScoreBridge -- MuseScore plugin protocol
    dorico.py           DoricoBridge -- thin subclass (Dorico defaults, experimental)
    registry.py         BridgeRegistry -- the bridges and which one is active
  musescore/
    paths.py            Where MuseScore keeps user files (plugins directory)
    executable.py       Where MuseScore's executable is (env var, PATH, platform defaults)
    headless.py         Headless rendering through the MuseScore command line
    plugin.qml          MuseScore QML plugin (WebSocket server)

.claude/skills/
  score-generate/       Claude Code skill for score generation
    SKILL.md            Skill instructions + music21 patterns
    references/         Instrument reference and template script

scripts/
  musescore_harness.py  Installs and drives a real MuseScore for the integration tests

tests/                  pytest tests (unit; offline)
tests/integration/      Tests against a real MuseScore (opt-in via MCP_SCORE_INTEGRATION=1)
docs/                   Documentation (Diataxis structure)
```

## Key design decisions

### Single server, multiple bridges

One MCP server supports multiple score applications through the bridge abstraction. Only one bridge is active at a time -- this avoids confusion about which application a tool operates on. Connecting to a new application automatically disconnects the previous one.

### MusicXML as interchange format

MusicXML is the standard interchange format, supported by MuseScore, Dorico, Sibelius and most other notation software. We do NOT generate `.mscz`/`.mscx` -- undocumented and version-fragile.

### music21 for score generation

music21 (MIT, Python) handles transposing instruments, voice leading, and MusicXML export. Used by the score-generate skill and, through `generate_score`, by every other MCP client.

### WebSocket bridges for live manipulation

Both supported applications use WebSocket for communication, but the protocols differ:

- **MuseScore**: QML plugin runs inside MuseScore Studio 4.4.2+ and opens a WebSocket server on port 8765 with MuseScore's built-in `api.websocketserver` (4.4 dropped the `QtWebSockets` QML module; 4.4.2 added the replacement, so older versions are not supported). JSON messages with `command` and `params` fields. Custom protocol -- implemented directly in `MuseScoreBridge`.
- **Dorico** (experimental): Uses Dorico's "Remote Control" protocol with `message`/`commandName` fields and session token handshake. Protocol logic lives in `RemoteControlBridge`; the thin `DoricoBridge` subclass provides Dorico's defaults (port, name).

Sibelius was removed as out of scope; LilyPond is out of scope for now.

### Verified against real MuseScore in CI

The unit tests mock the WebSocket and the subprocess, so they cannot catch MuseScore API changes (4.7 renamed the undo action, for example). The `Integration` workflow therefore installs real MuseScore Studio releases -- on Linux the versions in `tests/integration/musescore-versions.json` (the oldest supported line, one in between and the newest), on Windows and macOS the newest -- and runs `tests/integration/` against them: headless `render_score` export and the live plugin bridge. `scripts/musescore_harness.py` downloads MuseScore, seeds its configuration with the plugin bound to a keyboard shortcut (plugins cannot be started from the command line), launches it with a fixture score and presses the shortcut. See [CONTRIBUTING.md](../CONTRIBUTING.md#integration-tests) for running it locally.

### Server does not call LLMs

The MCP server provides primitives. The assistant is the musical intelligence.
