# Contributing to mcp-score

Thanks for your interest in contributing! This guide covers everything you need to get started.

## Prerequisites

- **Python 3.14+**
- **[Devbox](https://www.jetify.com/devbox)** (recommended) or manually install `uv`, `ruff`, `pyright`
- **MuseScore Studio 4** — only for `render_score`, the live plugin (which needs 4.4.2 or later) and the integration tests. Everything else runs without it

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

`docs/reference.md` is generated from the tool docstrings, input schemas and
the CLI parser; a test fails when it drifts. After changing a tool, run
`uv run scripts/generate_reference.py` and commit the result. Tool docstrings
are what MCP clients see, so write the reference there.

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
workflow: on Linux against the versions in `tests/integration/musescore-versions.json` (the oldest supported line, one in between and the newest), and on Windows and macOS against the newest.

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

`start` rewrites MuseScore's user configuration: it installs the plugin,
replaces `extensions/config.json` (other plugins end up disabled) and
`shortcuts.xml` (custom shortcuts are lost), sets the startup preferences that
suppress the first-launch and welcome dialogs, and deletes the saved session.
Use a throwaway `HOME` on a machine where you use MuseScore yourself.

The harness reads these environment variables:

| Variable                 | Meaning                                                                                                              |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `MUSESCORE_VERSION`      | Release to install; defaults to the newest in `tests/integration/musescore-versions.json`                            |
| `MUSESCORE_DOWNLOAD_URL` | Asset to download; otherwise the release is looked up through the GitHub releases API                                |
| `GITHUB_TOKEN`           | Raises the GitHub API rate limit for that lookup                                                                     |
| `MUSESCORE_CACHE_DIR`    | Where downloads and the unpacked application live; defaults to `~/.cache/mcp-score/musescore-<version>`              |
| `MUSESCORE_DISPLAY`      | Linux only: the Xvfb display the GUI runs on, default `:87` (not `:99`, which `xvfb-run` takes for the render tests) |

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

Release notes live on the [Releases page](https://github.com/tskovlund/mcp-score/releases);
there is no changelog file. Conventional commit messages are the raw material:
with squash merges, every commit on `main` is one typed line, and the release
workflow turns them into a draft.

1. Open a release PR that bumps `version` in `pyproject.toml`. Merge it.
2. Tag the merge commit and push the tag: `git tag -a vX.Y.Z -m "mcp-score-server X.Y.Z"`
   then `git push origin vX.Y.Z`. Tags are signed and protected.
3. The `Release` workflow builds the package, publishes it to PyPI through the
   `pypi` environment (approve the deployment when asked) and creates a
   **draft** GitHub release with the build artifacts and notes drafted by
   [git-cliff](https://git-cliff.org/) from the commits since the previous tag,
   grouped by type (`cliff.toml`).
4. Curate the draft into authored release notes and publish it. Published
   releases are immutable, so review before publishing.

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

The package layout, with a line per module, is in [docs/architecture.md](docs/architecture.md#package-structure). Tests live in `tests/`, grouped by concern; `tests/integration/` holds the opt-in tests against a real MuseScore.

## Skill development

The `score-generate` skill (`.claude/skills/score-generate/SKILL.md`) teaches Claude to write music21 Python scripts. To modify it:

1. Edit `SKILL.md` or files in `references/`
2. Test by running `mcp-score install-skill` and asking Claude Code to generate a score
3. Common changes: adding instrument examples, fixing music21 API gotchas, updating the template

The skill is bundled with the pip package so users can install it with `mcp-score install-skill`. The `score_generation_guide` tool and the `score-generate` MCP prompt serve the same files to other MCP clients, so a change to the skill reaches every client.

## Architecture decisions

The rationale is in [docs/architecture.md](docs/architecture.md#key-design-decisions); the decision ledger behind the beta is [issue #91](https://github.com/tskovlund/mcp-score/issues/91). Check both before reopening a settled question.
