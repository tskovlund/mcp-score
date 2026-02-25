# Tool reference

> Reference -- complete list of MCP tools provided by mcp-score.

## Generation tools

Build scores from scratch using music21. No MuseScore connection required.

### `create_score`

Create a new score with specified instrumentation and properties. Replaces any existing in-memory score.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | (required) | Score title |
| `instruments` | `list[str]` | (required) | Instrument names (e.g. `["trumpet 1", "trumpet 2", "alto sax", "piano"]`) |
| `key_signature` | `str` | `"C major"` | Key signature (e.g. `"Bb major"`, `"F# minor"`) |
| `time_signature` | `str` | `"4/4"` | Time signature (e.g. `"3/4"`, `"6/8"`) |
| `tempo` | `int` | `120` | Tempo in BPM |
| `num_measures` | `int` | `32` | Number of measures |

Returns: JSON with `success`, `message`, `parts` (list of part names), `num_measures`.

### `add_rehearsal_mark`

Add a rehearsal mark at the specified measure. Added to the first part (rehearsal marks apply to the full score).

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `label` | `str` | Rehearsal mark text (e.g. `"A"`, `"B"`, `"Intro"`, `"Coda"`) |

### `set_barline`

Set a barline type at the end of the specified measure. Applied to all parts.

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `barline_type` | `str` | Barline type (see [barline types](#barline-types)) |

### `add_chord_symbol`

Add a chord symbol at a specific measure and beat. Added to the first part (chord symbols apply to the whole ensemble).

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `beat` | `float` | Beat position (1.0 = beat 1, 2.0 = beat 2, etc.) |
| `symbol` | `str` | Chord symbol (e.g. `"Cmaj7"`, `"Dm7"`, `"G7alt"`, `"Bb7#11"`) |

### `add_tempo_marking`

Add a tempo marking at the specified measure.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `measure` | `int` | (required) | Measure number (1-indexed) |
| `bpm` | `int` | (required) | Beats per minute |
| `text` | `str \| None` | `None` | Optional display text (e.g. `"Swing"`, `"Ballad"`, `"Allegro"`) |

### `add_notes`

Add notes to a specific part and measure. Replaces any existing content (rests) in the measure.

| Parameter | Type | Description |
|-----------|------|-------------|
| `part` | `str` | Part name or index (e.g. `"Trumpet 1"`, `"Piano"`, `"0"`) |
| `measure` | `int` | Measure number (1-indexed) |
| `notes` | `list[dict]` | List of note objects (see below) |

Each note object has:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pitch` | `str` | (required) | Note name with octave (e.g. `"C5"`, `"Bb4"`, `"F#3"`) or `"rest"` |
| `duration` | `str` | `"quarter"` | Duration name (see [duration names](#duration-names)) |

Part lookup: parts can be referenced by 0-based index (`"0"`, `"1"`) or by name. Name matching is case-insensitive and supports partial matches (e.g. `"trumpet"` matches `"Trumpet 1"`).

### `get_score_info`

Get information about the current in-memory score. No parameters.

Returns: JSON with `title`, `num_parts`, `num_measures`, and `parts` (list of objects with `index`, `name`, `instrument`, `transposition`).

### `export_score`

Export the current in-memory score as MusicXML.

| Parameter | Type | Description |
|-----------|------|-------------|
| `filepath` | `str` | Output file path (should end in `.musicxml` or `.xml`) |

### `clear_score`

Clear the current in-memory score. No parameters.

## Connection tools

Manage the WebSocket bridge to a live MuseScore instance.

### `connect_to_musescore`

Connect to a running MuseScore instance. The MuseScore MCP Score Bridge plugin must be running.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"localhost"` | WebSocket host |
| `port` | `int` | `8765` | WebSocket port |

### `disconnect_from_musescore`

Close the WebSocket connection. No parameters.

### `get_live_score_info`

Get information about the currently open score in MuseScore. No parameters. Uses auto-connect (connects automatically if not already connected).

### `ping_musescore`

Check if MuseScore is connected and responsive. No parameters.

Returns: JSON with `success` and `message` if responsive, or `error` if not.

## Analysis tools

Read musical content from a live MuseScore instance. Requires an active connection.

### `read_passage`

Read musical content from a range of measures in the live MuseScore score.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_measure` | `int` | (required) | First measure to read (1-indexed) |
| `end_measure` | `int` | (required) | Last measure to read (inclusive, 1-indexed) |
| `staff` | `int \| None` | `None` | Staff index (0-indexed). If omitted, reads all staves. |

Returns: JSON with `success`, `start_measure`, `end_measure`, `staff`, and `elements` (list of objects with `measure` number and `content`).

### `get_measure_content`

Read the content of a specific measure and staff.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `measure` | `int` | (required) | Measure number (1-indexed) |
| `staff` | `int` | `0` | Staff index (0-indexed) |

## Manipulation tools

Modify the live MuseScore score via the WebSocket bridge. Requires an active connection.

### `add_live_rehearsal_mark`

Add a rehearsal mark in the live MuseScore score.

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `text` | `str` | Rehearsal mark text (e.g. `"A"`, `"B"`, `"Intro"`) |

### `add_live_chord_symbol`

Add a chord symbol in the live MuseScore score.

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `symbol` | `str` | Chord symbol (e.g. `"Cmaj7"`, `"Dm7"`, `"G7"`) |

### `set_live_barline`

Set a barline type in the live MuseScore score.

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `barline_type` | `str` | One of `"double"`, `"final"`, `"repeat-start"`, `"repeat-end"` |

### `set_live_key_signature`

Set the key signature in the live MuseScore score.

| Parameter | Type | Description |
|-----------|------|-------------|
| `measure` | `int` | Measure number (1-indexed) |
| `fifths` | `int` | Number of sharps (positive) or flats (negative). Examples: `0` = C major, `2` = D major, `-3` = Eb major, `5` = B major, `-4` = Ab major. |

### `set_live_tempo`

Set the tempo in the live MuseScore score.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `measure` | `int` | (required) | Measure number (1-indexed) |
| `bpm` | `int` | (required) | Beats per minute |
| `text` | `str \| None` | `None` | Optional display text (e.g. `"Swing"`, `"Allegro"`) |

### `transpose_passage`

Transpose a passage by a number of semitones in the live score.

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_measure` | `int` | First measure (1-indexed) |
| `end_measure` | `int` | Last measure (inclusive, 1-indexed) |
| `staff` | `int` | Staff index (0-indexed) |
| `semitones` | `int` | Semitones to transpose (positive = up, negative = down) |

### `undo_last_action`

Undo the last action in MuseScore. No parameters.

## Supported values

### Instrument names

Used in the `instruments` parameter of `create_score`. Case-insensitive. Supports numbered variants (e.g., `"trumpet 1"`, `"alto sax 2"`).

**Woodwinds:** `flute`, `piccolo`, `oboe`, `english horn`, `clarinet`, `bb clarinet`, `bass clarinet`, `bassoon`, `soprano sax` / `soprano saxophone`, `alto sax` / `alto saxophone`, `tenor sax` / `tenor saxophone`, `baritone sax` / `baritone saxophone` / `bari sax`

**Brass:** `trumpet` / `bb trumpet`, `horn` / `french horn`, `trombone`, `bass trombone`, `tuba`

**Strings:** `violin`, `viola`, `cello` / `violoncello`, `double bass` / `contrabass` / `bass` / `string bass`

**Keyboards:** `piano`, `organ`, `harpsichord`, `electric piano`

**Guitar:** `guitar` / `acoustic guitar`, `electric guitar`, `electric bass` / `bass guitar`

**Percussion:** `drums` / `drum set` / `percussion`

**Voices:** `soprano`, `alto`, `tenor`, `baritone`, `voice`

### Duration names

Used in the `notes` parameter of `add_notes`.

| Name | Quarter-length |
|------|---------------|
| `whole` | 4.0 |
| `half` | 2.0 |
| `quarter` | 1.0 |
| `eighth` / `8th` | 0.5 |
| `16th` | 0.25 |
| `32nd` | 0.125 |
| `dotted-whole` | 6.0 |
| `dotted-half` | 3.0 |
| `dotted-quarter` | 1.5 |
| `dotted-eighth` / `dotted-8th` | 0.75 |

### Barline types

Used in the `barline_type` parameter of `set_barline` and `set_live_barline`.

| Name | Description |
|------|-------------|
| `double` / `thin-thin` | Double barline |
| `final` / `thin-thick` | Final barline |
| `repeat-start` | Start repeat barline |
| `repeat-end` | End repeat barline |

### Key signature format

For generation tools (`create_score`): a string like `"C major"`, `"Bb major"`, `"F# minor"`, `"Ab major"`, `"D minor"`. Use `b` for flats and `#` for sharps.

For live tools (`set_live_key_signature`): an integer number of sharps/flats on the circle of fifths. Positive = sharps, negative = flats. Common values:

| Key | Fifths value |
|-----|-------------|
| C major / A minor | `0` |
| G major / E minor | `1` |
| D major / B minor | `2` |
| F major / D minor | `-1` |
| Bb major / G minor | `-2` |
| Eb major / C minor | `-3` |
| Ab major / F minor | `-4` |
