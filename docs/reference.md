# Tool reference

> Reference -- complete list of MCP tools provided by mcp-score.

In Claude Code, score generation is driven by the `score-generate` skill. The generation tools below make the same workflow available in any MCP client.

Connection, analysis and manipulation tools work with any connected application — MuseScore or Dorico — though some operations are limited or unavailable depending on what the application's WebSocket API exposes. Generation and rendering tools work on files and need no connection.

Dorico support is experimental: it uses Dorico's undocumented Remote Control WebSocket API, is command-only (it cannot read note content), and has not been verified against a running Dorico instance.

## Generation tools

Generate a score file from a music21 script. No connection to a score application is needed. The script runs on the user's machine, with the user's privileges, in the same Python interpreter as the server (so music21 is importable).

### `score_generation_guide`

Return the bundled `score-generate` guide as Markdown: the skill instructions (music21 conventions, troubleshooting), the instrument class reference, and the template script. No parameters. Read it before calling `generate_score`. Returns `{"error": ...}` if the bundled skill files cannot be found.

The same text is also exposed as the MCP prompt `score-generate`, so clients that support prompts can load it as a slash command.

### `generate_score`

Run a complete music21 Python script that ends by calling `score.write("musicxml", fp="<Title>.musicxml")`. The script is written to a temp file and executed in a subprocess; files created in the working directory during the run are reported back.

| Parameter    | Type          | Default    | Description                                                                                                                  |
| ------------ | ------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `script`     | `str`         | (required) | Complete Python source of the generation script                                                                              |
| `output_dir` | `str \| None` | `None`     | Working directory for the run. Defaults to a fresh directory under the user's Desktop (or home directory when there is none) |
| `timeout`    | `float`       | `120`      | Seconds to wait before the script is killed                                                                                  |

On success returns `{"success": true, "output_files": [...], "stdout": ...}` with absolute paths of the new files. On failure returns `{"error": ..., "stderr": ..., "returncode": ...}` with the tail of the script's stderr.

---

## Connection tools

Manage WebSocket bridges to live score notation applications. Each application has its own connect and disconnect pair, plus two shared tools that work with whichever application is currently active.

Connecting to a new application automatically disconnects any existing active connection.

### `connect_to_musescore`

Connect to a running MuseScore instance. The MCP Score Bridge QML plugin must be installed and running in MuseScore.

| Parameter | Type  | Default       | Description    |
| --------- | ----- | ------------- | -------------- |
| `host`    | `str` | `"localhost"` | WebSocket host |
| `port`    | `int` | `8765`        | WebSocket port |

### `disconnect_from_musescore`

Disconnect from MuseScore. No parameters.

### `connect_to_dorico`

Connect to a running Dorico instance via its built-in Remote Control API. Dorico 4+ has a built-in WebSocket server — no plugin required. The Remote Control API must be enabled in Dorico's preferences.

**Experimental:** this uses Dorico's undocumented Remote Control WebSocket API, is command-only (it cannot read note content), and has not been verified against a running Dorico instance.

| Parameter | Type  | Default       | Description                       |
| --------- | ----- | ------------- | --------------------------------- |
| `host`    | `str` | `"localhost"` | WebSocket host                    |
| `port`    | `int` | `4560`        | WebSocket port (Dorico's default) |

### `disconnect_from_dorico`

Disconnect from Dorico. No parameters.

### `get_live_score_info`

Get information about the currently open score in the connected application. No parameters. Requires an active connection — use one of the `connect_to_*` tools first.

### `ping_score_app`

Check if the connected score application is responsive. No parameters. Does not auto-connect — returns an error if not already connected.

---

## Analysis tools

Read musical content from the connected score application. All analysis tools require an active connection.

**Note on Dorico:** Dorico exposes a Remote Control WebSocket API that returns application status rather than detailed note content. `read_passage` and `get_measure_content` return a `warning` field when connected to Dorico. `get_selection_properties` is the recommended tool for reading score data with Dorico.

### `read_passage`

Read musical content from a range of measures. Returns notes, rests, and musical elements in the specified range.

| Parameter       | Type          | Default    | Description                                              |
| --------------- | ------------- | ---------- | -------------------------------------------------------- |
| `start_measure` | `int`         | (required) | First measure to read (1-indexed)                        |
| `end_measure`   | `int`         | (required) | Last measure to read (inclusive, 1-indexed)              |
| `staff`         | `int \| None` | `None`     | Staff index (0-indexed). Omit to read the current staff. |

Works best with MuseScore. When connected to Dorico, the response includes a `warning` field explaining the data limitations, and giving a `staff` returns an error because Dorico cannot move to a staff.

### `get_measure_content`

Read the content of a specific measure and staff.

| Parameter | Type  | Default    | Description                |
| --------- | ----- | ---------- | -------------------------- |
| `measure` | `int` | (required) | Measure number (1-indexed) |
| `staff`   | `int` | `0`        | Staff index (0-indexed)    |

MuseScore only: Dorico cannot move to a staff or select a measure through its API, so the tool returns an error there. Use `get_selection_properties` with Dorico.

### `get_selection_properties`

Get properties of the current selection in the connected application. Behaviour varies by application:

- **MuseScore**: Returns cursor position info (measure, beat, staff).
- **Dorico**: Returns names, types, and values of all properties on the selected items via the Remote Control API's `getproperties` message. This is the closest the WebSocket API gets to reading score data, and is the recommended way to inspect content when connected to Dorico.

No parameters. Requires an active connection.

---

## Manipulation tools

Modify the live score in the connected application. All manipulation tools require an active connection and navigate to the specified measure (and staff, where given) before applying the change; if the application cannot get there, the tool returns that error and changes nothing.

**Application-specific limitations:** Most manipulation tools are unavailable when connected to Dorico, because its Remote Control WebSocket API triggers UI commands rather than editing the score model, and cannot type into popovers or move the selection. Specifically:

- `add_live_note`, `add_live_chord_symbol`, `add_live_dynamic`, `set_live_key_signature`, `set_live_time_signature`, `set_live_tempo`, `append_live_measures` and `transpose_passage` — return an error for Dorico.
- `add_live_rehearsal_mark` — succeeds for Dorico but ignores the `text` parameter; the application uses its own auto-numbering instead.
- `set_live_barline` — works for Dorico with the four supported barline types.
- `undo_last_action` — works for both applications.
- Any tool that takes a `staff` — returns an error for Dorico, which cannot move to a staff.

### `add_live_note`

Add a note at the start of the specified measure. Consecutive calls on the same measure append notes one after another, since the application advances its cursor after each note.

| Parameter     | Type  | Default    | Description                                                       |
| ------------- | ----- | ---------- | ----------------------------------------------------------------- |
| `measure`     | `int` | (required) | Measure number (1-indexed)                                        |
| `pitch`       | `int` | (required) | MIDI pitch, 0–127 (`60` = middle C)                               |
| `numerator`   | `int` | `1`        | Duration numerator (with the default denominator: a quarter note) |
| `denominator` | `int` | `4`        | Duration denominator                                              |
| `staff`       | `int` | `0`        | Staff index (0-indexed)                                           |

Not supported with Dorico — returns an error for that application.

### `add_live_rehearsal_mark`

Add a rehearsal mark at the start of the specified measure.

| Parameter | Type  | Description                                        |
| --------- | ----- | -------------------------------------------------- |
| `measure` | `int` | Measure number (1-indexed)                         |
| `text`    | `str` | Rehearsal mark text (e.g. `"A"`, `"B"`, `"Intro"`) |

When connected to Dorico, the `text` parameter is ignored and the application uses its own auto-numbering. The response includes a `warning` field in that case.

### `add_live_chord_symbol`

Add a chord symbol at the start of the specified measure.

| Parameter | Type  | Description                                    |
| --------- | ----- | ---------------------------------------------- |
| `measure` | `int` | Measure number (1-indexed)                     |
| `symbol`  | `str` | Chord symbol (e.g. `"Cmaj7"`, `"Dm7"`, `"G7"`) |

Not supported with Dorico — returns an error for that application.

### `add_live_dynamic`

Add a dynamic marking at the start of the specified measure.

| Parameter | Type  | Default    | Description                                                           |
| --------- | ----- | ---------- | --------------------------------------------------------------------- |
| `measure` | `int` | (required) | Measure number (1-indexed)                                            |
| `dynamic` | `str` | (required) | Dynamic such as `"pp"`, `"p"`, `"mp"`, `"mf"`, `"f"`, `"ff"`, `"sfz"` |
| `staff`   | `int` | `0`        | Staff index (0-indexed)                                               |

Not supported with Dorico — returns an error for that application.

### `set_live_barline`

Set a barline type at the end of the specified measure.

| Parameter      | Type  | Description                                                                                                                                                                                                                                         |
| -------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `measure`      | `int` | Measure number (1-indexed)                                                                                                                                                                                                                          |
| `barline_type` | `str` | One of `"normal"`, `"double"`, `"final"`, `"dashed"`, `"dotted"`, `"tick"`, `"short"`, `"startRepeat"`, `"endRepeat"`, `"endStartRepeat"`. Repeat types set the measure's repeat flags; `"endStartRepeat"` also starts a repeat in the next measure |

Works with both applications.

### `set_live_key_signature`

Set the key signature at the specified measure.

| Parameter | Type  | Description                                                                          |
| --------- | ----- | ------------------------------------------------------------------------------------ |
| `measure` | `int` | Measure number (1-indexed)                                                           |
| `fifths`  | `int` | Sharps (positive) or flats (negative): `0` = C major, `2` = D major, `-3` = Eb major |

Not supported with Dorico — returns an error for that application.

### `set_live_time_signature`

Set the time signature from the specified measure onward.

| Parameter     | Type  | Description                         |
| ------------- | ----- | ----------------------------------- |
| `measure`     | `int` | Measure number (1-indexed)          |
| `numerator`   | `int` | Beats per measure (e.g. `3` in 3/4) |
| `denominator` | `int` | Beat unit (e.g. `4` in 3/4)         |

Not supported with Dorico — returns an error for that application.

### `set_live_tempo`

Set the tempo at the specified measure.

| Parameter | Type          | Default    | Description                                         |
| --------- | ------------- | ---------- | --------------------------------------------------- |
| `measure` | `int`         | (required) | Measure number (1-indexed)                          |
| `bpm`     | `int`         | (required) | Beats per minute                                    |
| `text`    | `str \| None` | `None`     | Optional display text (e.g. `"Swing"`, `"Allegro"`) |

Not supported with Dorico — returns an error for that application.

### `append_live_measures`

Append empty measures to the end of the live score.

| Parameter | Type  | Default | Description                 |
| --------- | ----- | ------- | --------------------------- |
| `count`   | `int` | `1`     | How many measures to append |

Not supported with Dorico — returns an error for that application.

### `transpose_passage`

Transpose the notes of a passage by a number of semitones, with conventional spelling (a minor second up turns C into Db). Key signatures and chord symbols in the passage are left unchanged.

| Parameter       | Type  | Description                                             |
| --------------- | ----- | ------------------------------------------------------- |
| `start_measure` | `int` | First measure (1-indexed)                               |
| `end_measure`   | `int` | Last measure (inclusive, 1-indexed)                     |
| `staff`         | `int` | Staff index (0-indexed)                                 |
| `semitones`     | `int` | Semitones to transpose (positive = up, negative = down) |

Not supported with Dorico — returns an error for that application, which cannot select a range through its API.

### `undo_last_action`

Undo the last action in the connected score application. No parameters. Works with both applications.

---

## Rendering tools

Export score files by running the MuseScore Studio 4 command line. MuseScore must be installed but does not need to be running, and no plugin or connection is required.

### `render_score`

Render a score file to PDF, PNG, MIDI, MP3, WAV or MusicXML. The input is typically MusicXML but can be any file MuseScore opens (`.mscz`, `.mid`, ...). MuseScore is located from the `MCP_SCORE_MUSESCORE_PATH` environment variable, then PATH (`mscore`, `musescore`, `mscore4portable`, `MuseScore4`), then the platform default: `/Applications/MuseScore 4.app` on macOS, `%ProgramFiles%\MuseScore 4` on Windows, or the `org.musescore.MuseScore` Flatpak on Linux. If it is not found, set `MCP_SCORE_MUSESCORE_PATH` to the executable in the MCP server's environment. On Linux the export runs headless (`QT_QPA_PLATFORM=offscreen`). Rendering times out after 120 seconds.

| Parameter     | Type          | Default    | Description                                                                                                        |
| ------------- | ------------- | ---------- | ------------------------------------------------------------------------------------------------------------------ |
| `input_path`  | `str`         | (required) | Path to the score file to render                                                                                   |
| `format`      | `str`         | `"pdf"`    | One of `"pdf"`, `"png"`, `"midi"`, `"mp3"`, `"wav"`, `"musicxml"`. PNG writes one file per page (`-1`, `-2`, ...)  |
| `output_path` | `str \| None` | `None`     | Output file. Defaults to the input path with the format's extension. Must match the format; overwritten if present |

Returns `{"success": true, "output_path": ..., "output_files": [...], "format": ...}`, where `output_files` lists the files MuseScore actually wrote (one per page for PNG), or `{"error": ...}` including the tail of MuseScore's stderr when no output was written. A rendering counts as successful when its output exists; if MuseScore crashes while shutting down afterwards (seen with MuseScore Studio 4.7 on macOS 26 after PDF export), the result carries a `warning` instead of failing.

## CLI

```
mcp-score serve            Run the MCP server (default when no command is given)
mcp-score run <script>     Run a Python script with music21 available
mcp-score install          Install the skill and the MuseScore plugin
mcp-score install-skill    Install the score-generate skill to ~/.claude/skills/
mcp-score install-plugin   Install the QML plugin to MuseScore's Plugins directory
mcp-score help             Show help
```
