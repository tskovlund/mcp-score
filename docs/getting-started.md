# Getting started

> Tutorial -- walk through setting up mcp-score and generating your first score.

## Prerequisites

- Python 3.13+
- An MCP-compatible client (Claude Desktop, Claude Code, Cursor, etc.)
- [MuseScore 4](https://musescore.org/en/download) (optional -- needed for opening generated scores and for live manipulation features)

## Installation

### From source

```bash
git clone https://github.com/tskovlund/mcp-score.git
cd mcp-score
```

If you have [Devbox](https://www.jetify.com/devbox) + direnv:

```bash
direnv allow    # sets up Python 3.13, uv, dev tools, git hooks
```

If you have Devbox but not direnv:

```bash
devbox shell    # enter the dev environment
```

Otherwise (manual setup):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configure your MCP client

Add mcp-score to your MCP client's configuration.

### Claude Desktop

Add to your `claude_desktop_config.json` (on macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mcp-score": {
      "command": "mcp-score"
    }
  }
}
```

If you installed from source using devbox/uv, use the full path to the executable:

```json
{
  "mcpServers": {
    "mcp-score": {
      "command": "/path/to/mcp-score/.venv/bin/mcp-score"
    }
  }
}
```

### Claude Code

In your project's `.claude/settings.json` or via `claude mcp add`:

```bash
claude mcp add mcp-score -- mcp-score
```

Restart your MCP client after updating the configuration.

## Your first score

Once connected, ask Claude to create a score. Here are some example conversations.

### Create a big band score

> "Create a big band score in Bb major, 32 measures, 4/4 time at 160 BPM.
> Instruments: alto sax 1, alto sax 2, tenor sax 1, tenor sax 2, baritone sax, trumpet 1, trumpet 2, trumpet 3, trumpet 4, trombone 1, trombone 2, trombone 3, bass trombone, piano, bass, drums."

Claude will call `create_score` with all the instruments, then you can continue:

> "Add rehearsal marks: A at measure 1, B at measure 9, C at measure 17, D at measure 25. Set a final barline at measure 32."

> "Add chord changes for a rhythm changes progression: Bb6 on beat 1 of measure 1, G7 on beat 3, Cm7 on beat 1 of measure 2, F7 on beat 3..."

### Add a melody

> "In the Trumpet 1 part, add this melody to measure 1: Bb4 quarter, D5 quarter, F5 quarter, Bb5 quarter."

Claude calls `add_notes` with the part name, measure, and note list.

### Export the score

> "Export the score to ~/Documents/big-band-chart.musicxml"

This creates a MusicXML file that MuseScore (or any notation software) can open.

### Create a string quartet

> "Create a string quartet in D major, 3/4 time, 16 measures at 72 BPM with instruments: violin 1, violin 2, viola, cello."

## Live MuseScore features

For reading and modifying a score that is already open in MuseScore, you need the WebSocket bridge.

### Setup

1. Install the MCP Score Bridge plugin in MuseScore 4 (see [MuseScore plugin setup](musescore-plugin.md))
2. Open a score in MuseScore
3. Start the plugin from the Plugins menu

### Connect and explore

> "Connect to MuseScore."

Claude calls `connect_to_musescore` (defaults to `localhost:8765`).

> "What's in the score right now?"

Claude calls `get_live_score_info` to see the open score's metadata.

> "Read measures 1 through 8 of the first staff."

Claude calls `read_passage` to extract the musical content.

### Modify the live score

> "Add a rehearsal mark 'A' at measure 1 and a double barline at measure 8."

> "Set the tempo to 140 BPM with the text 'Allegro' at measure 1."

> "Transpose the trumpet part in measures 5-8 up a perfect fourth (5 semitones)."

> "Undo that last change."

All live modifications happen immediately in MuseScore.

## Next steps

- [Architecture](architecture.md) -- understand how mcp-score is structured
- [Tool reference](reference.md) -- complete list of all MCP tools with parameters
- [MuseScore plugin](musescore-plugin.md) -- set up the WebSocket bridge plugin
