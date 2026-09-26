"""Tests for assembling the score-generate skill into one guide."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from mcp_score.guide import load_guide

if TYPE_CHECKING:
    from pathlib import Path

_PACKAGE_PATH_TARGET = "mcp_score.guide.package_path"


def _make_skill_directory(root: Path) -> Path:
    """Create a fake skill directory with all three guide files."""
    skill_directory = root / "score-generate"
    references = skill_directory / "references"
    references.mkdir(parents=True)
    (skill_directory / "SKILL.md").write_text("# Fake skill\n\nUse B- for flats.")
    (references / "instruments.md").write_text("# Fake instruments\n\nTrumpet")
    (references / "template.py").write_text('score.write("musicxml", fp=OUTPUT)')
    return skill_directory


class TestLoadGuide:
    def test_guide_contains_all_sections_in_order(self, tmp_path: Path) -> None:
        # Arrange
        skill_directory = _make_skill_directory(tmp_path)

        with patch(_PACKAGE_PATH_TARGET, return_value=skill_directory):
            # Act
            guide = load_guide()

        # Assert
        skill_index = guide.index("# SKILL.md")
        instruments_index = guide.index("# references/instruments.md")
        template_index = guide.index("# references/template.py")
        assert skill_index < instruments_index < template_index
        assert "Use B- for flats." in guide
        assert "Trumpet" in guide
        assert '```python\nscore.write("musicxml", fp=OUTPUT)\n```' in guide
        assert "generate_score" in guide[:skill_index]

    def test_guide_with_missing_reference_raises_naming_the_file(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        skill_directory = _make_skill_directory(tmp_path)
        (skill_directory / "references" / "instruments.md").unlink()

        with (
            patch(_PACKAGE_PATH_TARGET, return_value=skill_directory),
            pytest.raises(FileNotFoundError, match="instruments.md"),
        ):
            # Act / Assert
            load_guide()
