# Tool reference

> Reference documentation — complete list of MCP tools provided by mcp-score.

## Generation tools

Tools for creating scores from scratch. Output: MusicXML files.

| Tool | Description | Status |
|------|-------------|--------|
| `create_score` | Create a new score with instrumentation, key, time signature, and form | Planned |
| `add_section` | Add a labeled section with rehearsal mark, barline, and measures | Planned |
| `set_chord_symbols` | Add chord symbols to specified measures | Planned |
| `export_musicxml` | Export the generated score as a MusicXML file | Planned |

## Analysis tools

Tools for reading and understanding musical content from a live MuseScore instance.

| Tool | Description | Status |
|------|-------------|--------|
| `read_passage` | Extract musical content from a range of bars and parts | Planned |
| `analyze_harmony` | Identify the chord progression in a passage | Planned |
| `identify_pattern` | Extract a rhythmic or melodic pattern | Planned |

## Manipulation tools

Tools for modifying scores in a live MuseScore instance.

| Tool | Description | Status |
|------|-------------|--------|
| `arrange_for` | Arrange a passage for different instruments/sections | Planned |
| `harmonize` | Add harmony parts following a chord progression | Planned |
| `transpose_passage` | Musically transpose a passage | Planned |

## Connection tools

Tools for managing the WebSocket bridge to MuseScore.

| Tool | Description | Status |
|------|-------------|--------|
| `connect` | Connect to a running MuseScore instance | Planned |
| `get_score_info` | Get metadata about the currently open score | Planned |
