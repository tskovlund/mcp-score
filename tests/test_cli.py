"""Tests for the CLI entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from mcp_score.cli import (
    install_plugin,
    install_skill,
    main,
    run_script,
)


class TestInstallSkill:
    def test_install_skill_copies_files_to_destination(self, tmp_path: Path) -> None:
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

    def test_install_skill_without_files_returns_false(self) -> None:
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
    def test_install_plugin_copies_qml_to_destination(self, tmp_path: Path) -> None:
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

    def test_install_plugin_creates_missing_parent_dirs(self, tmp_path: Path) -> None:
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

    def test_install_plugin_on_unsupported_platform_returns_false(self) -> None:
        # Arrange
        with patch("mcp_score.cli.platform.system", return_value="FreeBSD"):
            # Act
            result = install_plugin()

        # Assert
        assert result is False

    def test_install_plugin_without_file_returns_false(self) -> None:
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

    def test_install_plugin_uses_ms4_source_file(self, tmp_path: Path) -> None:
        # Arrange — verify that install_plugin requests plugin_ms4.qml (not plugin.qml)
        plugin_dir = tmp_path / "Plugins"
        plugin_dir.mkdir()

        fake_qml = tmp_path / "plugin_ms4.qml"
        fake_qml.write_text("// ms4 plugin")

        captured: list[str] = []

        def capture_path(resource_path: str) -> Path:
            captured.append(resource_path)
            return fake_qml

        with (
            patch.dict("mcp_score.cli._PLUGIN_DIRS", {"Darwin": plugin_dir}),
            patch("mcp_score.cli.platform.system", return_value="Darwin"),
            patch("mcp_score.cli._package_path", side_effect=capture_path),
        ):
            result = install_plugin()

        assert result is True
        assert len(captured) == 1
        assert "plugin_ms4.qml" in captured[0]


class TestMainCli:
    def test_main_without_args_runs_serve(self) -> None:
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

    def test_help_command_exits_zero(self) -> None:
        # Arrange / Act / Assert
        with (
            patch("sys.argv", ["mcp-score", "help"]),
            pytest.raises(SystemExit, match="0"),
        ):
            main()

    def test_unknown_command_exits_with_error(self) -> None:
        # Arrange / Act / Assert
        with (
            patch("sys.argv", ["mcp-score", "nonsense"]),
            pytest.raises(SystemExit, match="1"),
        ):
            main()

    def test_install_skill_command_exits_zero(self) -> None:
        # Arrange
        with (
            patch("sys.argv", ["mcp-score", "install-skill"]),
            patch("mcp_score.cli.install_skill", return_value=True),
            pytest.raises(SystemExit, match="0"),
        ):
            # Act / Assert
            main()

    def test_install_plugin_command_exits_zero(self) -> None:
        # Arrange
        with (
            patch("sys.argv", ["mcp-score", "install-plugin"]),
            patch("mcp_score.cli.install_plugin", return_value=True),
            pytest.raises(SystemExit, match="0"),
        ):
            # Act / Assert
            main()

    def test_install_command_exits_zero(self) -> None:
        # Arrange
        with (
            patch("sys.argv", ["mcp-score", "install"]),
            patch("mcp_score.cli.install_all", return_value=True),
            pytest.raises(SystemExit, match="0"),
        ):
            # Act / Assert
            main()

    def test_install_failure_exits_with_error(self) -> None:
        # Arrange
        with (
            patch("sys.argv", ["mcp-score", "install"]),
            patch("mcp_score.cli.install_all", return_value=False),
            pytest.raises(SystemExit, match="1"),
        ):
            # Act / Assert
            main()


class TestRunScript:
    def test_run_script_without_args_exits_with_error(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SystemExit, match="1"):
            run_script([])

    def test_run_script_executes_python_script(self, tmp_path: Path) -> None:
        # Arrange
        script = tmp_path / "test_script.py"
        script.write_text("print('hello')")

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("subprocess.run", return_value=mock_result) as mock_run,
            pytest.raises(SystemExit, match="0"),
        ):
            # Act
            run_script([str(script)])

        # Assert
        mock_run.assert_called_once()
        assert str(script) in mock_run.call_args.args[0]

    def test_run_command_via_main_executes_script(self, tmp_path: Path) -> None:
        # Arrange
        script = tmp_path / "test_script.py"
        script.write_text("print('hello')")

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("sys.argv", ["mcp-score", "run", str(script)]),
            patch("subprocess.run", return_value=mock_result),
            pytest.raises(SystemExit, match="0"),
        ):
            # Act
            main()
