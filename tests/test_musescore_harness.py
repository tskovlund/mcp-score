"""Tests for scripts/musescore_harness.py: platform layout and config seeding."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

_HARNESS_PATH = Path(__file__).parent.parent / "scripts" / "musescore_harness.py"


def _load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("musescore_harness", _HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve their (postponed) annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


harness: Any = _load_harness()


class TestLayoutFor:
    def test_linux_uses_xdg_directories(self, tmp_path: Path) -> None:
        # Act
        layout = harness.layout_for("Linux", tmp_path)

        # Assert
        assert layout.settings_file == tmp_path / ".config/MuseScore/MuseScore4.ini"
        assert layout.data_dir == tmp_path / ".local/share/MuseScore/MuseScore4"
        assert layout.plugins_dir == tmp_path / "Documents/MuseScore4/Plugins"
        assert layout.log_dir == layout.data_dir / "logs"

    def test_macos_uses_library_directories(self, tmp_path: Path) -> None:
        # Act
        layout = harness.layout_for("Darwin", tmp_path)

        # Assert
        assert (
            layout.settings_file
            == tmp_path / "Library/Preferences/MuseScore/MuseScore4.ini"
        )
        assert (
            layout.data_dir
            == tmp_path / "Library/Application Support/MuseScore/MuseScore4"
        )
        assert layout.plugins_dir == tmp_path / "Documents/MuseScore4/Plugins"

    def test_windows_honours_appdata_variables(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))

        # Act
        layout = harness.layout_for("Windows", tmp_path)

        # Assert
        assert layout.settings_file == tmp_path / "Roaming/MuseScore/MuseScore4.ini"
        assert layout.data_dir == tmp_path / "Local/MuseScore/MuseScore4"


class TestDefaultDownloadUrl:
    @pytest.mark.parametrize(
        ("system", "suffix"),
        [
            ("Linux", "-x86_64.AppImage"),
            ("Windows", "-x86_64.msi"),
            ("Darwin", ".dmg"),
        ],
    )
    def test_points_at_release_asset_for_platform(
        self, system: str, suffix: str
    ) -> None:
        # Act
        url = harness.default_download_url(system, "4.7.5", "260831071")

        # Assert
        assert url == (
            "https://github.com/musescore/MuseScore/releases/download/v4.7.5/"
            f"MuseScore-Studio-4.7.5.260831071{suffix}"
        )


class TestSeedConfiguration:
    def test_installs_plugin_and_enables_it_under_both_uri_schemes(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        layout = harness.layout_for("Linux", tmp_path)

        # Act
        harness.seed_configuration(layout)

        # Assert: plugin copied, enabled for 4.4 (muse://) and 4.5+ (musescore://)
        plugin = layout.plugins_dir / harness.PLUGIN_FILE
        assert plugin.read_text() == harness.PLUGIN_SOURCE.read_text()
        enabled = json.loads((layout.data_dir / "extensions/config.json").read_text())
        assert [entry["uri"] for entry in enabled] == list(harness.PLUGIN_URIS)
        assert all(
            entry["actions"] == [{"code": "main", "exec_point": "manually"}]
            for entry in enabled
        )

    def test_binds_shortcut_to_every_action_code_form(self, tmp_path: Path) -> None:
        # Arrange
        layout = harness.layout_for("Linux", tmp_path)

        # Act
        harness.seed_configuration(layout)

        # Assert
        shortcuts = (layout.data_dir / "shortcuts.xml").read_text()
        for code in harness.PLUGIN_ACTION_CODES:
            assert f"<key>{code}</key>" in shortcuts
        assert shortcuts.count(f"<seq>{harness.PLUGIN_SHORTCUT}</seq>") == len(
            harness.PLUGIN_ACTION_CODES
        )

    def test_suppresses_startup_dialogs_and_stale_session(self, tmp_path: Path) -> None:
        # Arrange
        layout = harness.layout_for("Linux", tmp_path)
        stale_session = layout.data_dir / "session"
        stale_session.mkdir(parents=True)
        (stale_session / "score.mscz").write_bytes(b"")

        # Act
        harness.seed_configuration(layout)

        # Assert
        settings = layout.settings_file.read_text()
        assert "hasCompletedFirstLaunchSetup=true" in settings
        assert "welcomeDialogShowOnStartup=false" in settings
        assert "welcomeDialogLastShownVersion=99.0.0" in settings
        assert not stale_session.exists()


class TestMuseScoreProcessPattern:
    def test_linux_matches_the_appimage_binary_path(self) -> None:
        # The AppImage's binary renames its process, so the pattern must be
        # something that survives in the command line.
        assert harness.musescore_process_pattern("Linux") == "bin/mscore4portable"

    def test_windows_matches_the_image_name(self) -> None:
        assert harness.musescore_process_pattern("Windows") == "MuseScore4.exe"
