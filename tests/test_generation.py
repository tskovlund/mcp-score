"""Tests for MCP generation tool wrappers."""

import json
from pathlib import Path
from typing import Any

import pytest

from mcp_score.tools.generation import (
    add_notes,
    add_rehearsal_mark,
    clear_score,
    create_score,
    export_score,
    get_score_info,
)


def _parse(result: str) -> dict[str, Any]:
    """Parse a JSON string result from a tool wrapper."""
    parsed: dict[str, Any] = json.loads(result)
    return parsed


class TestCreateScoreTool:
    @pytest.mark.anyio()
    async def test_create_score_returns_valid_json(self) -> None:
        # Arrange / Act
        result = await create_score(title="Test", instruments=["trumpet"])

        # Assert
        parsed = _parse(result)
        assert parsed["success"] is True

    @pytest.mark.anyio()
    async def test_create_score_returns_json_string(self) -> None:
        # Arrange / Act
        result = await create_score(title="JSON Test", instruments=["piano"])

        # Assert
        assert isinstance(result, str)
        parsed = _parse(result)
        assert "parts" in parsed


class TestAddNotesTool:
    @pytest.mark.anyio()
    async def test_add_notes_returns_valid_json(self) -> None:
        # Arrange — create a score first
        await create_score(title="Note Test", instruments=["trumpet"])

        # Act
        result = await add_notes(
            part="0",
            measure=1,
            notes=[{"pitch": "C5", "duration": "quarter"}],
        )

        # Assert
        parsed = _parse(result)
        assert parsed["success"] is True

    @pytest.mark.anyio()
    async def test_add_notes_on_empty_returns_json_error(self) -> None:
        # Arrange — clear any existing score
        await clear_score()

        # Act
        result = await add_notes(
            part="0",
            measure=1,
            notes=[{"pitch": "C5", "duration": "quarter"}],
        )

        # Assert
        parsed = _parse(result)
        assert "error" in parsed


class TestAddRehearsalMarkTool:
    @pytest.mark.anyio()
    async def test_add_rehearsal_mark_returns_valid_json(self) -> None:
        # Arrange
        await create_score(title="Mark Test", instruments=["trumpet"])

        # Act
        result = await add_rehearsal_mark(measure=1, label="A")

        # Assert
        parsed = _parse(result)
        assert parsed["success"] is True


class TestGetScoreInfoTool:
    @pytest.mark.anyio()
    async def test_get_score_info_returns_valid_json(self) -> None:
        # Arrange
        await create_score(title="Info Test", instruments=["piano"])

        # Act
        result = await get_score_info()

        # Assert
        parsed = _parse(result)
        assert parsed["success"] is True
        assert "title" in parsed
        assert "num_parts" in parsed


class TestExportScoreTool:
    @pytest.mark.anyio()
    async def test_export_creates_file_and_returns_valid_json(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        await create_score(title="Export Test", instruments=["flute"])
        filepath = str(tmp_path / "export_test.musicxml")

        # Act
        result = await export_score(filepath=filepath)

        # Assert
        parsed = _parse(result)
        assert parsed["success"] is True
        assert Path(filepath).exists()

    @pytest.mark.anyio()
    async def test_export_on_empty_returns_json_error(self, tmp_path: Path) -> None:
        # Arrange
        await clear_score()
        filepath = str(tmp_path / "empty.musicxml")

        # Act
        result = await export_score(filepath=filepath)

        # Assert
        parsed = _parse(result)
        assert "error" in parsed


class TestClearScoreTool:
    @pytest.mark.anyio()
    async def test_clear_score_returns_valid_json(self) -> None:
        # Arrange
        await create_score(title="Clear Test", instruments=["trumpet"])

        # Act
        result = await clear_score()

        # Assert
        parsed = _parse(result)
        assert parsed["success"] is True

    @pytest.mark.anyio()
    async def test_clear_then_info_returns_error(self) -> None:
        # Arrange
        await create_score(title="Clear Info Test", instruments=["trumpet"])
        await clear_score()

        # Act
        result = await get_score_info()

        # Assert
        parsed = _parse(result)
        assert "error" in parsed
