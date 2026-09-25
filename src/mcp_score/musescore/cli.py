"""MuseScore command line — executable discovery and headless rendering.

MuseScore Studio 4 can convert any file it opens to PDF, PNG, MIDI, audio or
MusicXML from the command line (``mscore -o out.pdf in.musicxml``). This
module locates the executable and runs it as a subprocess; no plugin or
WebSocket connection is involved.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
from pathlib import Path

__all__ = [
    "MUSESCORE_PATH_ENV_VAR",
    "RENDER_TIMEOUT_SECONDS",
    "MuseScoreNotFoundError",
    "RenderError",
    "find_musescore_command",
    "render",
]

MUSESCORE_PATH_ENV_VAR = "MCP_SCORE_MUSESCORE_PATH"
RENDER_TIMEOUT_SECONDS = 120.0

# Executable names to look up on PATH, in order of preference.
_PATH_EXECUTABLE_NAMES: tuple[str, ...] = (
    "mscore",
    "musescore",
    "mscore4portable",
    "MuseScore4",
)

# Platform default install locations, consulted when PATH lookup fails.
_MACOS_DEFAULT_EXECUTABLE = Path("/Applications/MuseScore 4.app/Contents/MacOS/mscore")
_WINDOWS_PROGRAM_FILES_ENV_VAR = "ProgramFiles"
_WINDOWS_DEFAULT_PROGRAM_FILES = Path(r"C:\Program Files")
_WINDOWS_EXECUTABLE_RELATIVE_PATH = Path("MuseScore 4") / "bin" / "MuseScore4.exe"
_FLATPAK_APP_ID = "org.musescore.MuseScore"
_FLATPAK_RUN_COMMAND: tuple[str, ...] = ("flatpak", "run", _FLATPAK_APP_ID)
# Flatpak places a launcher for every installed app in one of these directories.
_FLATPAK_EXPORT_DIRECTORIES: tuple[Path, ...] = (
    Path("/var/lib/flatpak/exports/bin"),
    Path.home() / ".local" / "share" / "flatpak" / "exports" / "bin",
)

# Qt platform plugin that lets MuseScore run without a display server.
_QT_PLATFORM_ENV_VAR = "QT_QPA_PLATFORM"
_QT_OFFSCREEN_PLATFORM = "offscreen"

# How many trailing lines of MuseScore's stderr to include in error messages.
_STDERR_TAIL_LINES = 20


class MuseScoreNotFoundError(RuntimeError):
    """Raised when no MuseScore executable can be located."""


class RenderError(RuntimeError):
    """Raised when MuseScore fails to render a file."""


# ── Discovery ─────────────────────────────────────────────────────────


def _command_from_environment() -> list[str] | None:
    """Resolve the executable named by the override environment variable."""
    configured = os.environ.get(MUSESCORE_PATH_ENV_VAR)
    if not configured:
        return None
    if Path(configured).is_file():
        return [configured]
    resolved = shutil.which(configured)
    if resolved is not None:
        return [resolved]
    error_message = (
        f"{MUSESCORE_PATH_ENV_VAR} is set to {configured!r}, "
        "but no such executable exists."
    )
    raise MuseScoreNotFoundError(error_message)


def _command_from_path() -> list[str] | None:
    """Look up the well-known executable names on PATH."""
    for executable_name in _PATH_EXECUTABLE_NAMES:
        resolved = shutil.which(executable_name)
        if resolved is not None:
            return [resolved]
    return None


def _command_from_platform_defaults() -> list[str] | None:
    """Check the default install location for the current platform."""
    system = platform.system()
    if system == "Darwin":
        if _MACOS_DEFAULT_EXECUTABLE.is_file():
            return [str(_MACOS_DEFAULT_EXECUTABLE)]
        return None
    if system == "Windows":
        program_files = Path(
            os.environ.get(
                _WINDOWS_PROGRAM_FILES_ENV_VAR, str(_WINDOWS_DEFAULT_PROGRAM_FILES)
            )
        )
        executable = program_files / _WINDOWS_EXECUTABLE_RELATIVE_PATH
        if executable.is_file():
            return [str(executable)]
        return None
    if system == "Linux":
        flatpak_installed = any(
            (directory / _FLATPAK_APP_ID).exists()
            for directory in _FLATPAK_EXPORT_DIRECTORIES
        )
        if flatpak_installed and shutil.which(_FLATPAK_RUN_COMMAND[0]) is not None:
            return list(_FLATPAK_RUN_COMMAND)
        return None
    return None


def find_musescore_command() -> list[str]:
    """Locate the MuseScore executable and return it as an argv prefix.

    Search order: the ``MCP_SCORE_MUSESCORE_PATH`` environment variable,
    the well-known executable names on PATH, then the platform's default
    install location (macOS app bundle, Windows Program Files, Linux
    Flatpak). The result is a list because the Flatpak launcher is a
    multi-word command (``flatpak run org.musescore.MuseScore``).

    Raises:
        MuseScoreNotFoundError: If no executable can be found.
    """
    for locate in (
        _command_from_environment,
        _command_from_path,
        _command_from_platform_defaults,
    ):
        command = locate()
        if command is not None:
            return command
    error_message = (
        "MuseScore Studio 4 was not found. Install it, or set the "
        f"{MUSESCORE_PATH_ENV_VAR} environment variable to its executable."
    )
    raise MuseScoreNotFoundError(error_message)


# ── Rendering ─────────────────────────────────────────────────────────


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


async def render(input_path: Path, output_path: Path) -> None:
    """Convert *input_path* to *output_path* with the MuseScore command line.

    MuseScore infers the output format from the extension of *output_path*.
    An existing output file is overwritten.

    Raises:
        MuseScoreNotFoundError: If no executable can be found.
        RenderError: If MuseScore exits with an error or exceeds the timeout.
    """
    command = find_musescore_command()
    arguments = [*command, "-f", "-o", str(output_path), str(input_path)]
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

    if process.returncode != 0:
        error_message = f"MuseScore exited with code {process.returncode}."
        stderr_tail = _stderr_tail(stderr)
        if stderr_tail:
            error_message = f"{error_message}\n{stderr_tail}"
        raise RenderError(error_message)
