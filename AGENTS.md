# mcp-score

AI-driven music score generation and manipulation. Two complementary approaches:

- **Score generation** via Claude Code skill (`.claude/skills/score-generate/`) — Claude writes music21 Python scripts that export MusicXML. No MCP needed; runs as a standalone skill.
- **Live score manipulation** via MCP server — reads from and writes to a running score application (MuseScore, Dorico, or Sibelius) via WebSocket bridge.

## Architecture

```
src/mcp_score/
  server.py           MCP server entry point (FastMCP)
  app.py              Shared FastMCP instance
  tools/
    connection.py     Connect/disconnect MuseScore, Dorico & Sibelius, ping, score info
    analysis.py       Read passages and measures from live score
    manipulation.py   Modify live score (barlines, chords, keys, tempo, transpose)
  bridge/
    base.py           ScoreBridge abstract base class
    remote_control.py Shared Remote Control protocol (Dorico & Sibelius)
    musescore.py      WebSocket client for MuseScore plugin
    dorico.py         Dorico defaults (thin subclass of RemoteControlBridge)
    sibelius.py       Sibelius defaults (thin subclass of RemoteControlBridge)
  musescore/
    plugin.qml        MuseScore QML plugin (WebSocket server, 19 commands)

.claude/skills/
  score-generate/     Claude Code skill for score generation via music21
    SKILL.md
    references/

tests/                pytest tests, one file per module
docs/                 Diataxis-structured documentation
```

### Why two approaches?

**Generation** is best as a skill: Claude writes a complete music21 script in one shot, giving it full access to the entire music21 API. This is faster (one script vs dozens of MCP tool calls) and more flexible (no API surface to limit).

**Manipulation** is best as MCP: reading from and writing to a live score application requires a persistent WebSocket connection and state management that MCP handles well.

See [docs/architecture.md](docs/architecture.md) for detailed design documentation.

## Dev environment

Devbox + uv. Devbox provides Python 3.13, uv, ruff, pyright via Nix. uv manages Python packages in `.venv/`.

```bash
direnv allow         # or: devbox shell
```

## Commands

```bash
devbox run test      # run tests
devbox run lint      # lint
devbox run format    # format
devbox run typecheck # type check (strict mode)
devbox run check     # all of the above
mcp-score            # run the MCP server (after uv sync)
```

Or directly (inside devbox shell / after direnv allow):

```bash
pytest               # run tests
ruff check .         # lint
ruff format .        # format
pyright src/         # type check (strict mode)
```

**Multi-line commits:** `devbox run -- git commit -m "$(cat ...)"` produces literal `\n`. Always use `git commit -F /tmp/msg.txt` for multi-line commit messages.

## Code conventions

- **src layout** — all package code under `src/mcp_score/`
- **Pyright strict mode** — all function signatures fully typed
- **Ruff** for linting and formatting (line length 88)
- **Conventional commits** — enforced by `.githooks/commit-msg`
- **`__all__`** — every module explicitly declares its public API
- **Full variable names** — `measure_index` not `m`, `staff_number` not `s`. Intent should be readable, not inferred from abbreviations
- **No magic constants** — named constants for ports, protocol versions, error codes. Every literal value must be self-documenting
- **No DRY violations** — extract shared logic into a single source of truth. Prefer a base class or utility over copy-paste
- **Single responsibility** — each file and class has one clear purpose. Thin subclasses over monolithic duplicated implementations
- **No shorthand** — `connection` not `conn`, `message` not `msg`, `response` not `resp`
- Direct to main for small changes, branch + PR for structural work

## Test conventions

- **Naming:** `test_<action>_<expected_outcome>` (e.g. `test_create_score_sets_key_signature`)
- **Structure:** Arrange / Act / Assert comments in every test
- **Lean:** every test must earn its place by covering a meaningful path. No trivial tests (issubclass checks, json.dumps wrappers, constant assertions). No tests of library or built-in functionality
- **No duplication:** shared protocol logic is tested once in the base class test file, not repeated per subclass. Per-subclass tests cover only subclass-specific behavior (defaults, overrides)
- **Complete coverage of value paths:** every error path, edge case, and branching condition that could fail in production

## Tool design principles

MCP tools handle live score interaction (MuseScore, Dorico, or Sibelius):

1. **Connection** — manage WebSocket bridges to MuseScore, Dorico, and Sibelius
2. **Analysis** — read and understand musical content from the live score
3. **Manipulation** — modify the live score (barlines, chords, keys, tempo, transpose, undo)

Score generation is handled by the `score-generate` skill — Claude writes music21 scripts directly, giving full API access without an MCP bottleneck.

## Key technical decisions

- **MusicXML** as interchange format (not .mscz/.mscx — undocumented and version-fragile)
- **music21** for programmatic score generation (handles transposing instruments, voice leading, MusicXML export)
- **Skill over MCP for generation** — fewer round-trips, full API access, better results
- **WebSocket bridge** to MuseScore via QML plugin for live manipulation
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
