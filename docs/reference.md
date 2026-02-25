# Tool reference

> Reference -- complete list of MCP tools provided by mcp-score.

Score generation is handled by the `score-generate` Claude Code skill (not MCP tools). See the [skill documentation](../README.md#score-generation-skill) for usage.

The MCP server provides 13 tools for live MuseScore manipulation.

## Connection tools

Manage the WebSocket bridge to a live MuseScore instance.

### `connect_to_musescore`

Connect to a running MuseScore instance. The MCP Score Bridge plugin must be running.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"localhost"` | WebSocket host |
| `port` | `int` | `8765` | WebSocket port |

### `disconnect_from_musescore`

Close the WebSocket connection. No parameters.

### `get_live_score_info`

Get information about the currently open score in MuseScore. No parameters. Uses auto-connect.

### `ping_musescore`

Check if MuseScore is connected and responsive. No parameters.

## Analysis tools

Read musical content from a live MuseScore instance. Requires an active connection.

### `read_passage`

Read musical content from a range of measures.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_measure` | `int` | (required) | First measure (1-indexed) |
| `end_measure` | `int` | (required) | Last measure (inclusive, 1-indexed) |
| `staff` | `int \| None` | `None` | Staff index (0-indexed). Omit to read all staves. |

### `get_measure_content`

Read the content of a specific measure and staff.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `measure` | `int` | (required) | Measure number (1-indexed) |
| `staff` | `int` | `0` | Staff index (0-indexed) |

## Manipulation tools

Modify the live MuseScore score via the WebSocket bridge. Requires an active connection.

### `add_live_rehearsal_mark`

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `text` | `str` | Rehearsal mark text (e.g. `"A"`, `"Intro"`) |

### `add_live_chord_symbol`

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `symbol` | `str` | Chord symbol (e.g. `"Cmaj7"`, `"Dm7"`) |

### `set_live_barline`

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `barline_type` | `str` | One of `"double"`, `"final"`, `"startRepeat"`, `"endRepeat"`, `"dashed"`, `"dotted"` |

### `set_live_key_signature`

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `fifths` | `int` | Sharps (positive) or flats (negative): `0`=C, `2`=D, `-2`=Bb, `-3`=Eb |

### `set_live_tempo`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `measure` | `int` | (required) | Measure number (1-indexed) |
| `bpm` | `int` | (required) | Beats per minute |
| `text` | `str \| None` | `None` | Optional display text (e.g. `"Swing"`) |

### `transpose_passage`

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_measure` | `int` | First measure (1-indexed) |
| `end_measure` | `int` | Last measure (inclusive, 1-indexed) |
| `staff` | `int` | Staff index (0-indexed) |
| `semitones` | `int` | Semitones (positive=up, negative=down) |

### `undo_last_action`

Undo the last action in MuseScore. No parameters.
