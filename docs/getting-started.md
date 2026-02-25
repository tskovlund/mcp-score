# Getting started

> Tutorial -- set up mcp-score and generate your first score.

## Prerequisites

- Python 3.13+
- An MCP-compatible client (Claude Desktop, Claude Code, etc.)
- [MuseScore 4](https://musescore.org/en/download) (optional -- needed for live manipulation features)

## Installation

```bash
pip install mcp-score
```

Or with uv:

```bash
uv tool install mcp-score
```

### Install the score generation skill

```bash
mcp-score install-skill
```

This copies the `score-generate` skill to `~/.claude/skills/score-generate/`.

### Install the MuseScore plugin (optional)

```bash
mcp-score install-plugin
```

This copies the WebSocket bridge plugin to your MuseScore 4 plugins directory. Then enable it in MuseScore: Plugins > Plugin Manager > MCP Score Bridge.

## Configure your MCP client

### Claude Code

```bash
claude mcp add mcp-score -- mcp-score serve
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-score": {
      "command": "mcp-score",
      "args": ["serve"]
    }
  }
}
```

## Generate your first score

With the `score-generate` skill installed, just ask Claude:

> "Create a 12-bar blues lead sheet in Bb major at 120 BPM."

Claude writes a music21 Python script, runs it, and produces a `.musicxml` file on your Desktop. Open it in MuseScore.

More examples:

> "Write a big band chart -- 32-bar AABA form, Bb major, slow blues at 66 BPM. Standard big band instrumentation: 5 saxes, 4 trumpets, 4 trombones, piano, guitar, bass, drums."

> "Create a string quartet in D major, 3/4 time, 16 measures at 72 BPM."

## Live MuseScore manipulation

For reading and modifying a score that's already open in MuseScore:

1. Open a score in MuseScore 4
2. Start the MCP Score Bridge plugin (Plugins menu)
3. Ask Claude:

> "Connect to MuseScore."

> "What's in the score right now?"

> "Read measures 1 through 8 of the first staff."

> "Add a rehearsal mark 'A' at measure 1 and a double barline at measure 8."

> "Transpose the trumpet part in measures 5-8 up a perfect fourth (5 semitones)."

> "Undo that last change."

All modifications happen immediately in MuseScore.

## Next steps

- [Architecture](architecture.md) -- understand how mcp-score is structured
- [Tool reference](reference.md) -- complete list of MCP tools
- [MuseScore plugin](musescore-plugin.md) -- detailed plugin setup
