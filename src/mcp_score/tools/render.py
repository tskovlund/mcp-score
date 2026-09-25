"""Rendering tools: export score files through the MuseScore command line."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mcp_score.bridge import CommandResult
from mcp_score.musescore.headless import (
    MUSESCORE_PATH_ENV_VAR,
    MuseScoreNotFoundError,
    RenderError,
    render,
)
from mcp_score.tools import ToolError, score_tool

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

__all__ = ["register"]

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


def _output_file(input_file: Path, format: str, output_path: str | None) -> Path:
    """Where the rendered file goes, checked against what MuseScore can do.

    Raises:
        ToolError: When the input is missing, the format unknown, the
            output extension wrong for the format, its directory missing,
            or the output would overwrite the input.
    """
    if not input_file.is_file():
        raise ToolError(f"Input file not found: {input_file}")
    extension = _FORMAT_EXTENSIONS.get(format)
    if extension is None:
        supported = ", ".join(_FORMAT_EXTENSIONS)
        raise ToolError(
            f"Unsupported format {format!r}. Supported formats: {supported}."
        )

    if output_path is None:
        output_file = input_file.with_suffix(extension)
    else:
        output_file = Path(output_path)
        if output_file.suffix.lower() != extension:
            raise ToolError(
                f"output_path must end with {extension} for format {format!r}: "
                f"{output_file}"
            )
        if not output_file.parent.is_dir():
            raise ToolError(f"Output directory does not exist: {output_file.parent}")

    if output_file.resolve() == input_file.resolve():
        raise ToolError(f"Output path would overwrite the input file: {input_file}")
    return output_file


@score_tool
async def render_score(
    input_path: str, format: str = "pdf", output_path: str | None = None
) -> CommandResult:
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
    output_file = _output_file(input_file, format, output_path)
    try:
        rendered = await render(input_file, output_file)
    except MuseScoreNotFoundError as exception:
        raise ToolError(
            f"{exception} Rendering needs MuseScore Studio 4; point "
            f"{MUSESCORE_PATH_ENV_VAR} at its executable if it is installed "
            "somewhere unusual."
        ) from None
    except RenderError as exception:
        raise ToolError(f"Rendering failed: {exception}") from None
    result: CommandResult = {
        "success": True,
        "output_path": str(output_file),
        "output_files": [str(file) for file in rendered.output_files],
        "format": format,
    }
    if rendered.warning is not None:
        result["warning"] = rendered.warning
    return result


def register(server: MCPServer) -> None:
    server.tool()(render_score)
