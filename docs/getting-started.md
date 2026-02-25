# Getting started

> Tutorial — walk through setting up mcp-score and generating your first score.

## Prerequisites

- Python 3.13+
- [MuseScore 4](https://musescore.org/en/download) (for opening generated scores and live manipulation)
- An MCP-compatible client (Claude Desktop, Claude Code, Cursor, etc.)

## Installation

### From PyPI (once published)

```bash
pip install mcp-score
```

### From source

```bash
git clone https://github.com/tskovlund/mcp-score.git
cd mcp-score
```

If you have Nix + direnv:

```bash
direnv allow    # sets up Python 3.13, uv, dev tools, git hooks
```

Otherwise:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configure your MCP client

Add mcp-score to your MCP client's configuration. For Claude Desktop, add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-score": {
      "command": "mcp-score"
    }
  }
}
```

## Your first score

Once connected, ask Claude to generate a score:

> "Create a string quartet score in D major, 4/4 time, 16 bars with rehearsal marks at bars 1, 5, 9, and 13."

The server will generate a MusicXML file that you can open in MuseScore.

## Next steps

- Read the [architecture](architecture.md) for a deeper understanding of how mcp-score works
- See the [tool reference](reference.md) for all available MCP tools
- Set up the [MuseScore plugin](musescore-plugin.md) for live score manipulation
