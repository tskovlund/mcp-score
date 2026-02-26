# Contributing to mcp-score

Thanks for your interest in contributing! This guide covers everything you need to get started.

## Prerequisites

- **Python 3.13+**
- **[Devbox](https://www.jetify.com/devbox)** (recommended) or manually install `uv`, `ruff`, `pyright`
- **MuseScore 4** (for testing the QML plugin and live manipulation features)

## Development setup

```bash
git clone https://github.com/tskovlund/mcp-score.git
cd mcp-score

# Option A: devbox + direnv (recommended)
direnv allow

# Option B: devbox shell
devbox shell

# Option C: manual (if not using devbox)
uv venv --python python3.13
source .venv/bin/activate
uv sync
```

The devbox shell automatically creates a virtualenv, installs dependencies, and configures git hooks.

## Running checks

All checks must pass before merging:

```bash
devbox run check    # runs all of the below
devbox run lint     # ruff check .
devbox run format   # ruff format .
devbox run typecheck  # pyright src/
devbox run test     # pytest
```

Or directly (inside devbox shell):

```bash
ruff check .
ruff format --check .
pyright src/
pytest
```

## Code style

Follow the code standards in [CONVENTIONS.md](CONVENTIONS.md). The Python-specific highlights:

- Pyright strict mode, Ruff for linting/formatting (line length 88)
- `__all__` in every module, full variable names, src layout

## Commit conventions

This project uses [Conventional Commits](https://conventionalcommits.org), enforced by a git hook:

```
feat: add tempo detection tool
fix: handle missing key signature in MusicXML export
refactor: extract barline normalization to helper
docs: update plugin installation instructions
test: add tests for chord symbol parsing
```

**Note:** When committing through devbox (`devbox run -- git commit`), write multi-line messages to a temp file and use `git commit -F /tmp/msg.txt` instead of `-m` with a HEREDOC — devbox can produce literal `\n` otherwise.

## Tests

- **Naming:** `test_action_expectation` (e.g. `test_create_score_sets_key_signature`)
- **Structure:** Arrange / Act / Assert comments in every test
- **Lean:** every test must earn its place by adding value
- **Location:** `tests/` directory, one file per module (e.g. `test_bridge.py`, `test_cli.py`)

```bash
pytest                    # run all tests
pytest tests/test_cli.py  # run specific test file
pytest -k "test_install"  # run tests matching pattern
```

## PR process

All contributions go through pull requests — **do not push directly to `main`**.

1. Fork or create a feature branch from `main`
2. Make your changes
3. Ensure `devbox run check` passes
4. Push and create a pull request
5. CI must pass (lint, format, typecheck, test)
6. A maintainer will review your PR — address any feedback
7. The maintainer merges once approved

## Project structure

```
src/mcp_score/
  cli.py              CLI entry point (serve, run, install-skill, install-plugin)
  server.py           MCP server setup and tool imports
  app.py              Shared FastMCP instance
  tools/
    connection.py     Connect/disconnect MuseScore, Dorico & Sibelius, ping, score info
    analysis.py       Score reading tools (read_passage, get_measure_content, get_selection_properties)
    manipulation.py   Score modification tools (barlines, chords, keys, tempo, transpose, undo)
  bridge/
    base.py           ScoreBridge abstract base class
    remote_control.py Shared Remote Control protocol (Dorico & Sibelius)
    musescore.py      WebSocket client for MuseScore plugin
    dorico.py         Dorico defaults (thin subclass of RemoteControlBridge)
    sibelius.py       Sibelius defaults (thin subclass of RemoteControlBridge)
  musescore/
    plugin.qml        MuseScore 4 QML plugin (WebSocket server)

.claude/skills/
  score-generate/     Claude Code skill for music21 score generation
    SKILL.md          Skill definition and instructions
    references/
      instruments.md  music21 instrument class reference

tests/                One test file per module
docs/                 Diataxis-structured documentation
```

## Skill development

The `score-generate` skill (`.claude/skills/score-generate/SKILL.md`) teaches Claude to write music21 Python scripts. To modify it:

1. Edit `SKILL.md` or files in `references/`
2. Test by running `mcp-score install-skill` and asking Claude Code to generate a score
3. Common changes: adding instrument examples, fixing music21 API gotchas, updating the template

The skill is bundled with the pip package so users can install it with `mcp-score install-skill`.

## Architecture decisions

- **MusicXML** as interchange format (not `.mscz`/`.mscx`)
- **music21** for programmatic score generation
- **Skill over MCP for generation** — one script vs. dozens of tool calls
- **MCP for live manipulation** — WebSocket bridge to MuseScore
- **Python** — music21 is Python-only and MCP SDK has first-class Python support

See [docs/architecture.md](docs/architecture.md) for the full rationale.
