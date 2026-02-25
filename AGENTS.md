# mcp-score

MCP server for AI-driven music score generation and manipulation. Natural language to notation via MusicXML, with live MuseScore integration for reading and modifying open scores.

## Architecture

```
src/mcp_score/
  server.py           MCP server entry point (FastMCP)
  tools/
    generation.py     Score generation (create_score, add_section, set_chord_symbols)
    analysis.py       Score analysis (read_passage, analyze_harmony, identify_pattern)
    manipulation.py   Score manipulation (arrange_for, harmonize, transpose_passage)
  bridge/
    client.py         WebSocket client to MuseScore plugin
  musescore/
    plugin.qml        MuseScore QML plugin (WebSocket server)

tests/                pytest tests, one file per module
docs/                 Diataxis-structured documentation
```

Two modes of operation:
- **Generate:** music21 builds a score -> exports MusicXML -> opens in MuseScore
- **Manipulate:** reads from a live MuseScore instance via WebSocket -> transforms -> writes back

See [docs/architecture.md](docs/architecture.md) for detailed design documentation.

## Dev environment

Nix + uv hybrid. Nix provides Python 3.13, uv, ruff, pyright. uv manages Python packages in `.venv/`.

```bash
nix develop          # or: direnv allow
uv sync              # install/update Python deps
```

## Commands

```bash
pytest               # run tests
ruff check .         # lint
ruff format .        # format
ruff format --check .  # check formatting
pyright src/         # type check (strict mode)
mcp-score            # run the MCP server (after uv sync)
```

## Code conventions

- **src layout** — all package code under `src/mcp_score/`
- **Pyright strict mode** — all function signatures fully typed
- **Ruff** for linting and formatting (line length 88)
- **Conventional commits** — enforced by `.githooks/commit-msg`
- **`__all__`** — every module explicitly declares its public API
- **Full variable names** — `measure_index` not `m`, `staff_number` not `s`
- Direct to main for small changes, branch + PR for structural work

## Test conventions

- **Naming:** `test_action_expectation` (e.g. `test_create_score_sets_key_signature`)
- **Structure:** Arrange / Act / Assert comments in every test
- **Lean:** every test must earn its place by adding value

## Tool design principles

Tools are organized in three tiers by abstraction level:

1. **Generation** — create scores from structured descriptions (music21 -> MusicXML)
2. **Analysis** — read and understand musical content from a live MuseScore instance
3. **Manipulation** — transform and write back (combines reading + musical intelligence + writing)

The MCP server does NOT call LLMs. Claude is the musical intelligence; the server provides construction and analysis primitives.

## Key technical decisions

- **MusicXML** as interchange format (not .mscz/.mscx — undocumented and version-fragile)
- **music21** for programmatic score generation (handles transposing instruments, voice leading, MusicXML export)
- **WebSocket bridge** to MuseScore via QML plugin (proven pattern, same as existing MuseScore MCP servers)
- **Python** because music21 is Python-only and the MCP SDK has first-class Python support

## Git workflow

- **Direct to main:** small tweaks, bug fixes
- **Branch + PR:** new tools, structural changes, anything touching multiple modules

### PR workflow

1. Create feature branch
2. Make changes, test with `pytest` and manual MuseScore testing
3. Push and create PR
4. Review loop: wait for CI + Copilot -> address comments -> push -> iterate until clean
5. Merge

### Issue tracking

GitHub Issues for implementation tracking. Linear for higher-level planning (workspace: tskovlund, project: MCP Music Notation).

**Templates:** Enhancement, Bug, Research. Use the appropriate template. Blank issues disabled.

**Labels:** `bug`, `enhancement`, `documentation`, `research`, `dependencies`, `github actions`
