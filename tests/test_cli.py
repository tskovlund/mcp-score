"""Tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_score.cli import (
    _PLUGIN_DIRS,
    _SKILL_DEST,
    install_plugin,
    install_skill,
    main,
)


class TestInstallSkill:
    def test_install_skill_copies_files(self, tmp_path: Path) -> None:
        # Arrange
        skill_dest = tmp_path / "skills" / "score-generate"

        # Create a fake source skill directory.
        fake_skill = tmp_path / "source" / ".claude" / "skills" / "score-generate"
        fake_skill.mkdir(parents=True)
        (fake_skill / "SKILL.md").write_text("# Test skill")
        refs = fake_skill / "references"
        refs.mkdir()
        (refs / "instruments.md").write_text("# Instruments")

        with (
            patch("mcp_score.cli._SKILL_DEST", skill_dest),
            patch("mcp_score.cli._package_path", return_value=fake_skill),
        ):
            # Act
            result = install_skill()

        # Assert
        assert result is True
        assert (skill_dest / "SKILL.md").exists()
        assert (skill_dest / "references" / "instruments.md").exists()

    def test_install_skill_returns_false_when_not_found(self) -> None:
        # Arrange
        with patch(
            "mcp_score.cli._package_path",
            side_effect=FileNotFoundError("not found"),
        ):
            # Act
            result = install_skill()

        # Assert
        assert result is False


class TestInstallPlugin:
    def test_install_plugin_copies_file(self, tmp_path: Path) -> None:
        # Arrange
        plugin_dir = tmp_path / "Plugins"
        plugin_dir.mkdir()

        fake_qml = tmp_path / "source" / "plugin.qml"
        fake_qml.parent.mkdir(parents=True)
        fake_qml.write_text("// fake plugin")

        with (
            patch.dict("mcp_score.cli._PLUGIN_DIRS", {"Darwin": plugin_dir}),
            patch("mcp_score.cli.platform.system", return_value="Darwin"),
            patch("mcp_score.cli._package_path", return_value=fake_qml),
        ):
            # Act
            result = install_plugin()

        # Assert
        assert result is True
        assert (plugin_dir / "mcp-score-bridge.qml").exists()
        assert (plugin_dir / "mcp-score-bridge.qml").read_text() == "// fake plugin"

    def test_install_plugin_creates_parent_dirs(self, tmp_path: Path) -> None:
        # Arrange
        plugin_dir = tmp_path / "nested" / "path" / "Plugins"

        fake_qml = tmp_path / "source" / "plugin.qml"
        fake_qml.parent.mkdir(parents=True)
        fake_qml.write_text("// fake plugin")

        with (
            patch.dict("mcp_score.cli._PLUGIN_DIRS", {"Linux": plugin_dir}),
            patch("mcp_score.cli.platform.system", return_value="Linux"),
            patch("mcp_score.cli._package_path", return_value=fake_qml),
        ):
            # Act
            result = install_plugin()

        # Assert
        assert result is True
        assert (plugin_dir / "mcp-score-bridge.qml").exists()

    def test_install_plugin_unsupported_platform(self) -> None:
        # Arrange
        with patch("mcp_score.cli.platform.system", return_value="Windows"):
            # Act
            result = install_plugin()

        # Assert
        assert result is False

    def test_install_plugin_returns_false_when_not_found(self) -> None:
        # Arrange
        with (
            patch("mcp_score.cli.platform.system", return_value="Darwin"),
            patch(
                "mcp_score.cli._package_path",
                side_effect=FileNotFoundError("not found"),
            ),
        ):
            # Act
            result = install_plugin()

        # Assert
        assert result is False


class TestMainCli:
    def test_serve_is_default(self) -> None:
        # Arrange
        mock_serve = MagicMock()

        with (
            patch("sys.argv", ["mcp-score"]),
            patch("mcp_score.server.main", mock_serve),
            pytest.raises(SystemExit, match="0"),
        ):
            # Act
            main()

        # Assert
        mock_serve.assert_called_once()

    def test_help_exits_zero(self) -> None:
        # Arrange / Act / Assert
        with (
            patch("sys.argv", ["mcp-score", "help"]),
            pytest.raises(SystemExit, match="0"),
        ):
            main()

    def test_unknown_command_exits_one(self) -> None:
        # Arrange / Act / Assert
        with (
            patch("sys.argv", ["mcp-score", "nonsense"]),
            pytest.raises(SystemExit, match="1"),
        ):
            main()

    def test_install_skill_command(self) -> None:
        # Arrange
        with (
            patch("sys.argv", ["mcp-score", "install-skill"]),
            patch("mcp_score.cli.install_skill", return_value=True),
            pytest.raises(SystemExit, match="0"),
        ):
            # Act / Assert
            main()

    def test_install_plugin_command(self) -> None:
        # Arrange
        with (
            patch("sys.argv", ["mcp-score", "install-plugin"]),
            patch("mcp_score.cli.install_plugin", return_value=True),
            pytest.raises(SystemExit, match="0"),
        ):
            # Act / Assert
            main()

    def test_install_command(self) -> None:
        # Arrange
        with (
            patch("sys.argv", ["mcp-score", "install"]),
            patch("mcp_score.cli.install_all", return_value=True),
            pytest.raises(SystemExit, match="0"),
        ):
            # Act / Assert
            main()

    def test_install_failure_exits_one(self) -> None:
        # Arrange
        with (
            patch("sys.argv", ["mcp-score", "install"]),
            patch("mcp_score.cli.install_all", return_value=False),
            pytest.raises(SystemExit, match="1"),
        ):
            # Act / Assert
            main()


class TestPackagePaths:
    def test_skill_dest_is_under_home(self) -> None:
        # Arrange
        expected = Path.home() / ".claude" / "skills" / "score-generate"

        # Act / Assert
        assert expected == _SKILL_DEST

    def test_plugin_dirs_has_darwin_and_linux(self) -> None:
        # Arrange / Act / Assert
        assert "Darwin" in _PLUGIN_DIRS
        assert "Linux" in _PLUGIN_DIRS
