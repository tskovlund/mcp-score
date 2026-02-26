# Tool reference

> Reference -- complete list of MCP tools provided by mcp-score.

Score generation is handled by the `score-generate` Claude Code skill (not MCP tools). See the [skill documentation](../README.md#score-generation-skill) for usage.

The MCP server provides 18 tools across 3 categories for live score manipulation. All tools work with any connected application — MuseScore, Dorico, or Sibelius — though some operations are limited or unavailable depending on what the application's WebSocket API exposes.

## Connection tools (8)

Manage WebSocket bridges to live score notation applications. Each application has its own connect and disconnect pair, plus two shared tools that work with whichever application is currently active.

Connecting to a new application automatically disconnects any existing active connection.

### `connect_to_musescore`

Connect to a running MuseScore instance. The MCP Score Bridge QML plugin must be installed and running in MuseScore.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"localhost"` | WebSocket host |
| `port` | `int` | `8765` | WebSocket port |

### `disconnect_from_musescore`

Disconnect from MuseScore. No parameters.

### `connect_to_dorico`

Connect to a running Dorico instance via its built-in Remote Control API. Dorico 4+ has a built-in WebSocket server — no plugin required. The Remote Control API must be enabled in Dorico's preferences.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"localhost"` | WebSocket host |
| `port` | `int` | `4560` | WebSocket port (Dorico's default) |

### `disconnect_from_dorico`

Disconnect from Dorico. No parameters.

### `connect_to_sibelius`

Connect to a running Sibelius instance via Sibelius Connect. Sibelius 2024.3+ has a built-in WebSocket server — no plugin required. Requires the Sibelius Ultimate tier. The port is configurable in Sibelius's preferences.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"localhost"` | WebSocket host |
| `port` | `int` | `1898` | WebSocket port (Sibelius Connect's default) |

### `disconnect_from_sibelius`

Disconnect from Sibelius. No parameters.

### `get_live_score_info`

Get information about the currently open score in the connected application. No parameters. Requires an active connection — use one of the `connect_to_*` tools first.

### `ping_score_app`

Check if the connected score application is responsive. No parameters. Does not auto-connect — returns an error if not already connected.

---

## Analysis tools (3)

Read musical content from the connected score application. All analysis tools require an active connection.

**Note on Dorico and Sibelius:** These applications expose a Remote Control WebSocket API that returns application status rather than detailed note content. `read_passage` and `get_measure_content` return a `warning` field when connected to Dorico or Sibelius. `get_selection_properties` is the recommended tool for reading score data with those applications.

### `read_passage`

Read musical content from a range of measures. Returns notes, rests, and musical elements in the specified range.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_measure` | `int` | (required) | First measure to read (1-indexed) |
| `end_measure` | `int` | (required) | Last measure to read (inclusive, 1-indexed) |
| `staff` | `int \| None` | `None` | Staff index (0-indexed). Omit to read all staves. |

Works best with MuseScore. When connected to Dorico or Sibelius, the response includes a `warning` field explaining the data limitations.

### `get_measure_content`

Read the content of a specific measure and staff.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `measure` | `int` | (required) | Measure number (1-indexed) |
| `staff` | `int` | `0` | Staff index (0-indexed) |

Works best with MuseScore. When connected to Dorico or Sibelius, the response includes a `warning` field explaining the data limitations.

### `get_selection_properties`

Get properties of the current selection in the connected application. Behaviour varies by application:

- **MuseScore**: Returns cursor position info (measure, beat, staff).
- **Dorico / Sibelius**: Returns names, types, and values of all properties on the selected items via the Remote Control API's `getproperties` message. This is the closest the WebSocket API gets to reading score data, and is the recommended way to inspect content when connected to Dorico or Sibelius.

No parameters. Requires an active connection.

---

## Manipulation tools (7)

Modify the live score in the connected application. All manipulation tools require an active connection and navigate to the specified measure before applying the change.

**Application-specific limitations:** Several manipulation tools are unavailable when connected to Dorico or Sibelius, because their Remote Control WebSocket API interacts with UI commands rather than the score model directly. Specifically:

- `add_live_chord_symbol` — returns an error for Dorico/Sibelius (chord symbols require popover input that the API cannot provide).
- `set_live_key_signature` — returns an error for Dorico/Sibelius (key signatures require popover input).
- `set_live_tempo` — returns an error for Dorico/Sibelius (tempo marks require popover input).
- `add_live_rehearsal_mark` — succeeds for Dorico/Sibelius but ignores the `text` parameter; the application uses its own auto-numbering instead.
- `set_live_barline` — works for Dorico/Sibelius with the four supported barline types.
- `transpose_passage` and `undo_last_action` — work for all applications.

### `add_live_rehearsal_mark`

Add a rehearsal mark at the start of the specified measure.

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `text` | `str` | Rehearsal mark text (e.g. `"A"`, `"B"`, `"Intro"`) |

When connected to Dorico or Sibelius, the `text` parameter is ignored and the application uses its own auto-numbering. The response includes a `warning` field in that case.

### `add_live_chord_symbol`

Add a chord symbol at the start of the specified measure.

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `symbol` | `str` | Chord symbol (e.g. `"Cmaj7"`, `"Dm7"`, `"G7"`) |

Not supported with Dorico or Sibelius — returns an error for those applications.

### `set_live_barline`

Set a barline type at the end of the specified measure.

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `barline_type` | `str` | One of `"double"`, `"final"`, `"startRepeat"`, `"endRepeat"` |

Works with all three applications.

### `set_live_key_signature`

Set the key signature at the specified measure.

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `fifths` | `int` | Sharps (positive) or flats (negative): `0` = C major, `2` = D major, `-3` = Eb major |

Not supported with Dorico or Sibelius — returns an error for those applications.

### `set_live_tempo`

Set the tempo at the specified measure.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `measure` | `int` | (required) | Measure number (1-indexed) |
| `bpm` | `int` | (required) | Beats per minute |
| `text` | `str \| None` | `None` | Optional display text (e.g. `"Swing"`, `"Allegro"`) |

Not supported with Dorico or Sibelius — returns an error for those applications.

### `transpose_passage`

Transpose a passage by a number of semitones.

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_measure` | `int` | First measure (1-indexed) |
| `end_measure` | `int` | Last measure (inclusive, 1-indexed) |
| `staff` | `int` | Staff index (0-indexed) |
| `semitones` | `int` | Semitones to transpose (positive = up, negative = down) |

Works with all three applications.

### `undo_last_action`

Undo the last action in the connected score application. No parameters. Works with all three applications.
