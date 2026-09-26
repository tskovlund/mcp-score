"""Headless rendering through the MuseScore command line.

MuseScore Studio 4 can convert any file it opens to PDF, PNG, MIDI, audio or
MusicXML from the command line (``mscore -o out.pdf in.musicxml``). This
module runs it as a subprocess; no plugin or WebSocket connection is
involved.

Success is judged by the files MuseScore writes, not by its exit status
alone: MuseScore Studio 4.7 on macOS 26 completes a PDF export and then
aborts while shutting down, and a rendering that produced its output is
a rendering that worked.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import platform
from typing import TYPE_CHECKING, NamedTuple

from mcp_score.musescore.executable import find_musescore_command

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["RENDER_TIMEOUT_SECONDS", "RenderError", "RenderResult", "render"]

logger = logging.getLogger(__name__)

RENDER_TIMEOUT_SECONDS = 120.0

# Qt platform plugin that lets MuseScore run without a display server.
_QT_PLATFORM_ENV_VAR = "QT_QPA_PLATFORM"
_QT_OFFSCREEN_PLATFORM = "offscreen"

# How many trailing lines of MuseScore's stderr to include in error messages.
_STDERR_TAIL_LINES = 20


class RenderError(RuntimeError):
    """Raised when MuseScore fails to render a file."""


class RenderResult(NamedTuple):
    """What a rendering produced."""

    output_files: tuple[Path, ...]
    """The files MuseScore wrote: one, or one per page for PNG (``name-1.png``)."""

    warning: str | None
    """Set when MuseScore wrote the output but did not exit cleanly afterwards."""


def _subprocess_environment() -> dict[str, str]:
    """Build the environment for MuseScore, headless on Linux."""
    environment = os.environ.copy()
    if platform.system() == "Linux":
        environment.setdefault(_QT_PLATFORM_ENV_VAR, _QT_OFFSCREEN_PLATFORM)
    return environment


def _stderr_tail(stderr: bytes) -> str:
    """Return the last few lines of captured stderr, decoded leniently."""
    lines = stderr.decode("utf-8", errors="replace").strip().splitlines()
    return "\n".join(lines[-_STDERR_TAIL_LINES:])


def _with_stderr_tail(message: str, stderr: bytes) -> str:
    stderr_tail = _stderr_tail(stderr)
    return f"{message}\n{stderr_tail}" if stderr_tail else message


# A file's modification time and size, or ``None`` while it does not exist.
type _FileState = tuple[int, int] | None


def _output_candidates(output_path: Path) -> set[Path]:
    """*output_path* and the numbered series MuseScore writes for multi-page formats."""
    series = f"{glob.escape(output_path.stem)}-[0-9]*{glob.escape(output_path.suffix)}"
    return {output_path, *output_path.parent.glob(series)}


def _file_states(files: set[Path]) -> dict[Path, _FileState]:
    states: dict[Path, _FileState] = {}
    for file in files:
        try:
            stat = file.stat()
        except FileNotFoundError:
            states[file] = None
        else:
            states[file] = (stat.st_mtime_ns, stat.st_size)
    return states


def _written_outputs(
    output_path: Path, before: dict[Path, _FileState]
) -> tuple[Path, ...]:
    """The output files that exist now and were created or changed since *before*."""
    after = _file_states(_output_candidates(output_path))
    return tuple(
        sorted(
            file
            for file, state in after.items()
            if state is not None and state != before.get(file)
        )
    )


async def render(input_path: Path, output_path: Path) -> RenderResult:
    """Convert *input_path* to *output_path* with the MuseScore command line.

    MuseScore infers the output format from the extension of *output_path*.
    An existing output file is overwritten. The rendering succeeded when
    MuseScore wrote the output; an unclean exit after that is reported as
    a warning on the result rather than as a failure.

    Raises:
        MuseScoreNotFoundError: If no executable can be found (see
            :mod:`mcp_score.musescore.executable`).
        RenderError: If MuseScore wrote no output or exceeds the timeout.
    """
    command = find_musescore_command()
    arguments = [*command, "-f", "-o", str(output_path), str(input_path)]
    before = _file_states(_output_candidates(output_path))
    process = await asyncio.create_subprocess_exec(
        *arguments,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        env=_subprocess_environment(),
    )
    try:
        _, stderr = await asyncio.wait_for(
            process.communicate(), timeout=RENDER_TIMEOUT_SECONDS
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        error_message = (
            f"MuseScore did not finish within {RENDER_TIMEOUT_SECONDS:.0f} seconds."
        )
        raise RenderError(error_message) from None

    output_files = _written_outputs(output_path, before)
    if not output_files:
        outcome = (
            "exited normally but wrote no output file"
            if process.returncode == 0
            else f"exited with code {process.returncode}"
        )
        raise RenderError(_with_stderr_tail(f"MuseScore {outcome}.", stderr))

    warning = None
    if process.returncode != 0:
        warning = (
            "MuseScore wrote the output but then exited with code "
            f"{process.returncode}."
        )
        logger.warning("%s", _with_stderr_tail(warning, stderr))
    return RenderResult(output_files, warning)
