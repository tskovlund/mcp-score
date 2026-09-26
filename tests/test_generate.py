"""Tests for the generation tools — script execution, guide and prompt."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_score.tools.generate import (
    STDERR_TAIL_LINES,
    generate_score,
    score_generate_prompt,
    score_generation_guide,
)

_SUBPROCESS_TARGET = "mcp_score.tools.generate.asyncio.create_subprocess_exec"
_LOAD_GUIDE_TARGET = "mcp_score.tools.generate.load_guide"
_HOME_TARGET = "mcp_score.tools.generate.Path.home"


def _fake_process(
    returncode: int, stdout: bytes = b"", stderr: bytes = b""
) -> MagicMock:
    """Build a process double whose communicate() returns the given output."""
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(stdout, stderr))
    process.kill = MagicMock()
    process.wait = AsyncMock()
    return process


# ── generate_score ───────────────────────────────────────────────────


class TestGenerateScore:
    @pytest.mark.anyio()
    async def test_successful_run_reports_only_new_files(self, tmp_path: Path) -> None:
        # Arrange
        (tmp_path / "existing.txt").write_text("already here")
        process = _fake_process(0, stdout=b"Exported\n")
        script = 'print("hi")\n'
        executed: dict[str, Any] = {}

        async def fake_exec(*args: str, **kwargs: Any) -> MagicMock:
            executed["args"] = args
            executed["script"] = Path(args[1]).read_text()
            (Path(kwargs["cwd"]) / "Song.musicxml").write_text("<score/>")
            return process

        with patch(_SUBPROCESS_TARGET, side_effect=fake_exec):
            # Act
            result = await generate_score(script, output_dir=str(tmp_path))

        # Assert
        assert result["success"] is True
        assert result["output_files"] == [str(tmp_path / "Song.musicxml")]
        assert result["stdout"] == "Exported\n"
        assert executed["args"][0] == sys.executable
        assert executed["script"] == script

    @pytest.mark.anyio()
    async def test_failing_script_returns_stderr_tail(self, tmp_path: Path) -> None:
        # Arrange
        noise = [f"line {index}" for index in range(STDERR_TAIL_LINES)]
        stderr = "\n".join([*noise, "NameError: name 'x' is not defined"])
        process = _fake_process(1, stderr=stderr.encode())

        with patch(_SUBPROCESS_TARGET, AsyncMock(return_value=process)):
            # Act
            result = await generate_score("x", output_dir=str(tmp_path))

        # Assert
        assert result["returncode"] == 1
        assert "code 1" in result["error"]
        assert result["stderr"].endswith("NameError: name 'x' is not defined")
        assert "line 0" not in result["stderr"]
        assert len(result["stderr"].splitlines()) == STDERR_TAIL_LINES

    @pytest.mark.anyio()
    async def test_timeout_kills_process_and_returns_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        process = _fake_process(-9)

        async def never_finishes() -> tuple[bytes, bytes]:
            await asyncio.sleep(60)
            return b"", b""

        process.communicate = AsyncMock(side_effect=never_finishes)

        with patch(_SUBPROCESS_TARGET, AsyncMock(return_value=process)):
            # Act
            result = await generate_score("x", output_dir=str(tmp_path), timeout=0.01)

        # Assert
        process.kill.assert_called_once()
        process.wait.assert_awaited_once()
        assert "timed out" in result["error"]
        assert result["returncode"] == -9

    @pytest.mark.anyio()
    async def test_output_dir_pointing_at_file_returns_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        not_a_directory = tmp_path / "file.txt"
        not_a_directory.write_text("x")

        with patch(_SUBPROCESS_TARGET, AsyncMock()) as mock_exec:
            # Act
            result = await generate_score("x", output_dir=str(not_a_directory))

        # Assert
        assert "not a directory" in result["error"]
        mock_exec.assert_not_awaited()

    @pytest.mark.anyio()
    async def test_default_output_dir_is_fresh_directory_under_desktop(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        desktop = tmp_path / "Desktop"
        desktop.mkdir()
        process = _fake_process(0)

        with (
            patch(_HOME_TARGET, return_value=tmp_path),
            patch(_SUBPROCESS_TARGET, AsyncMock(return_value=process)) as mock_exec,
        ):
            # Act
            await generate_score("x")

        # Assert
        working_directory = Path(mock_exec.call_args.kwargs["cwd"])
        assert working_directory.parent == desktop
        assert working_directory.is_dir()

    @pytest.mark.anyio()
    async def test_default_output_dir_falls_back_to_home(self, tmp_path: Path) -> None:
        # Arrange
        process = _fake_process(0)

        with (
            patch(_HOME_TARGET, return_value=tmp_path),
            patch(_SUBPROCESS_TARGET, AsyncMock(return_value=process)) as mock_exec,
        ):
            # Act
            await generate_score("x")

        # Assert
        working_directory = Path(mock_exec.call_args.kwargs["cwd"])
        assert working_directory.parent == tmp_path


# ── score_generation_guide ───────────────────────────────────────────


class TestScoreGenerationGuide:
    def test_guide_tool_returns_the_assembled_guide(self) -> None:
        # Arrange
        with patch(_LOAD_GUIDE_TARGET, return_value="# Guide"):
            # Act
            guide = score_generation_guide()

        # Assert
        assert guide == "# Guide"

    def test_guide_with_missing_skill_files_returns_error(self) -> None:
        # Arrange
        with patch(_LOAD_GUIDE_TARGET, side_effect=FileNotFoundError("no skill files")):
            # Act
            result = json.loads(score_generation_guide())

        # Assert
        assert result["error"] == "no skill files"


# ── score-generate prompt ────────────────────────────────────────────


class TestScoreGeneratePrompt:
    def test_prompt_returns_same_text_as_guide_tool(self) -> None:
        # Arrange
        with patch(_LOAD_GUIDE_TARGET, return_value="# Guide"):
            # Act
            prompt_text = score_generate_prompt()
            guide_text = score_generation_guide()

        # Assert
        assert prompt_text == guide_text == "# Guide"
