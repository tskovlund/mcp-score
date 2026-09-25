# MuseScore plugin setup

> How-to guide -- install and configure the mcp-score MuseScore plugin for live manipulation.

## Overview

The MuseScore plugin runs inside MuseScore Studio 4 and opens a WebSocket server on `localhost:8765` using MuseScore's built-in plugin API (`api.websocketserver`). The mcp-score Python server connects to this WebSocket to read from and write to the active score.

The plugin is only needed for **manipulation** and **analysis** tools (reading passages, arranging, transposing, etc.). **Generation** tools work without it -- they produce MusicXML files that MuseScore can open directly.

## Prerequisites

- MuseScore Studio **4.4.2 or later** (4.4.2 added the plugin WebSocket API the bridge uses)

Earlier versions are not supported: MuseScore 4.4 moved to Qt 6 and stopped shipping the `QtWebSockets` QML module, and versions before 4.4.2 have no replacement API. The plugin fails to load on those versions with `module "QtWebSockets" is not installed` (older plugin builds) or reports the missing API in its window (current build).

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

3. Restart MuseScore, then go to **Plugins > Manage plugins** and enable "MCP Score Bridge"

4. Run the plugin: **Plugins > MCP Score Bridge**

The plugin opens a small status window and starts a WebSocket server on port 8765. **Keep the window open** -- closing it stops the plugin and the server with it (MuseScore 4 has no persistent dock plugins). The mcp-score Python server connects automatically when you use manipulation or analysis tools.

## Verifying the connection

The plugin window shows `Bridge running on ws://localhost:8765` when the server is up. MuseScore's log file also records:

```
[mcp-score] Bridge plugin started -- WebSocket server on port 8765
```

Log locations:

- **macOS:** `~/Library/Application Support/MuseScore/MuseScore4/logs/`
- **Linux:** `~/.local/share/MuseScore/MuseScore4/logs/`
- **Windows:** `%LOCALAPPDATA%\MuseScore\MuseScore4\logs\`

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

| Command         | Params | Description                                                       |
| --------------- | ------ | ----------------------------------------------------------------- |
| `ping`          | none   | Health check. Returns `"pong"`.                                   |
| `getScore`      | none   | Score metadata: title, parts, measure count, key/time signatures. |
| `getCursorInfo` | none   | Current cursor position: measure, staff, beat, element info.      |

### Navigation

| Command       | Params           | Description                         |
| ------------- | ---------------- | ----------------------------------- |
| `goToMeasure` | `{measure: int}` | Move cursor to measure (1-indexed). |
| `goToStaff`   | `{staff: int}`   | Move cursor to staff (0-indexed).   |

### Writing notes

| Command   | Params                                          | Description                                                                                                                                  |
| --------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `addNote` | `{pitch, duration?, advanceCursorAfterAction?}` | Add a note at cursor. Pitch is MIDI number (60 = middle C). Duration is `{numerator, denominator}` fraction, defaults to 1/4 (quarter note). |

### Score markings

| Command            | Params                      | Description                                      |
| ------------------ | --------------------------- | ------------------------------------------------ |
| `addRehearsalMark` | `{text: string}`            | Add rehearsal mark (e.g. "A", "B").              |
| `setBarline`       | `{type: string}`            | Set barline type. See barline types below.       |
| `setKeySignature`  | `{fifths: int}`             | Set key signature (-7 to 7 on circle of fifths). |
| `setTimeSignature` | `{numerator, denominator}`  | Set time signature (e.g. 4/4, 3/4, 6/8).         |
| `setTempo`         | `{bpm: int, text?: string}` | Set tempo marking. Optional text override.       |
| `addChordSymbol`   | `{text: string}`            | Add chord symbol (e.g. "Cmaj7", "Dm7b5").        |
| `addDynamic`       | `{type: string}`            | Add dynamic marking. See dynamic types below.    |

### Score structure

| Command          | Params         | Description                                    |
| ---------------- | -------------- | ---------------------------------------------- |
| `appendMeasures` | `{count: int}` | Append empty measures to the end of the score. |

### Selection and transformation

| Command                | Params                                             | Description                                                                                    |
| ---------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `selectCurrentMeasure` | none                                               | Select all elements in the measure at the cursor.                                              |
| `selectCustomRange`    | `{startMeasure, endMeasure, startStaff, endStaff}` | Select a range. Measures are 1-indexed (inclusive). Staves are 0-indexed (inclusive).          |
| `transpose`            | `{semitones: int}`                                 | Transpose the current selection. Positive = up, negative = down. Requires an active selection. |

### Undo

| Command | Params | Description           |
| ------- | ------ | --------------------- |
| `undo`  | none   | Undo the last action. |

### Batch operations

| Command           | Params                                | Description                                                                                                |
| ----------------- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `processSequence` | `{sequence: [{action, params}, ...]}` | Execute multiple commands atomically in a single undo group. If any step fails, all steps are rolled back. |

### Barline types

`normal`, `double`, `startRepeat`, `endRepeat`, `endStartRepeat`, `final`, `dashed`, `dotted`, `tick`, `short`

### Dynamic types

`pppp`, `ppp`, `pp`, `p`, `mp`, `mf`, `f`, `ff`, `fff`, `ffff`, `fp`, `sfz`, `sffz`, `sfp`, `rfz`, `fz`

### Key signature fifths values

| Value | Major key | Minor key |
| ----- | --------- | --------- |
| -7    | Cb major  | Ab minor  |
| -6    | Gb major  | Eb minor  |
| -5    | Db major  | Bb minor  |
| -4    | Ab major  | F minor   |
| -3    | Eb major  | C minor   |
| -2    | Bb major  | G minor   |
| -1    | F major   | D minor   |
| 0     | C major   | A minor   |
| 1     | G major   | E minor   |
| 2     | D major   | B minor   |
| 3     | A major   | F# minor  |
| 4     | E major   | C# minor  |
| 5     | B major   | G# minor  |
| 6     | F# major  | D# minor  |
| 7     | C# major  | A# minor  |

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
      {
        "action": "addNote",
        "params": {
          "pitch": 60,
          "duration": { "numerator": 1, "denominator": 4 }
        }
      },
      {
        "action": "addNote",
        "params": {
          "pitch": 62,
          "duration": { "numerator": 1, "denominator": 4 }
        }
      },
      {
        "action": "addNote",
        "params": {
          "pitch": 64,
          "duration": { "numerator": 1, "denominator": 4 }
        }
      },
      {
        "action": "addNote",
        "params": {
          "pitch": 65,
          "duration": { "numerator": 1, "denominator": 4 }
        }
      }
    ]
  }
}
```

## Troubleshooting

### Plugin doesn't appear in Manage plugins

- Verify the `.qml` file is in the correct directory
- Restart MuseScore after adding the plugin
- Check that the file is named with a `.qml` extension
- Check your MuseScore version: **Help > About**. The bridge requires 4.4.2 or later
- MuseScore hides plugins that fail to compile. Look in the log file (paths above) for `ExtensionBuilder::load | Failed to load QML file` and the line after it, which names the cause. `module "QtWebSockets" is not installed` means an old copy of the plugin: re-run `mcp-score install-plugin`

### Plugin window shows an error

- `this MuseScore build has no plugin WebSocket API` -- your MuseScore is older than 4.4.2. Upgrade MuseScore

### WebSocket connection fails

- Ensure the plugin window is open and shows `Bridge running`
- Verify no other application is using port 8765: `lsof -i :8765` (macOS/Linux) or `netstat -ano | findstr 8765` (Windows)
- Check MuseScore's log file for `[mcp-score]` error messages

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
