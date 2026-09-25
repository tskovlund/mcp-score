"""CLI entry point for mcp-score."""

from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path
from typing import NoReturn

from mcp_score.resources import PLUGIN_FILE, SKILL_DIRECTORY, package_path

__all__ = ["main"]

# ── Paths ─────────────────────────────────────────────────────────────

_SKILL_DEST = Path.home() / ".claude" / "skills" / "score-generate"

_PLUGIN_DIRS: dict[str, Path] = {
    "Darwin": Path.home() / "Documents" / "MuseScore4" / "Plugins",
    "Linux": Path.home() / "Documents" / "MuseScore4" / "Plugins",
    "Windows": Path.home() / "Documents" / "MuseScore4" / "Plugins",
}


# ── Helpers ───────────────────────────────────────────────────────────


def _copy_tree(source: Path, destination: Path) -> None:
    """Copy a directory tree, creating parents as needed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _copy_file(source: Path, destination: Path) -> None:
    """Copy a single file, creating parents as needed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


# ── Install commands ──────────────────────────────────────────────────


def install_skill() -> bool:
    """Install the score-generate skill to ~/.claude/skills/."""
    try:
        skill_dir = package_path(str(SKILL_DIRECTORY))
    except FileNotFoundError:
        sys.stderr.write("Error: skill files not found in package.\n")
        return False

    _copy_tree(skill_dir, _SKILL_DEST)
    print(f"Installed score-generate skill to {_SKILL_DEST}")  # noqa: T201
    print(f"  SKILL.md:       {_SKILL_DEST / 'SKILL.md'}")  # noqa: T201
    print(f"  instruments.md: {_SKILL_DEST / 'references' / 'instruments.md'}")  # noqa: T201
    return True


def install_plugin() -> bool:
    """Install the QML plugin to MuseScore's Plugins directory."""
    system = platform.system()
    plugin_dir = _PLUGIN_DIRS.get(system)

    if plugin_dir is None:
        sys.stderr.write(f"Error: unsupported platform '{system}'.\n")
        sys.stderr.write("Supported: macOS (Darwin), Linux, Windows.\n")
        sys.stderr.write(
            "Manual install: copy src/mcp_score/musescore/plugin.qml"
            " to your MuseScore Plugins directory.\n"
        )
        return False

    try:
        source = package_path(str(PLUGIN_FILE))
    except FileNotFoundError:
        sys.stderr.write("Error: plugin.qml not found in package.\n")
        return False

    destination = plugin_dir / "mcp-score-bridge.qml"
    _copy_file(source, destination)
    print(f"Installed MuseScore plugin to {destination}")  # noqa: T201
    print("Enable it in MuseScore: Plugins > Manage plugins > MCP Score Bridge")  # noqa: T201
    print("Requires MuseScore Studio 4.4.2 or later.")  # noqa: T201
    return True


def install_all() -> bool:
    """Install both the skill and the plugin."""
    skill_ok = install_skill()
    plugin_ok = install_plugin()
    return skill_ok and plugin_ok


# ── CLI entry point ───────────────────────────────────────────────────


def run_script(script_args: list[str]) -> NoReturn:
    """Run a Python script with the package's interpreter (has music21)."""
    import subprocess

    if not script_args:
        print("Usage: mcp-score run <script.py> [args...]")  # noqa: T201
        sys.exit(1)

    result = subprocess.run([sys.executable, *script_args])
    sys.exit(result.returncode)


_USAGE = """\
Usage: mcp-score <command>

Commands:
  serve            Run the MCP server (default)
  run <script>     Run a Python script with music21 available
  install          Install skill and MuseScore plugin
  install-skill    Install the score-generate skill to ~/.claude/skills/
  install-plugin   Install the QML plugin to MuseScore's Plugins directory
  help             Show this help message
"""


def main() -> NoReturn:
    """CLI entry point for mcp-score."""
    args = sys.argv[1:]
    command = args[0] if args else "serve"

    if command in ("serve", "--stdio"):
        # Import here to avoid loading heavy dependencies for install commands.
        from mcp_score.server import main as serve_main

        serve_main()
        sys.exit(0)

    if command == "run":
        run_script(args[1:])

    if command == "install":
        ok = install_all()
        sys.exit(0 if ok else 1)

    if command == "install-skill":
        ok = install_skill()
        sys.exit(0 if ok else 1)

    if command == "install-plugin":
        ok = install_plugin()
        sys.exit(0 if ok else 1)

    if command in ("help", "--help", "-h"):
        print(_USAGE)  # noqa: T201
        sys.exit(0)

    sys.stderr.write(f"Unknown command: {command}\n")
    sys.stderr.write(_USAGE)
    sys.exit(1)
