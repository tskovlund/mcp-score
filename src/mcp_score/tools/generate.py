"""Generation tools — run music21 scripts and serve the score-generate guide.

These make score generation available in any MCP client, not only Claude
Code (where the bundled ``score-generate`` skill covers the same job).
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from mcp_score.bridge import CommandResult
from mcp_score.resources import SKILL_DIRECTORY, package_path
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

_GUIDE_FILES: tuple[Path, ...] = (
    Path("SKILL.md"),
    Path("references") / "instruments.md",
    Path("references") / "template.py",
)
"""Skill files concatenated into the guide, relative to the skill directory."""

_GUIDE_PREAMBLE = """\
# Score generation guide

This is the bundled `score-generate` skill that Claude Code uses, served so
any MCP client can follow the same instructions.

When you read this through MCP, replace the skill's "save to /tmp and run
`mcp-score run`" steps with the `generate_score` tool: pass the complete
music21 script as the `script` argument. The tool runs it in a working
directory of its own and returns the absolute paths of the files it created,
so end the script with `score.write("musicxml", fp="<Title>.musicxml")`
(a plain file name, relative to the working directory).
"""


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


def _load_guide() -> str:
    """Concatenate the skill files into one guide document.

    Raises FileNotFoundError when the bundled skill files are missing.
    """
    skill_directory = package_path(str(SKILL_DIRECTORY))
    sections: list[str] = [_GUIDE_PREAMBLE]
    for relative_path in _GUIDE_FILES:
        file_path = skill_directory / relative_path
        if not file_path.is_file():
            error_message = f"Cannot find bundled skill file: {file_path}"
            raise FileNotFoundError(error_message)
        content = file_path.read_text(encoding="utf-8")
        if file_path.suffix == ".py":
            content = f"```python\n{content}\n```"
        sections.append(f"---\n\n# {relative_path.as_posix()}\n\n{content}")
    return "\n\n".join(sections)


# ── Tools ─────────────────────────────────────────────────────────────


@score_tool
async def generate_score(
    script: str,
    output_dir: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> CommandResult:
    """Run a music21 Python script to generate a score file (MusicXML).

    Write a COMPLETE, self-contained music21 script that builds the whole
    score and ends by exporting it, e.g.
    ``score.write("musicxml", fp="My Piece.musicxml")``. Use a plain file
    name (no directory) so the file lands in the working directory and is
    reported back in ``output_files``. Read the ``score_generation_guide``
    tool first: it holds the music21 conventions this project relies on
    (flats are written ``B-`` not ``Bb``, metadata, repeats, volta brackets,
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

    Returns:
        JSON. On success: ``{"success": true, "output_files": [absolute paths
        of files created in the working directory], "stdout": ...}``. On
        failure: ``{"error": ..., "stderr": last lines, "returncode": n}``.
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
                f"Script timed out after {timeout} seconds and was killed.",
                stderr="",
                returncode=process.returncode,
            ) from None

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if process.returncode != 0:
        raise ToolError(
            f"Script exited with code {process.returncode}.",
            stderr=_stderr_tail(stderr),
            returncode=process.returncode,
        )

    new_files = sorted(_list_files(working_directory) - files_before)
    return {
        "success": True,
        "output_files": [str(path) for path in new_files],
        "stdout": stdout,
    }


def score_generation_guide() -> str:
    """Return the score generation guide for writing music21 scripts.

    Read this before calling ``generate_score``. It is the bundled
    ``score-generate`` skill (instructions, music21 conventions and
    troubleshooting), the instrument class reference (which class to use for
    each instrument, with transposition handled by music21), and a complete
    runnable template script. Takes no parameters.

    Returns the guide as Markdown, or ``{"error": ...}`` JSON if the bundled
    skill files cannot be found.
    """
    try:
        return _load_guide()
    except FileNotFoundError as exception:
        return json.dumps({"error": str(exception)})


# ── Prompt ────────────────────────────────────────────────────────────


def score_generate_prompt() -> str:
    """Serve the generation guide as a prompt for clients that support them."""
    return _load_guide()


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
