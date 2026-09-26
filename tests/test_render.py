"""Tests for the render_score tool and the headless rendering it delegates to."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from mcp_score.musescore import headless
from mcp_score.musescore.executable import (
    MUSESCORE_PATH_ENV_VAR,
    MuseScoreNotFoundError,
)
from mcp_score.musescore.headless import RenderError, RenderResult, render
from mcp_score.tools import ToolError
from mcp_score.tools.render import RenderedScore, render_score

_MUSESCORE_COMMAND = ["/opt/musescore/mscore"]


def _mock_process(
    returncode: int = 0, stderr: bytes = b"", writes: tuple[Path, ...] = ()
) -> MagicMock:
    """Build a fake asyncio subprocess that writes *writes* and exits *returncode*."""

    async def communicate() -> tuple[bytes, bytes]:
        for file in writes:
            file.write_bytes(b"rendered")
        return (b"", stderr)

    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(side_effect=communicate)
    process.kill = MagicMock()
    process.wait = AsyncMock()
    return process


def _rendering(*outputs: Path, warning: str | None = None) -> AsyncMock:
    """A stand-in for ``render`` that reports *outputs* as written."""
    return AsyncMock(return_value=RenderResult(outputs, warning))


@pytest.fixture
def score_file(tmp_path: Path) -> Path:
    """A minimal input file for the tool to find on disk."""
    path = tmp_path / "piece.musicxml"
    path.write_text("<score-partwise/>")
    return path


# ── Subprocess runner ─────────────────────────────────────────────────


class TestRender:
    @pytest.mark.anyio()
    async def test_render_invokes_musescore_with_force_and_output(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        output = tmp_path / "out.pdf"
        create_subprocess = AsyncMock(return_value=_mock_process(writes=(output,)))

        with (
            patch.object(
                headless, "find_musescore_command", return_value=_MUSESCORE_COMMAND
            ),
            patch.object(headless.asyncio, "create_subprocess_exec", create_subprocess),
            patch.object(headless.platform, "system", return_value="Linux"),
            patch.dict("os.environ", {}, clear=True),
        ):
            # Act
            result = await render(tmp_path / "in.musicxml", output)

        # Assert
        assert result == RenderResult((output,), None)
        arguments = create_subprocess.call_args.args
        assert arguments == (
            *_MUSESCORE_COMMAND,
            "-f",
            "-o",
            str(tmp_path / "out.pdf"),
            str(tmp_path / "in.musicxml"),
        )
        environment = create_subprocess.call_args.kwargs["env"]
        assert environment["QT_QPA_PLATFORM"] == "offscreen"

    @pytest.mark.anyio()
    async def test_render_on_linux_keeps_user_qt_platform(self, tmp_path: Path) -> None:
        # Arrange
        output = tmp_path / "out.pdf"
        create_subprocess = AsyncMock(return_value=_mock_process(writes=(output,)))

        with (
            patch.object(
                headless, "find_musescore_command", return_value=_MUSESCORE_COMMAND
            ),
            patch.object(headless.asyncio, "create_subprocess_exec", create_subprocess),
            patch.object(headless.platform, "system", return_value="Linux"),
            patch.dict("os.environ", {"QT_QPA_PLATFORM": "xcb"}),
        ):
            # Act
            await render(tmp_path / "in.musicxml", output)

        # Assert
        environment = create_subprocess.call_args.kwargs["env"]
        assert environment["QT_QPA_PLATFORM"] == "xcb"

    @pytest.mark.anyio()
    async def test_render_off_linux_leaves_qt_platform_unset(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        output = tmp_path / "out.pdf"
        create_subprocess = AsyncMock(return_value=_mock_process(writes=(output,)))

        with (
            patch.object(
                headless, "find_musescore_command", return_value=_MUSESCORE_COMMAND
            ),
            patch.object(headless.asyncio, "create_subprocess_exec", create_subprocess),
            patch.object(headless.platform, "system", return_value="Darwin"),
            patch.dict("os.environ", {}, clear=True),
        ):
            # Act
            await render(tmp_path / "in.musicxml", output)

        # Assert
        environment = create_subprocess.call_args.kwargs["env"]
        assert "QT_QPA_PLATFORM" not in environment

    @pytest.mark.anyio()
    async def test_render_reports_page_series_written_for_output(
        self, tmp_path: Path
    ) -> None:
        # Arrange: PNG export writes one numbered file per page, never the
        # requested path itself.
        output = tmp_path / "out.png"
        pages = (tmp_path / "out-1.png", tmp_path / "out-2.png")
        process = _mock_process(writes=pages)

        with (
            patch.object(
                headless, "find_musescore_command", return_value=_MUSESCORE_COMMAND
            ),
            patch.object(
                headless.asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=process),
            ),
        ):
            # Act
            result = await render(tmp_path / "in.musicxml", output)

        # Assert
        assert result == RenderResult(pages, None)

    @pytest.mark.anyio()
    async def test_render_with_output_written_and_unclean_exit_warns(
        self, tmp_path: Path
    ) -> None:
        # Arrange: MuseScore exports the file and then aborts while shutting
        # down, as MuseScore Studio 4.7 does on macOS 26 after a PDF export.
        output = tmp_path / "out.pdf"
        process = _mock_process(returncode=-6, writes=(output,))

        with (
            patch.object(
                headless, "find_musescore_command", return_value=_MUSESCORE_COMMAND
            ),
            patch.object(
                headless.asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=process),
            ),
        ):
            # Act
            result = await render(tmp_path / "in.musicxml", output)

        # Assert
        assert result.output_files == (output,)
        assert result.warning is not None
        assert "exited with code -6" in result.warning

    @pytest.mark.anyio()
    async def test_render_with_clean_exit_but_no_output_raises(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        process = _mock_process(returncode=0)

        with (
            patch.object(
                headless, "find_musescore_command", return_value=_MUSESCORE_COMMAND
            ),
            patch.object(
                headless.asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=process),
            ),
            pytest.raises(RenderError, match="wrote no output file"),
        ):
            # Act / Assert
            await render(tmp_path / "in.musicxml", tmp_path / "out.pdf")

    @pytest.mark.anyio()
    async def test_render_does_not_count_untouched_earlier_output(
        self, tmp_path: Path
    ) -> None:
        # Arrange: a file from an earlier run is already there and MuseScore
        # fails before overwriting it.
        output = tmp_path / "out.pdf"
        output.write_bytes(b"stale")
        process = _mock_process(returncode=1, stderr=b"Error: cannot open file")

        with (
            patch.object(
                headless, "find_musescore_command", return_value=_MUSESCORE_COMMAND
            ),
            patch.object(
                headless.asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=process),
            ),
            pytest.raises(RenderError, match="exited with code 1"),
        ):
            # Act / Assert
            await render(tmp_path / "in.musicxml", output)

    @pytest.mark.anyio()
    async def test_render_with_nonzero_exit_raises_with_stderr_tail(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        stderr_lines = [f"line {index}" for index in range(30)]
        stderr_lines.append("Error: cannot open file")
        process = _mock_process(returncode=1, stderr="\n".join(stderr_lines).encode())

        with (
            patch.object(
                headless, "find_musescore_command", return_value=_MUSESCORE_COMMAND
            ),
            patch.object(
                headless.asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=process),
            ),
            pytest.raises(RenderError) as exception_info,
        ):
            # Act / Assert
            await render(tmp_path / "in.musicxml", tmp_path / "out.pdf")

        message = str(exception_info.value)
        assert "exited with code 1" in message
        assert "Error: cannot open file" in message
        assert "line 0" not in message  # only the tail is included

    @pytest.mark.anyio()
    async def test_render_with_timeout_kills_process_and_raises(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        async def never_finishes() -> tuple[bytes, bytes]:
            await asyncio.sleep(60)
            return (b"", b"")

        process = _mock_process()
        process.communicate = AsyncMock(side_effect=never_finishes)

        with (
            patch.object(
                headless, "find_musescore_command", return_value=_MUSESCORE_COMMAND
            ),
            patch.object(
                headless.asyncio,
                "create_subprocess_exec",
                AsyncMock(return_value=process),
            ),
            patch.object(headless, "RENDER_TIMEOUT_SECONDS", 0.01),
            pytest.raises(RenderError, match="did not finish"),
        ):
            # Act / Assert
            await render(tmp_path / "in.musicxml", tmp_path / "out.pdf")

        process.kill.assert_called_once()
        process.wait.assert_awaited_once()


# ── render_score tool ─────────────────────────────────────────────────


class TestRenderScore:
    @pytest.mark.anyio()
    async def test_render_score_returns_default_output_path(
        self, score_file: Path
    ) -> None:
        # Arrange
        expected_output = score_file.with_suffix(".pdf")
        render_mock = _rendering(expected_output)

        with patch("mcp_score.tools.render.render", render_mock):
            # Act
            result = await render_score(str(score_file))

        # Assert
        assert result == RenderedScore(
            output_path=str(expected_output),
            output_files=[str(expected_output)],
            format="pdf",
        )
        render_mock.assert_awaited_once_with(score_file, expected_output)

    @pytest.mark.anyio()
    async def test_render_score_maps_midi_to_mid_extension(
        self, score_file: Path
    ) -> None:
        # Arrange
        render_mock = _rendering(score_file.with_suffix(".mid"))

        with patch("mcp_score.tools.render.render", render_mock):
            # Act
            result = await render_score(str(score_file), format="midi")

        # Assert
        assert result.output_path == str(score_file.with_suffix(".mid"))
        assert result.format == "midi"

    @pytest.mark.anyio()
    async def test_render_score_uses_explicit_output_path(
        self, score_file: Path, tmp_path: Path
    ) -> None:
        # Arrange
        output = tmp_path / "exports" / "piece.png"
        output.parent.mkdir()
        pages = (output.with_name("piece-1.png"), output.with_name("piece-2.png"))
        render_mock = _rendering(*pages)

        with patch("mcp_score.tools.render.render", render_mock):
            # Act
            result = await render_score(str(score_file), "png", str(output))

        # Assert
        assert result.output_files == [str(page) for page in pages]
        render_mock.assert_awaited_once_with(score_file, output)

    @pytest.mark.anyio()
    async def test_render_score_passes_on_render_warning(
        self, score_file: Path
    ) -> None:
        # Arrange
        output = score_file.with_suffix(".pdf")
        render_mock = _rendering(output, warning="MuseScore exited with code -6.")

        with patch("mcp_score.tools.render.render", render_mock):
            # Act
            result = await render_score(str(score_file))

        # Assert
        assert result.warning == "MuseScore exited with code -6."

    @pytest.mark.anyio()
    async def test_render_score_with_missing_input_raises_without_rendering(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        render_mock = AsyncMock()

        with (
            patch("mcp_score.tools.render.render", render_mock),
            pytest.raises(ToolError, match="not found"),
        ):
            # Act
            await render_score(str(tmp_path / "missing.xml"))

        # Assert
        render_mock.assert_not_awaited()

    @pytest.mark.anyio()
    async def test_render_score_refuses_to_overwrite_input(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        score = tmp_path / "score.musicxml"
        score.write_text("<score-partwise/>")
        render_mock = AsyncMock()

        with (
            patch("mcp_score.tools.render.render", render_mock),
            pytest.raises(ToolError, match="overwrite the input"),
        ):
            # Act
            await render_score(str(score), format="musicxml")

        # Assert
        render_mock.assert_not_awaited()

    @pytest.mark.anyio()
    async def test_render_score_with_bad_format_raises_listing_formats(
        self, score_file: Path
    ) -> None:
        # Arrange
        render_mock = AsyncMock()

        with (
            patch("mcp_score.tools.render.render", render_mock),
            pytest.raises(ToolError, match="Unsupported format 'svg'") as exc_info,
        ):
            # Act
            await render_score(str(score_file), format="svg")

        # Assert
        assert "pdf" in str(exc_info.value)
        render_mock.assert_not_awaited()

    @pytest.mark.anyio()
    async def test_render_score_with_mismatched_extension_raises(
        self, score_file: Path, tmp_path: Path
    ) -> None:
        # Arrange
        render_mock = AsyncMock()

        with (
            patch("mcp_score.tools.render.render", render_mock),
            pytest.raises(ToolError, match=r"must end with \.pdf"),
        ):
            # Act
            await render_score(str(score_file), "pdf", str(tmp_path / "out.png"))

        # Assert
        render_mock.assert_not_awaited()

    @pytest.mark.anyio()
    async def test_render_score_with_missing_output_dir_raises(
        self, score_file: Path, tmp_path: Path
    ) -> None:
        # Arrange
        render_mock = AsyncMock()
        output = tmp_path / "no-such-dir" / "out.pdf"

        with (
            patch("mcp_score.tools.render.render", render_mock),
            pytest.raises(ToolError, match="Output directory does not exist"),
        ):
            # Act
            await render_score(str(score_file), "pdf", str(output))

        # Assert
        render_mock.assert_not_awaited()

    @pytest.mark.anyio()
    async def test_render_score_without_musescore_raises_naming_env_var(
        self, score_file: Path
    ) -> None:
        # Arrange
        render_mock = AsyncMock(
            side_effect=MuseScoreNotFoundError("MuseScore Studio 4 was not found.")
        )

        with (
            patch("mcp_score.tools.render.render", render_mock),
            pytest.raises(
                ToolError, match="MuseScore Studio 4 was not found"
            ) as exc_info,
        ):
            # Act
            await render_score(str(score_file))

        # Assert
        assert MUSESCORE_PATH_ENV_VAR in str(exc_info.value)

    @pytest.mark.anyio()
    async def test_render_score_with_failed_render_raises_with_stderr(
        self, score_file: Path
    ) -> None:
        # Arrange
        render_mock = AsyncMock(
            side_effect=RenderError("MuseScore exited with code 1.\nbad input")
        )

        with (
            patch("mcp_score.tools.render.render", render_mock),
            pytest.raises(ToolError) as exc_info,
        ):
            # Act
            await render_score(str(score_file))

        # Assert
        assert str(exc_info.value) == (
            "Rendering failed: MuseScore exited with code 1.\nbad input"
        )

    @pytest.mark.anyio()
    async def test_render_score_end_to_end_runs_subprocess(
        self, score_file: Path
    ) -> None:
        # Arrange: only the discovery and the subprocess are mocked.
        expected_output = score_file.with_suffix(".wav")
        create_subprocess = AsyncMock(
            return_value=_mock_process(writes=(expected_output,))
        )

        with (
            patch.object(
                headless, "find_musescore_command", return_value=_MUSESCORE_COMMAND
            ),
            patch.object(headless.asyncio, "create_subprocess_exec", create_subprocess),
        ):
            # Act
            result = await render_score(str(score_file), "wav")

        # Assert
        assert result == RenderedScore(
            output_path=str(expected_output),
            output_files=[str(expected_output)],
            format="wav",
        )
        assert create_subprocess.call_args.args[-2] == str(expected_output)
