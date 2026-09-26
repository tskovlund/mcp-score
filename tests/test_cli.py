"""Tests for the mcp-score command line."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from mcp_score import cli
from mcp_score.cli import install_plugin, install_skill, main
from mcp_score.musescore.paths import PLUGIN_DIRECTORY_NAME, plugins_directory

if TYPE_CHECKING:
    from pathlib import Path

_PACKAGE_PATH = "mcp_score.cli.package_path"


@pytest.fixture
def skill_source(tmp_path: Path) -> Path:
    """A skill directory with the files the install copies."""
    source = tmp_path / "source" / "score-generate"
    (source / "references").mkdir(parents=True)
    (source / "SKILL.md").write_text("# Test skill")
    (source / "references" / "instruments.md").write_text("# Instruments")
    return source


@pytest.fixture
def plugin_source(tmp_path: Path) -> Path:
    """A plugin directory with the QML file and a module it imports."""
    source = tmp_path / "source" / "plugin"
    source.mkdir(parents=True)
    (source / "mcp-score-bridge.qml").write_text("// fake plugin")
    (source / "score.js").write_text("// fake module")
    return source


class TestInstallSkill:
    def test_copies_the_skill_tree_to_destination(
        self, skill_source: Path, tmp_path: Path
    ) -> None:
        # Arrange
        destination = tmp_path / "skills" / "score-generate"

        with patch(_PACKAGE_PATH, return_value=skill_source):
            # Act
            installed = install_skill(destination)

        # Assert
        assert installed == destination
        assert (destination / "SKILL.md").read_text() == "# Test skill"
        assert (destination / "references" / "instruments.md").exists()

    def test_replaces_an_earlier_install(
        self, skill_source: Path, tmp_path: Path
    ) -> None:
        # Arrange: a stale file from an older skill version
        destination = tmp_path / "skills" / "score-generate"
        destination.mkdir(parents=True)
        (destination / "old.md").write_text("stale")

        with patch(_PACKAGE_PATH, return_value=skill_source):
            # Act
            install_skill(destination)

        # Assert
        assert not (destination / "old.md").exists()
        assert (destination / "SKILL.md").exists()


class TestInstallPlugin:
    def test_copies_the_plugin_under_its_musescore_name(
        self, plugin_source: Path, tmp_path: Path
    ) -> None:
        # Arrange
        directory = tmp_path / "nested" / "Plugins"

        with patch(_PACKAGE_PATH, return_value=plugin_source):
            # Act
            installed = install_plugin(directory)

        # Assert: parent directories created, directory named as MuseScore expects
        assert installed == directory / PLUGIN_DIRECTORY_NAME
        assert (installed / "mcp-score-bridge.qml").read_text() == "// fake plugin"
        assert (installed / "score.js").read_text() == "// fake module"

    def test_defaults_to_musescores_plugins_directory(
        self, plugin_source: Path, tmp_path: Path
    ) -> None:
        # Arrange
        with (
            patch(_PACKAGE_PATH, return_value=plugin_source),
            patch("mcp_score.musescore.paths.Path.home", return_value=tmp_path),
        ):
            # Act
            installed = install_plugin()

        # Assert
        assert installed == plugins_directory(tmp_path) / PLUGIN_DIRECTORY_NAME
        assert installed.is_dir()


class TestMain:
    def test_without_command_runs_the_server(self) -> None:
        # Arrange
        serve = MagicMock()

        with patch("mcp_score.server.main", serve):
            # Act
            code = main([])

        # Assert
        assert code == cli.EXIT_SUCCESS
        serve.assert_called_once()

    def test_unknown_command_exits_with_usage_error(self) -> None:
        # Arrange / Act / Assert: argparse reports unknown commands with code 2
        with pytest.raises(SystemExit, match="2"):
            main(["nonsense"])

    def test_run_passes_script_and_arguments_to_this_interpreter(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        script = tmp_path / "script.py"
        script.write_text("print('hello')")
        completed = MagicMock(returncode=3)

        with patch.object(cli.subprocess, "run", return_value=completed) as run:
            # Act
            code = main(["run", str(script), "--flag", "value"])

        # Assert: the script's exit code is the command's exit code
        assert code == 3
        assert run.call_args.args[0] == [
            cli.sys.executable,
            str(script),
            "--flag",
            "value",
        ]

    @pytest.mark.parametrize(
        ("command", "skill", "plugin"),
        [
            ("install", True, True),
            ("install-skill", True, False),
            ("install-plugin", False, True),
        ],
    )
    def test_install_commands_install_what_they_name(
        self, command: str, skill: bool, plugin: bool, tmp_path: Path
    ) -> None:
        # Arrange
        install_skill_mock = MagicMock(return_value=tmp_path / "skill")
        install_plugin_mock = MagicMock(return_value=tmp_path / "plugin")

        with (
            patch.object(cli, "install_skill", install_skill_mock),
            patch.object(cli, "install_plugin", install_plugin_mock),
        ):
            # Act
            code = main([command])

        # Assert
        assert code == cli.EXIT_SUCCESS
        assert install_skill_mock.called is skill
        assert install_plugin_mock.called is plugin

    def test_install_with_missing_files_fails_with_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Arrange
        with patch(_PACKAGE_PATH, side_effect=FileNotFoundError("no plugin files")):
            # Act
            code = main(["install-plugin"])

        # Assert
        assert code == cli.EXIT_FAILURE
        assert "no plugin files" in capsys.readouterr().err
