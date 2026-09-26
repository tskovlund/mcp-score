"""Integration tests: ``render_score`` against a real MuseScore Studio install.

Requires ``MCP_SCORE_INTEGRATION=1``, ``MCP_SCORE_MUSESCORE_PATH`` pointing
at the MuseScore executable and, on Linux, an X display
(``xvfb-run -a pytest tests/integration/test_musescore_render.py``).
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from mcp_score.tools import ToolError
from mcp_score.tools.render import render_score

if TYPE_CHECKING:
    from pathlib import Path

    from mcp_score.tools.render import RenderedScore

pytestmark = pytest.mark.integration

# Leading bytes that identify each rendered file format.
_PDF_MAGIC = b"%PDF"
_MIDI_MAGIC = b"MThd"


async def _render(
    input_path: Path, render_format: str, output_path: Path | None = None
) -> RenderedScore:
    """Call the tool with string paths, as an MCP client would."""
    return await render_score(
        str(input_path),
        format=render_format,
        output_path=None if output_path is None else str(output_path),
    )


class TestRenderScoreWithMuseScore:
    @pytest.mark.anyio()
    @pytest.mark.parametrize(
        ("render_format", "extension", "magic"),
        [("pdf", ".pdf", _PDF_MAGIC), ("midi", ".mid", _MIDI_MAGIC)],
    )
    async def test_render_to_output_path_writes_file_of_that_format(
        self,
        fixture_score: Path,
        tmp_path: Path,
        render_format: str,
        extension: str,
        magic: bytes,
    ) -> None:
        # Arrange
        output_path = tmp_path / f"rendered{extension}"

        # Act
        response = await _render(fixture_score, render_format, output_path)

        # Assert
        assert response.output_path == str(output_path)
        assert response.output_files == [str(output_path)]
        assert response.format == render_format
        assert output_path.stat().st_size > 0
        assert output_path.read_bytes().startswith(magic)

    @pytest.mark.anyio()
    async def test_render_without_output_path_writes_next_to_input(
        self, fixture_score: Path, tmp_path: Path
    ) -> None:
        # Arrange: copy the fixture so the default output lands in tmp_path.
        input_path = tmp_path / "piece.musicxml"
        shutil.copyfile(fixture_score, input_path)

        # Act
        response = await _render(input_path, "pdf")

        # Assert
        expected_output = tmp_path / "piece.pdf"
        assert response.output_path == str(expected_output)
        assert expected_output.read_bytes().startswith(_PDF_MAGIC)

    @pytest.mark.anyio()
    async def test_render_musicxml_over_input_raises_and_keeps_input(
        self, fixture_score: Path, tmp_path: Path
    ) -> None:
        # Arrange: the default output for "musicxml" is the input path itself.
        input_path = tmp_path / "piece.musicxml"
        shutil.copyfile(fixture_score, input_path)
        original_content = input_path.read_bytes()

        # Act
        with pytest.raises(ToolError, match="overwrite the input file"):
            await _render(input_path, "musicxml")

        # Assert
        assert input_path.read_bytes() == original_content
