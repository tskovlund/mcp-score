# MuseScore plugin setup

> How-to guide -- install and configure the mcp-score MuseScore plugin for live manipulation.

## Overview

The MuseScore plugin runs inside MuseScore 4 and opens a WebSocket server on `localhost:8765`. The mcp-score Python server connects to this WebSocket to read from and write to the active score.

The plugin is only needed for **manipulation** and **analysis** tools (reading passages, arranging, transposing, etc.). **Generation** tools work without it -- they produce MusicXML files that MuseScore can open directly.

## Prerequisites

- MuseScore 4 (4.0 or later)
- QtWebSockets support (included in standard MuseScore 4 builds)

## Installation

1. Locate your MuseScore plugins directory:
   - **macOS:** `~/Library/Application Support/MuseScore4/Plugins/`
   - **Linux:** `~/.local/share/MuseScore4/Plugins/`
   - **Windows:** `%APPDATA%/MuseScore4/Plugins/`

2. Copy the plugin file:
   ```bash
   # macOS
   cp src/mcp_score/musescore/plugin.qml ~/Library/Application\ Support/MuseScore4/Plugins/mcp-score-bridge.qml

   # Linux
   cp src/mcp_score/musescore/plugin.qml ~/.local/share/MuseScore4/Plugins/mcp-score-bridge.qml
   ```

3. In MuseScore, go to **Plugins > Plugin Manager** and enable "MCP Score Bridge"

4. Run the plugin: **Plugins > MCP Score Bridge**

The plugin starts a WebSocket server on port 8765. It runs as a dock plugin (invisible) so it stays active as long as MuseScore is open. The mcp-score Python server connects automatically when you use manipulation or analysis tools.

## Verifying the connection

After enabling the plugin, you can verify it is running by checking the MuseScore console (View > Console in some builds) for the message:

```
[mcp-score] Bridge plugin started -- WebSocket server on port 8765
```

You can also test the connection with any WebSocket client:

```bash
# Using websocat (install with: cargo install websocat)
echo '{"command": "ping"}' | websocat ws://localhost:8765

# Expected response: {"result":"pong"}
```

## Protocol

The plugin accepts JSON messages over WebSocket. Each message must have a `command` field and optionally a `params` field. Responses have either a `result` field (on success) or an `error` field (on failure).

### Request format

```json
{
    "command": "commandName",
    "params": { ... }
}
```

### Response format (success)

```json
{
    "result": { ... }
}
```

### Response format (error)

```json
{
    "error": "Description of what went wrong"
}
```

## Available commands

### Score information

| Command | Params | Description |
|---------|--------|-------------|
| `ping` | none | Health check. Returns `"pong"`. |
| `getScore` | none | Score metadata: title, parts, measure count, key/time signatures. |
| `getCursorInfo` | none | Current cursor position: measure, staff, beat, element info. |

### Navigation

| Command | Params | Description |
|---------|--------|-------------|
| `goToMeasure` | `{measure: int}` | Move cursor to measure (1-indexed). |
| `goToStaff` | `{staff: int}` | Move cursor to staff (0-indexed). |

### Writing notes

| Command | Params | Description |
|---------|--------|-------------|
| `addNote` | `{pitch, duration?, advanceCursorAfterAction?}` | Add a note at cursor. Pitch is MIDI number (60 = middle C). Duration is `{numerator, denominator}` fraction, defaults to 1/4 (quarter note). |

### Score markings

| Command | Params | Description |
|---------|--------|-------------|
| `addRehearsalMark` | `{text: string}` | Add rehearsal mark (e.g. "A", "B"). |
| `setBarline` | `{type: string}` | Set barline type. See barline types below. |
| `setKeySignature` | `{fifths: int}` | Set key signature (-7 to 7 on circle of fifths). |
| `setTimeSignature` | `{numerator, denominator}` | Set time signature (e.g. 4/4, 3/4, 6/8). |
| `setTempo` | `{bpm: int, text?: string}` | Set tempo marking. Optional text override. |
| `addChordSymbol` | `{text: string}` | Add chord symbol (e.g. "Cmaj7", "Dm7b5"). |
| `addDynamic` | `{type: string}` | Add dynamic marking. See dynamic types below. |

### Score structure

| Command | Params | Description |
|---------|--------|-------------|
| `appendMeasures` | `{count: int}` | Append empty measures to the end of the score. |

### Selection and transformation

| Command | Params | Description |
|---------|--------|-------------|
| `selectCurrentMeasure` | none | Select all elements in the measure at the cursor. |
| `selectCustomRange` | `{startMeasure, endMeasure, startStaff, endStaff}` | Select a range. Measures are 1-indexed (inclusive). Staves are 0-indexed (inclusive). |
| `transpose` | `{semitones: int}` | Transpose the current selection. Positive = up, negative = down. Requires an active selection. |

### Undo

| Command | Params | Description |
|---------|--------|-------------|
| `undo` | none | Undo the last action. |

### Batch operations

| Command | Params | Description |
|---------|--------|-------------|
| `processSequence` | `{sequence: [{action, params}, ...]}` | Execute multiple commands atomically in a single undo group. If any step fails, all steps are rolled back. |

### Barline types

`normal`, `double`, `startRepeat`, `endRepeat`, `endStartRepeat`, `final`, `dashed`, `dotted`, `tick`, `short`

### Dynamic types

`pppp`, `ppp`, `pp`, `p`, `mp`, `mf`, `f`, `ff`, `fff`, `ffff`, `fp`, `sfz`, `sffz`, `sfp`, `rfz`, `fz`

### Key signature fifths values

| Value | Major key | Minor key |
|-------|-----------|-----------|
| -7 | Cb major | Ab minor |
| -6 | Gb major | Eb minor |
| -5 | Db major | Bb minor |
| -4 | Ab major | F minor |
| -3 | Eb major | C minor |
| -2 | Bb major | G minor |
| -1 | F major | D minor |
| 0 | C major | A minor |
| 1 | G major | E minor |
| 2 | D major | B minor |
| 3 | A major | F# minor |
| 4 | E major | C# minor |
| 5 | B major | G# minor |
| 6 | F# major | D# minor |
| 7 | C# major | A# minor |

## Example: writing a melody

This example uses `processSequence` to write a four-note melody in the first measure:

```json
{
    "command": "processSequence",
    "params": {
        "sequence": [
            { "action": "goToMeasure", "params": { "measure": 1 } },
            { "action": "goToStaff", "params": { "staff": 0 } },
            { "action": "setTempo", "params": { "bpm": 120, "text": "Allegro" } },
            { "action": "addNote", "params": { "pitch": 60, "duration": { "numerator": 1, "denominator": 4 } } },
            { "action": "addNote", "params": { "pitch": 62, "duration": { "numerator": 1, "denominator": 4 } } },
            { "action": "addNote", "params": { "pitch": 64, "duration": { "numerator": 1, "denominator": 4 } } },
            { "action": "addNote", "params": { "pitch": 65, "duration": { "numerator": 1, "denominator": 4 } } }
        ]
    }
}
```

## Troubleshooting

### Plugin doesn't appear in Plugin Manager

- Verify the `.qml` file is in the correct directory
- Restart MuseScore after adding the plugin
- Check that the file is named with a `.qml` extension

### WebSocket connection fails

- Ensure the plugin is running (look for the `[mcp-score]` log messages in MuseScore's console)
- Verify no other application is using port 8765: `lsof -i :8765`
- Check MuseScore's console for error messages

### "No score is currently open" errors

- Open a score in MuseScore before sending commands
- The plugin operates on the currently active score (`curScore`)

### Commands seem to have no effect

- Write operations require an open, editable score (not a read-only file)
- Check that the cursor position (measure, staff) is within valid ranges
- Use `getScore` to verify the score state and `getCursorInfo` to check cursor position

### processSequence rolls back unexpectedly

- If any step in the sequence fails, all steps are undone
- Check the `failedAction` and `failedIndex` fields in the error response to identify which step failed
- Fix the failing step and retry the entire sequence
