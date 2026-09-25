[![CI](https://github.com/tskovlund/mcp-score/actions/workflows/ci.yml/badge.svg)](https://github.com/tskovlund/mcp-score/actions/workflows/ci.yml)
[![Integration](https://github.com/tskovlund/mcp-score/actions/workflows/integration.yml/badge.svg)](https://github.com/tskovlund/mcp-score/actions/workflows/integration.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

# mcp-score

Music notation for AI assistants. Describe a piece in plain language and get a MusicXML score; with MuseScore open, read and edit the live score by conversation.

Works with any MCP client (Claude Code, Claude Desktop, LM Studio, and others). Status: beta.

## Quick demo

> "Create a big band chart: 32-bar AABA form, key of Bb, slow blues at 66 BPM, with rhythm changes and rehearsal marks at each section."

The assistant writes a complete music21 script, runs it, and hands you a MusicXML file ready to open in MuseScore, Dorico, or any notation app.

With the MuseScore plugin running, you can go further:

> "Read the melody in bars 9-16 and arrange it as a trombone soli following the chord progression."

The assistant reads the live score, applies musical judgement, and writes the arrangement back, all through conversation.

## What it does

- **Generate scores.** The assistant writes a [music21](https://www.music21.org/) script that exports MusicXML, which opens in MuseScore, Dorico, or any notation app. In Claude Code this is driven by the bundled `score-generate` skill. In other MCP clients, the `generate_score` tool runs the script and `score_generation_guide` supplies the same instructions.
- **Edit live scores.** MCP tools connect to a running MuseScore and read passages, add notes, dynamics and chord symbols, set barlines, keys, time signatures and tempo, append measures, transpose, and undo.
- **Render.** The `render_score` tool exports PDF, PNG, MIDI or audio from a score file through the MuseScore command line; MuseScore must be installed but not running.

## Supported applications

| Application      | Versions        | Status                                                                                                |
| ---------------- | --------------- | ----------------------------------------------------------------------------------------------------- |
| MuseScore Studio | 4.4.2 and later | Supported; tested in CI on 4.4, 4.6 and 4.7. Earlier versions lack the plugin WebSocket API.          |
| Dorico           | 4 and later     | Experimental. Undocumented Remote Control API, command-only, not verified against a running instance. |
| Any notation app | MusicXML import | Generated scores open anywhere MusicXML does.                                                         |

## Install

Not on PyPI yet. Install from GitHub with Python 3.14 or later:

```bash
pip install git+https://github.com/tskovlund/mcp-score
# or
uv tool install git+https://github.com/tskovlund/mcp-score
```

Then:

```bash
mcp-score install-plugin   # MuseScore plugin, for live editing
mcp-score install-skill    # score-generate skill, for Claude Code
```

## Connect your MCP client

Claude Code:

```bash
claude mcp add mcp-score -- mcp-score serve
```

Claude Desktop and other clients: run the command `mcp-score` with the argument `serve`, for example in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-score": { "command": "mcp-score", "args": ["serve"] }
  }
}
```

## Use it with MuseScore

1. Open a score in MuseScore Studio 4.4.2 or later.
2. Plugins > Manage plugins > enable **MCP Score Bridge**, then Plugins > MCP Score Bridge. Keep its window open.
3. Ask your assistant to connect to MuseScore.

Details and troubleshooting: [MuseScore plugin](docs/musescore-plugin.md).

## Documentation

| Document                                     | Description                                    |
| -------------------------------------------- | ---------------------------------------------- |
| [Getting started](docs/getting-started.md)   | Set up mcp-score and generate your first score |
| [Tool reference](docs/reference.md)          | All MCP tools and CLI commands                 |
| [MuseScore plugin](docs/musescore-plugin.md) | Plugin installation and WebSocket protocol     |
| [Architecture](docs/architecture.md)         | System design and key decisions                |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Built in spare time, largely with Claude Code, and reviewed by a human before merge.

## Author

Thomas Skovlund Hansen — [skovlund.dev](https://skovlund.dev) · [thomas@skovlund.dev](mailto:thomas@skovlund.dev)

## License

[MIT](LICENSE)
