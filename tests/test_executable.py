"""Tests for locating the MuseScore executable."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from mcp_score.musescore import executable as discovery
from mcp_score.musescore.executable import (
    MUSESCORE_PATH_ENV_VAR,
    MuseScoreNotFoundError,
    find_musescore_command,
)


class TestFindMusescoreCommand:
    def test_find_with_env_var_file_returns_configured_path(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        executable = tmp_path / "mscore-custom"
        executable.write_text("")

        with (
            patch.dict("os.environ", {MUSESCORE_PATH_ENV_VAR: str(executable)}),
            patch.object(discovery.shutil, "which", return_value="/usr/bin/mscore"),
        ):
            # Act
            command = find_musescore_command()

        # Assert: the env var wins over PATH.
        assert command == [str(executable)]

    def test_find_with_env_var_command_name_resolves_on_path(self) -> None:
        # Arrange
        with (
            patch.dict("os.environ", {MUSESCORE_PATH_ENV_VAR: "mscore-nightly"}),
            patch.object(
                discovery.shutil, "which", return_value="/usr/bin/mscore-nightly"
            ),
        ):
            # Act
            command = find_musescore_command()

        # Assert
        assert command == ["/usr/bin/mscore-nightly"]

    def test_find_with_bad_env_var_raises_naming_env_var(self) -> None:
        # Arrange
        with (
            patch.dict("os.environ", {MUSESCORE_PATH_ENV_VAR: "/nowhere/mscore"}),
            patch.object(discovery.shutil, "which", return_value=None),
            pytest.raises(MuseScoreNotFoundError, match=MUSESCORE_PATH_ENV_VAR),
        ):
            # Act / Assert
            find_musescore_command()

    def test_find_on_path_returns_first_known_name(self) -> None:
        # Arrange
        def which(name: str) -> str | None:
            return f"/usr/bin/{name}" if name in {"musescore", "MuseScore4"} else None

        with (
            patch.dict("os.environ", {MUSESCORE_PATH_ENV_VAR: ""}),
            patch.object(discovery.shutil, "which", side_effect=which),
        ):
            # Act
            command = find_musescore_command()

        # Assert: "musescore" precedes "MuseScore4" in the search order.
        assert command == ["/usr/bin/musescore"]

    def test_find_on_macos_returns_app_bundle_executable(self, tmp_path: Path) -> None:
        # Arrange
        executable = tmp_path / "MuseScore 4.app" / "Contents" / "MacOS" / "mscore"
        executable.parent.mkdir(parents=True)
        executable.write_text("")

        with (
            patch.dict("os.environ", {MUSESCORE_PATH_ENV_VAR: ""}),
            patch.object(discovery.shutil, "which", return_value=None),
            patch.object(discovery.platform, "system", return_value="Darwin"),
            patch.object(discovery, "_MACOS_DEFAULT_EXECUTABLE", executable),
        ):
            # Act
            command = find_musescore_command()

        # Assert
        assert command == [str(executable)]

    def test_find_on_windows_honours_program_files(self, tmp_path: Path) -> None:
        # Arrange
        executable = tmp_path / "MuseScore 4" / "bin" / "MuseScore4.exe"
        executable.parent.mkdir(parents=True)
        executable.write_text("")

        with (
            patch.dict(
                "os.environ",
                {MUSESCORE_PATH_ENV_VAR: "", "ProgramFiles": str(tmp_path)},
            ),
            patch.object(discovery.shutil, "which", return_value=None),
            patch.object(discovery.platform, "system", return_value="Windows"),
        ):
            # Act
            command = find_musescore_command()

        # Assert
        assert command == [str(executable)]

    def test_find_on_linux_returns_flatpak_argv(self, tmp_path: Path) -> None:
        # Arrange
        export_directory = tmp_path / "exports" / "bin"
        export_directory.mkdir(parents=True)
        (export_directory / "org.musescore.MuseScore").write_text("")

        def which(name: str) -> str | None:
            return "/usr/bin/flatpak" if name == "flatpak" else None

        with (
            patch.dict("os.environ", {MUSESCORE_PATH_ENV_VAR: ""}),
            patch.object(discovery.shutil, "which", side_effect=which),
            patch.object(discovery.platform, "system", return_value="Linux"),
            patch.object(discovery, "_FLATPAK_EXPORT_DIRECTORIES", (export_directory,)),
        ):
            # Act
            command = find_musescore_command()

        # Assert
        assert command == ["flatpak", "run", "org.musescore.MuseScore"]

    def test_find_with_nothing_installed_raises_naming_env_var(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        with (
            patch.dict("os.environ", {MUSESCORE_PATH_ENV_VAR: ""}),
            patch.object(discovery.shutil, "which", return_value=None),
            patch.object(discovery.platform, "system", return_value="Linux"),
            patch.object(discovery, "_FLATPAK_EXPORT_DIRECTORIES", (tmp_path,)),
            pytest.raises(MuseScoreNotFoundError, match=MUSESCORE_PATH_ENV_VAR),
        ):
            # Act / Assert
            find_musescore_command()
