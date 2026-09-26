# mcp-score

AI-driven music score generation and manipulation, for any MCP client. Three jobs:

- **Score generation** — the assistant writes a music21 Python script that exports MusicXML. In Claude Code the bundled `score-generate` skill (`.claude/skills/score-generate/`) drives this without MCP. In other clients the `generate_score` tool runs the script and `score_generation_guide` (also the `score-generate` MCP prompt) serves the same instructions.
- **Live score manipulation** via MCP server — reads from and writes to a running MuseScore Studio 4.4.2+ (or experimentally Dorico) via WebSocket bridge.
- **Rendering** — `render_score` exports PDF, PNG, MIDI, audio or MusicXML through the MuseScore command line.

Follow the code standards in [CONVENTIONS.md](CONVENTIONS.md).

## Architecture

```
src/mcp_score/
  cli.py              CLI entry point (serve, run, install, install-skill, install-plugin)
  server.py           MCP server entry point: create_server() registers every tool module
  resources.py        Locate bundled files (skill directory, plugin.qml)
  tools/
    __init__.py       Shared tool plumbing: ToolError, score_tool, bridge and measure guards
    connection.py     Connect/disconnect MuseScore & Dorico, ping, score info
    analysis.py       Read passages and measures from live score
    manipulation.py   Modify live score (notes, rehearsal marks, dynamics, chords, barlines, keys, time, tempo, measures, transpose, undo)
    generate.py       Run music21 scripts and serve the score-generate guide (any MCP client)
    render.py         Export score files through the MuseScore command line
  bridge/
    base.py           ScoreBridge abstract interface, CommandResult, NoteDuration
    websocket.py      WebSocketTransport and WebSocketBridge (connection lifecycle, reconnect)
    remote_control.py Remote Control protocol layer (used by Dorico)
    musescore.py      MuseScore plugin protocol on WebSocketBridge
    dorico.py         Dorico defaults (thin subclass of RemoteControlBridge, experimental)
    registry.py       BridgeRegistry: the bridges and which one is active
  musescore/
    paths.py          Where MuseScore keeps user files (plugins directory)
    headless.py       MuseScore executable discovery and headless rendering
    plugin.qml        MuseScore QML plugin (WebSocket server inside MuseScore)

.claude/skills/
  score-generate/     Claude Code skill for score generation via music21
    SKILL.md
    references/       instruments.md, template.py

scripts/
  musescore_harness.py  Installs and drives a real MuseScore for integration tests

tests/                pytest tests, grouped by concern, offline
tests/integration/    Tests against a real MuseScore (opt-in, MCP_SCORE_INTEGRATION=1)
docs/                 Diataxis-structured documentation
```

### Why a skill and tools for generation?

One music21 script per score beats dozens of tool calls. Claude Code runs the skill directly; `generate_score` and `score_generation_guide` give every other MCP client the same script from the same skill text. Live manipulation needs a persistent connection and state, which is what MCP tools are for. Details: [docs/architecture.md](docs/architecture.md).

## Dev environment

Devbox + uv. Devbox provides Python 3.14, uv, ruff, pyright via Nix. uv manages Python packages in `.venv/`.

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

Integration tests against a real MuseScore are opt-in; see [CONTRIBUTING.md](CONTRIBUTING.md#integration-tests).

**Multi-line commits:** `devbox run -- git commit -m "$(cat ...)"` produces literal `\n`. Always use `git commit -F /tmp/msg.txt` for multi-line commit messages.

## Repo-specific conventions

- **Conventional commits** — enforced by `.githooks/commit-msg`
- **Thin subclasses over monolithic duplicated implementations** — protocol logic lives in `RemoteControlBridge`; app-specific bridges (Dorico) only override defaults
- **Test non-triviality** — no issubclass checks, json.dumps wrappers, or constant assertions. Every test must cover a meaningful code path
- **Test deduplication** — shared protocol logic is tested once in the base class test file, not repeated per subclass. Per-subclass tests cover only subclass-specific behavior (defaults, overrides)
- **No counts in docs that drift** — no tool, command or test counts in documentation. List things by name or describe them; numbers go stale silently

## Tool design principles

MCP tools fall into these categories:

1. **Connection** — manage WebSocket bridges to MuseScore and Dorico
2. **Analysis** — read and understand musical content from the live score
3. **Manipulation** — modify the live score (notes, rehearsal marks, dynamics, chords, barlines, keys, time signatures, tempo, measures, transpose, undo)
4. **Generation** — run a music21 script (`generate_score`) and serve the skill text (`score_generation_guide`) so clients other than Claude Code get the same workflow
5. **Rendering** — export a score file through the MuseScore command line (`render_score`); needs MuseScore installed, not running

In Claude Code, generation is handled by the `score-generate` skill — Claude writes music21 scripts directly, giving full API access without an MCP bottleneck.

## Key technical decisions

The rationale lives in [docs/architecture.md](docs/architecture.md#key-design-decisions) and the decision ledger in [issue #91](https://github.com/tskovlund/mcp-score/issues/91). The constraints to keep in mind while coding:

- **MuseScore Studio 4.4.2+ only** for the live plugin; older versions lack the plugin WebSocket API. Dorico is experimental; Sibelius is out.
- **MusicXML** is the interchange format; never generate `.mscz`/`.mscx`.
- **PyPI name `mcp-score-server`**; the import package `mcp_score` and the CLI `mcp-score` keep their names.
- **Integration tests run against real MuseScore** in CI on all three platforms; the versions live in `tests/integration/musescore-versions.json`.

## Git workflow

### PR workflow

1. Create feature branch
2. Make changes, test with `pytest` and manual MuseScore testing
3. Push and create PR
4. Review loop: wait for CI -> address review comments -> push -> iterate until clean
5. Squash merge

One small PR per change. Much of the code is written with Claude Code; the maintainer reviews every PR before merge. Versioning is semver, 0.x until stable.

### Issue tracking

GitHub Issues for implementation tracking. Linear for higher-level planning (workspace: tskovlund, project: MCP Music Notation). The decision ledger for the beta is [issue #91](https://github.com/tskovlund/mcp-score/issues/91); check it before re-opening a settled question.

**Templates:** Enhancement, Bug, Research. Use the appropriate template. Blank issues disabled.

**Labels:** `bug`, `enhancement`, `documentation`, `research`, `prompt-request`, `dependencies`, `github actions`
