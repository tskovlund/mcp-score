"""Generation tools — run music21 scripts and serve the score-generate guide.

These make score generation available in any MCP client, not only Claude
Code (where the bundled `score-generate` skill covers the same job).
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from mcp_score.bridge.results import Result
from mcp_score.guide import load_guide
from mcp_score.tools import ToolError, score_tool

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

__all__ = ["register"]

# ── Constants ─────────────────────────────────────────────────────────

DEFAULT_TIMEOUT_SECONDS: float = 120.0
"""How long a generation script may run before it is killed."""

STDERR_TAIL_LINES: int = 40
"""Number of trailing stderr lines returned when a script fails."""

SCRIPT_FILENAME = "generate_score.py"
"""Name of the temp file the script is written to (shown in tracebacks)."""

OUTPUT_DIRECTORY_PREFIX = "mcp-score-"
"""Prefix of the fresh directory created per run when no output_dir is given."""

PROMPT_NAME = "score-generate"
"""Name of the MCP prompt that serves the generation guide."""


class GeneratedScore(Result):
    output_files: list[str]
    """Absolute paths of the files the script created in its working directory."""
    stdout: str


# ── Helpers ───────────────────────────────────────────────────────────


def _default_output_directory() -> Path:
    """Create a fresh directory for this run's output files.

    Matches the skill's default output location: the user's Desktop when it
    exists, otherwise the home directory.
    """
    desktop = Path.home() / "Desktop"
    base = desktop if desktop.is_dir() else Path.home()
    return Path(tempfile.mkdtemp(prefix=OUTPUT_DIRECTORY_PREFIX, dir=base))


def _resolve_output_directory(output_dir: str | None) -> Path:
    """The working directory for a run, created if needed.

    Raises:
        ToolError: When *output_dir* exists but is not a directory.
    """
    if output_dir is None:
        return _default_output_directory()
    directory = Path(output_dir).expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise ToolError(f"output_dir is not a directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _list_files(directory: Path) -> set[Path]:
    """Snapshot the files directly inside *directory*."""
    return {entry for entry in directory.iterdir() if entry.is_file()}


def _stderr_tail(stderr: str) -> str:
    """Return the last STDERR_TAIL_LINES lines of *stderr*."""
    lines = stderr.splitlines()
    return "\n".join(lines[-STDERR_TAIL_LINES:])


# ── Tools ─────────────────────────────────────────────────────────────


@score_tool
async def generate_score(
    script: str,
    output_dir: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> GeneratedScore:
    """Run a music21 Python script to generate a score file (MusicXML).

    Write a COMPLETE, self-contained music21 script that builds the whole
    score and ends by exporting it, e.g.
    `score.write("musicxml", fp="My Piece.musicxml")`. Use a plain file
    name (no directory) so the file lands in the working directory and is
    reported back in `output_files`. Read the `score_generation_guide`
    tool first: it holds the music21 conventions this project relies on
    (flats are written `B-` not `Bb`, metadata, repeats, volta brackets,
    transposing instruments, and a full template).

    The script runs on the user's machine with the user's privileges, in the
    same Python interpreter as this server (so music21 is importable).
    Only send code the user would be comfortable running themselves.

    Args:
        script: Complete Python source of the generation script.
        output_dir: Working directory for the run. Defaults to a fresh
            directory under the user's Desktop (or home directory when there
            is no Desktop). Created if it does not exist.
        timeout: Seconds to wait before killing the script (default: 120).

    A script that fails is a tool error whose message ends with the last
    lines of its stderr.
    """
    working_directory = _resolve_output_directory(output_dir)
    files_before = _list_files(working_directory)

    with tempfile.TemporaryDirectory(prefix=OUTPUT_DIRECTORY_PREFIX) as script_dir:
        script_path = Path(script_dir) / SCRIPT_FILENAME
        script_path.write_text(script, encoding="utf-8")

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script_path),
            cwd=working_directory,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            raise ToolError(
                f"Script timed out after {timeout} seconds and was killed."
            ) from None

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if process.returncode != 0:
        raise ToolError(
            f"Script exited with code {process.returncode}.\n{_stderr_tail(stderr)}"
        )

    new_files = sorted(_list_files(working_directory) - files_before)
    return GeneratedScore(output_files=[str(path) for path in new_files], stdout=stdout)


def score_generation_guide() -> str:
    """Return the score generation guide for writing music21 scripts.

    Read this before calling `generate_score`. It is the bundled
    `score-generate` skill (instructions, music21 conventions and
    troubleshooting), the instrument class reference (which class to use for
    each instrument, with transposition handled by music21), and a complete
    runnable template script. Takes no parameters.

    Returns the guide as Markdown.
    """
    try:
        return load_guide()
    except FileNotFoundError as exception:
        raise ToolError(str(exception)) from None


# ── Prompt ────────────────────────────────────────────────────────────


def score_generate_prompt() -> str:
    """Serve the generation guide as a prompt for clients that support them."""
    return load_guide()


def register(server: MCPServer) -> None:
    server.tool()(generate_score)
    server.tool()(score_generation_guide)
    server.prompt(
        name=PROMPT_NAME,
        title="Score generation guide",
        description=(
            "Load the score-generate instructions (music21 conventions, "
            "instrument reference and template) before generating a score "
            "with generate_score."
        ),
    )(score_generate_prompt)
