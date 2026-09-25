"""Where MuseScore Studio 4 keeps user files.

MuseScore uses the same layout on macOS, Windows and Linux for the files
this project touches, so there is one answer per question here.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["PLUGIN_FILE_NAME", "plugins_directory"]

PLUGIN_FILE_NAME = "mcp-score-bridge.qml"
"""The bridge plugin's file name inside MuseScore's plugins directory."""


def plugins_directory(home: Path | None = None) -> Path:
    """MuseScore's user plugins directory (``~/Documents/MuseScore4/Plugins``)."""
    return (home or Path.home()) / "Documents" / "MuseScore4" / "Plugins"
