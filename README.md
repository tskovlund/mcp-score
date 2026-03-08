[![CI](https://github.com/tskovlund/mcp-score/actions/workflows/ci.yml/badge.svg)](https://github.com/tskovlund/mcp-score/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mcp-score.svg)](https://pypi.org/project/mcp-score/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

# mcp-score

AI-powered music notation. Describe what you want in plain English -- get a publication-ready score in MuseScore.

## Quick demo

> "Create a big band chart -- 32-bar AABA form, key of Bb, slow blues at 66 BPM, with rhythm changes and rehearsal marks at each section."

Claude writes a complete music21 script, executes it, and hands you a MusicXML file ready to open in MuseScore, Dorico, Sibelius, or any notation app.

With the MuseScore plugin running, you can go further:

> "Read the melody in bars 9-16 and arrange it as a trombone soli following the chord progression."

Claude reads the live score, applies musical intelligence, and writes the arrangement back -- all through natural language.

## Installation

```bash
pip install mcp-score
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install mcp-score
```

Then set up the components you need:

```bash
# Install the score generation skill (for Claude Code)
mcp-score install-skill

# Install the MuseScore plugin (for live score manipulation)
mcp-score install-plugin

# Or install both at once
mcp-score install
```

## Components

mcp-score has three components that work together:

### MCP server

A Python MCP server with 18 tools for live score manipulation across MuseScore, Dorico, and Sibelius: connect/disconnect, read passages, add chords, set barlines, transpose, and more. Runs via `mcp-score serve` (or just `mcp-score`).

### Score generation skill

A Claude Code [skill](https://docs.anthropic.com/en/docs/claude-code/skills) that teaches Claude to write music21 Python scripts for score generation. Installed to `~/.claude/skills/score-generate/`. This handles the "create a score from scratch" use case -- no MCP round-trips needed.

### MuseScore plugin

A QML plugin that runs a WebSocket server inside MuseScore 4, enabling the MCP server to read from and write to the active score in real time. Supports 19 commands including navigation, note input, chord symbols, rehearsal marks, barlines, key/time signatures, tempo, transposition, and undo.

## Configuration

### Claude Code

Add the MCP server to your project or global settings:

```bash
claude mcp add mcp-score -- mcp-score serve
```

The score generation skill is installed separately with `mcp-score install-skill` and activates automatically when you ask Claude to create a score.

### Claude Desktop

Add to your `claude_desktop_config.json`:

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

### MuseScore plugin setup

After `mcp-score install-plugin`:

1. Open MuseScore 4
2. Go to **Plugins > Plugin Manager**
3. Enable **MCP Score Bridge**
4. The plugin starts a WebSocket server on port 8765

See [MuseScore plugin docs](docs/musescore-plugin.md) for details.

## CLI reference

```
mcp-score serve            Run the MCP server (default)
mcp-score run <script>     Run a Python script with music21 available
mcp-score install          Install skill and MuseScore plugin
mcp-score install-skill    Install the score-generate skill to ~/.claude/skills/
mcp-score install-plugin   Install the QML plugin to MuseScore's Plugins directory
mcp-score help             Show help
```

## Documentation

| Document | Description |
|----------|-------------|
| [Getting started](docs/getting-started.md) | Set up mcp-score and generate your first score |
| [Architecture](docs/architecture.md) | System design and key decisions |
| [Tool reference](docs/reference.md) | Complete list of MCP tools |
| [MuseScore plugin](docs/musescore-plugin.md) | Plugin installation and WebSocket protocol |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and PR process.

## Author

Thomas Skovlund Hansen — [skovlund.dev](https://skovlund.dev) · [thomas@skovlund.dev](mailto:thomas@skovlund.dev)

## License

[MIT](LICENSE)
