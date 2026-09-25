# Contributing to mcp-score

Thanks for your interest in contributing! This guide covers everything you need to get started.

## Prerequisites

- **Python 3.14+**
- **[Devbox](https://www.jetify.com/devbox)** (recommended) or manually install `uv`, `ruff`, `pyright`
- **MuseScore Studio 4.4.2+** — only for the live features (the QML plugin, `render_score`) and the integration tests. Everything else runs without it

## Development setup

```bash
git clone https://github.com/tskovlund/mcp-score.git
cd mcp-score

# Option A: devbox + direnv (recommended)
direnv allow

# Option B: devbox shell
devbox shell

# Option C: manual (if not using devbox)
uv venv --python python3.14
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

Markdown is formatted with Prettier; CI checks it, so run `npx prettier --write "**/*.md"` on the files you touch.

## Code style

Follow the code standards in [CONVENTIONS.md](CONVENTIONS.md) — code quality,
testing, commit conventions, and Python-specific rules are all defined there.

**Devbox commit gotcha:** When committing through devbox (`devbox run -- git
commit`), write multi-line messages to a temp file and use `git commit -F
/tmp/msg.txt` instead of `-m` with a HEREDOC — devbox can produce literal `\n`
otherwise.

## Tests

```bash
pytest                    # run all tests
pytest tests/test_cli.py  # run specific test file
pytest -k "test_install"  # run tests matching pattern
```

### Integration tests

`tests/integration/` runs the real thing against MuseScore Studio: the
headless `render_score` export and the live plugin bridge. The tests are
marked `integration` and skip unless `MCP_SCORE_INTEGRATION=1` is set, so the
plain `pytest` run stays fast and offline. CI runs them in the `Integration`
workflow on Linux (MuseScore 4.4, 4.6 and 4.7), Windows and macOS.

`scripts/musescore_harness.py` installs MuseScore and drives it on all three
platforms (Linux needs `xvfb`, `xdotool` and the Qt runtime libraries listed
in `.github/workflows/integration.yml`):

```bash
# 1. Download MuseScore into the cache (prints the executable)
export MCP_SCORE_MUSESCORE_PATH="$(uv run scripts/musescore_harness.py install)"

# 2. Headless export tests (on Linux, MuseScore needs an X display even for export)
MCP_SCORE_INTEGRATION=1 xvfb-run -a pytest tests/integration/test_musescore_render.py

# 3. Live bridge tests: start MuseScore with the plugin listening on :8765
uv run scripts/musescore_harness.py start tests/integration/fixtures/fixture.musicxml
MCP_SCORE_INTEGRATION=1 pytest tests/integration/test_musescore_bridge.py
uv run scripts/musescore_harness.py stop
```

`start` overwrites MuseScore's user configuration (plugin, shortcut,
first-launch flags), so use a throwaway `HOME` on a machine where you use
MuseScore yourself. The version defaults to the newest one in
`tests/integration/musescore-versions.json`, the file the workflow matrix reads
and Renovate keeps current; `MUSESCORE_VERSION` picks another. The harness
looks the release asset up through the GitHub releases API (set
`GITHUB_TOKEN` to raise the rate limit) unless `MUSESCORE_DOWNLOAD_URL` names
it, and keeps downloads in `MUSESCORE_CACHE_DIR`.

## PR process

All contributions go through pull requests — **do not push directly to `main`**.
Keep each PR to one change; small PRs get reviewed and merged faster.

1. Fork or create a feature branch from `main`
2. Make your changes
3. Ensure `devbox run check` passes
4. Push and create a pull request
5. CI must pass: lint, format, typecheck, tests, Markdown formatting (Prettier)
   and the integration tests against real MuseScore
6. A maintainer will review your PR — address any feedback
7. The maintainer squash-merges once approved

Much of this project is written with Claude Code, and that is fine for
contributions too. Every PR is reviewed by the maintainer before merge, so
say what you tested and how.

Releases follow [semver](https://semver.org/); versions stay 0.x until the
tool set is stable, so minor releases may still change tool names and
parameters.

### Cutting a release

1. Open a release PR: bump `version` in `pyproject.toml`, move the
   `Unreleased` entries in `CHANGELOG.md` under the new version with the date,
   and update anything else that names the version. Merge it.
2. Tag the merge commit and push the tag: `git tag -a vX.Y.Z -m "mcp-score-server X.Y.Z"`
   then `git push origin vX.Y.Z`. Tags are signed and protected.
3. The `Release` workflow builds the package, publishes it to PyPI through the
   `pypi` environment (approve the deployment when asked) and creates a
   **draft** GitHub release with generated notes and the build artifacts.
4. Edit the draft into authored release notes (the changelog section is the
   source) and publish it. Published releases are immutable, so review before
   publishing.

### Prompt request PRs

We welcome **prompt request PRs** — pull requests that contain a well-described
specification instead of code. These are designed to be implemented by AI agents.

A prompt request PR should include:

- **Clear problem statement** — what should change and why
- **Acceptance criteria** — specific, testable outcomes
- **Constraints** — any boundaries on the solution (e.g. "must not break existing
  API", "should use music21's built-in transposition")
- **Examples** — input/output examples or before/after descriptions where helpful

Label prompt request PRs with `prompt-request`. A maintainer or AI agent will
pick them up, implement the changes, and push commits to the PR branch. The
normal review process applies after implementation.

## Project structure

```
src/mcp_score/
  cli.py              CLI entry point (serve, run, install, install-skill, install-plugin)
  server.py           create_server(): builds the MCPServer and registers every tool module
  resources.py        Locate bundled files (skill directory, plugin.qml)
  tools/
    __init__.py       Shared tool plumbing: ToolError, score_tool, bridge and measure guards
    connection.py     Connect/disconnect MuseScore & Dorico, ping, score info
    analysis.py       Score reading tools (read_passage, get_measure_content, get_selection_properties)
    generate.py       Score generation tools (generate_score, score_generation_guide) and the score-generate prompt
    manipulation.py   Score modification tools (notes, dynamics, barlines, chords, keys, time, tempo, measures, transpose, undo)
    render.py         render_score: export through the MuseScore command line
  bridge/
    base.py           ScoreBridge abstract interface, CommandResult, NoteDuration
    websocket.py      WebSocketTransport and WebSocketBridge (connection lifecycle, reconnect)
    remote_control.py Remote Control protocol layer (used by Dorico)
    musescore.py      MuseScore plugin protocol (thin subclass of WebSocketBridge)
    dorico.py         Dorico defaults (thin subclass of RemoteControlBridge, experimental)
    registry.py       BridgeRegistry: the bridges and which one is active
  musescore/
    paths.py          Where MuseScore keeps user files (plugins directory)
    headless.py       MuseScore executable discovery and headless rendering
    plugin.qml        MuseScore QML plugin (WebSocket server)

.claude/skills/
  score-generate/     Claude Code skill for music21 score generation
    SKILL.md          Skill definition and instructions
    references/
      instruments.md  music21 instrument class reference
      template.py     Complete, runnable generation script to start from

scripts/
  musescore_harness.py  Installs and drives a real MuseScore for the integration tests

tests/                One test file per module
tests/integration/    Tests against a real MuseScore (opt-in, see above)
docs/                 Diataxis-structured documentation
```

## Skill development

The `score-generate` skill (`.claude/skills/score-generate/SKILL.md`) teaches Claude to write music21 Python scripts. To modify it:

1. Edit `SKILL.md` or files in `references/`
2. Test by running `mcp-score install-skill` and asking Claude Code to generate a score
3. Common changes: adding instrument examples, fixing music21 API gotchas, updating the template

The skill is bundled with the pip package so users can install it with `mcp-score install-skill`. The `score_generation_guide` tool and the `score-generate` MCP prompt serve the same files to other MCP clients, so a change to the skill reaches every client.

## Architecture decisions

- **MusicXML** as interchange format (not `.mscz`/`.mscx`, which are undocumented and version-fragile)
- **music21** for programmatic score generation
- **Skill in Claude Code, tools for other clients** — one script per score beats dozens of tool calls; `generate_score` and `score_generation_guide` give every MCP client the same workflow from the same skill text
- **MCP for live manipulation** — WebSocket bridge to MuseScore Studio 4.4.2+ through a QML plugin built on MuseScore's built-in plugin WebSocket API; older MuseScore is not supported
- **Dorico is experimental** (undocumented, command-only Remote Control API, unverified); **Sibelius was removed** as out of scope
- **Integration tests against real MuseScore** in CI, on several versions and all three platforms
- **Semver, 0.x until stable**
- **Python** — music21 is Python-only and the MCP SDK has first-class Python support

See [docs/architecture.md](docs/architecture.md) for the full rationale and
[issue #91](https://github.com/tskovlund/mcp-score/issues/91) for the decision
ledger behind the beta.
