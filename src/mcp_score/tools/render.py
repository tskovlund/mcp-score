"""Rendering tools — export score files through the MuseScore command line."""

from __future__ import annotations

from pathlib import Path

from mcp_score.app import mcp
from mcp_score.musescore.cli import (
    MUSESCORE_PATH_ENV_VAR,
    MuseScoreNotFoundError,
    RenderError,
    render,
)
from mcp_score.tools import to_json

__all__: list[str] = []

# Output file extension for each supported format. MuseScore picks the
# export format from the extension of the output path.
_FORMAT_EXTENSIONS: dict[str, str] = {
    "pdf": ".pdf",
    "png": ".png",
    "midi": ".mid",
    "mp3": ".mp3",
    "wav": ".wav",
    "musicxml": ".musicxml",
}


def _validate(input_file: Path, format: str, output_file: Path | None) -> str | None:
    """Return an error message for invalid arguments, else ``None``."""
    if not input_file.is_file():
        return f"Input file not found: {input_file}"
    if format not in _FORMAT_EXTENSIONS:
        supported = ", ".join(_FORMAT_EXTENSIONS)
        return f"Unsupported format {format!r}. Supported formats: {supported}."
    if output_file is not None:
        expected_extension = _FORMAT_EXTENSIONS[format]
        if output_file.suffix.lower() != expected_extension:
            return (
                f"output_path must end with {expected_extension} "
                f"for format {format!r}: {output_file}"
            )
        if not output_file.parent.is_dir():
            return f"Output directory does not exist: {output_file.parent}"
    return None


@mcp.tool()
async def render_score(
    input_path: str, format: str = "pdf", output_path: str | None = None
) -> str:
    """Render a score file to PDF, PNG, MIDI, MP3, WAV or MusicXML.

    Runs the MuseScore Studio 4 command line, so MuseScore Studio 4 must be
    installed. It does not need to be running, and no plugin or live
    connection is required. The input is typically a MusicXML file
    (.musicxml, .xml, .mxl) but can be any file MuseScore opens, such as
    .mscz or .mid.

    MuseScore is located from the MCP_SCORE_MUSESCORE_PATH environment
    variable, then PATH (mscore, musescore, mscore4portable, MuseScore4),
    then the platform default install location (macOS app bundle, Windows
    Program Files, Linux Flatpak). If it is not found automatically, set
    MCP_SCORE_MUSESCORE_PATH to the executable in the MCP server's
    environment.

    Args:
        input_path: Path to the score file to render.
        format: One of "pdf", "png", "midi", "mp3", "wav", "musicxml"
            (default: pdf). PNG export writes one file per page, named
            with a -1, -2, ... suffix before the extension.
        output_path: Where to write the result. Defaults to the input path
            with the format's extension. Its extension must match the
            format. An existing file is overwritten.
    """
    input_file = Path(input_path)
    output_file = Path(output_path) if output_path is not None else None
    error = _validate(input_file, format, output_file)
    if error is not None:
        return to_json({"error": error})
    if output_file is None:
        output_file = input_file.with_suffix(_FORMAT_EXTENSIONS[format])
    if output_file.resolve() == input_file.resolve():
        return to_json(
            {"error": f"Output path would overwrite the input file: {input_file}"}
        )

    try:
        await render(input_file, output_file)
    except MuseScoreNotFoundError as exception:
        return to_json(
            {
                "error": f"{exception} Rendering needs MuseScore Studio 4; "
                f"point {MUSESCORE_PATH_ENV_VAR} at its executable if it is "
                "installed somewhere unusual."
            }
        )
    except RenderError as exception:
        return to_json({"error": f"Rendering failed: {exception}"})

    return to_json({"success": True, "output_path": str(output_file), "format": format})
