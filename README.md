[![CI](https://github.com/tskovlund/mcp-score/actions/workflows/ci.yml/badge.svg)](https://github.com/tskovlund/mcp-score/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![pyright strict](https://img.shields.io/badge/pyright-strict-yellow.svg)](https://github.com/microsoft/pyright)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)

# mcp-score

MCP server for AI-driven music score generation and manipulation. Describe what you want in plain English — get a score in MuseScore.

## What it does

**Generate scores from natural language:**

> "Create a standard big band score, AABA form, key of Bb, 32 bars, with rehearsal marks at each section and chord symbols following a rhythm changes progression."

**Manipulate live scores:**

> "Read the pattern in bar 34, arrange it as a backing for the trombone section following the chord progression."

mcp-score connects to any MCP-compatible AI assistant (Claude Desktop, Claude Code, Cursor) and provides tools for creating, analyzing, and transforming music notation.

## Features

- **Score generation** — create scores from structured descriptions: instrumentation, form, key, time signature, rehearsal marks, barlines, chord symbols
- **Score analysis** — read and understand musical content from a live MuseScore instance
- **Score manipulation** — arrange, harmonize, transpose — high-level musical operations, not just note-by-note editing
- **MusicXML output** — portable format that works with MuseScore, Dorico, Sibelius, and 270+ other notation apps
- **Live MuseScore bridge** — WebSocket connection to a running MuseScore instance for real-time read/write

## Quick start

### Install

```bash
pip install mcp-score
```

Or from source with Nix + direnv:

```bash
git clone https://github.com/tskovlund/mcp-score.git
cd mcp-score
direnv allow    # sets up Python 3.13, uv, dev tools, git hooks
```

### Configure your MCP client

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mcp-score": {
      "command": "mcp-score"
    }
  }
}
```

### Generate your first score

Ask Claude:

> "Create a string quartet score in D major, 4/4 time, 16 bars with rehearsal marks at bars 1, 5, 9, and 13."

The server generates MusicXML that you can open in MuseScore or any notation software.

### Live manipulation (optional)

For reading from and writing to an open score in MuseScore, install the [MuseScore plugin](docs/musescore-plugin.md).

## Architecture

```
src/mcp_score/
  server.py           MCP server entry point
  tools/
    generation.py     Create scores from descriptions (music21 -> MusicXML)
    analysis.py       Read and understand musical content
    manipulation.py   Arrange, harmonize, transpose
  bridge/
    client.py         WebSocket client to MuseScore
  musescore/
    plugin.qml        MuseScore QML plugin (WebSocket server)
```

Two modes of operation:

| Mode | How it works | Requires MuseScore plugin? |
|------|-------------|---------------------------|
| **Generate** | music21 builds score -> MusicXML export -> open in any notation app | No |
| **Manipulate** | Read from live MuseScore -> transform -> write back | Yes |

See [docs/architecture.md](docs/architecture.md) for detailed design documentation.

## Development

```bash
pytest               # run tests
ruff check .         # lint
ruff format .        # format
pyright src/         # type check (strict mode)
```

## Documentation

| Document | Type | Description |
|----------|------|-------------|
| [Getting started](docs/getting-started.md) | Tutorial | Set up mcp-score and generate your first score |
| [Architecture](docs/architecture.md) | Reference | System design, package structure, key decisions |
| [Tool reference](docs/reference.md) | Reference | Complete list of MCP tools |
| [MuseScore plugin](docs/musescore-plugin.md) | How-to | Install the MuseScore plugin for live manipulation |

## License

MIT
