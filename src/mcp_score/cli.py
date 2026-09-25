"""The ``mcp-score`` command line.

``mcp-score`` with no command runs the MCP server. The other commands
install the extras (the score-generate skill for Claude Code and the
MuseScore bridge plugin) and run music21 scripts with the package's own
interpreter.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from mcp_score.musescore.paths import PLUGIN_FILE_NAME, plugins_directory
from mcp_score.resources import PLUGIN_FILE, SKILL_DIRECTORY, package_path

__all__ = ["build_parser", "install_plugin", "install_skill", "main", "run_script"]

SKILL_DESTINATION = Path.home() / ".claude" / "skills" / "score-generate"
"""Where Claude Code looks for user skills."""

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


# ── Commands ──────────────────────────────────────────────────────────


def install_skill(destination: Path = SKILL_DESTINATION) -> Path:
    """Copy the bundled score-generate skill to *destination*, replacing it.

    Raises:
        FileNotFoundError: When the skill files are not bundled.
    """
    source = package_path(str(SKILL_DIRECTORY))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination


def install_plugin(directory: Path | None = None) -> Path:
    """Copy the bridge plugin into MuseScore's plugins *directory*.

    Raises:
        FileNotFoundError: When the plugin file is not bundled.
    """
    source = package_path(str(PLUGIN_FILE))
    destination = (directory or plugins_directory()) / PLUGIN_FILE_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def run_script(script: str, arguments: list[str]) -> int:
    """Run a Python script with this interpreter, which has music21."""
    return subprocess.run([sys.executable, script, *arguments], check=False).returncode  # noqa: S603


def serve() -> int:
    """Run the MCP server over stdio until the client disconnects."""
    # Imported here so the install commands do not load the server stack.
    from mcp_score.server import main as serve_main

    serve_main()
    return EXIT_SUCCESS


# ── Argument parsing ──────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-score",
        description="MCP server for music notation; runs the server by default.",
    )
    commands = parser.add_subparsers(dest="command", metavar="<command>")
    commands.add_parser("serve", help="run the MCP server (the default)")
    run = commands.add_parser("run", help="run a Python script with music21 available")
    run.add_argument("script", help="the script to run")
    run.add_argument(
        "arguments", nargs=argparse.REMAINDER, help="arguments for the script"
    )
    commands.add_parser("install", help="install the skill and the MuseScore plugin")
    commands.add_parser(
        "install-skill", help="install the score-generate skill for Claude Code"
    )
    commands.add_parser(
        "install-plugin", help="install the bridge plugin into MuseScore"
    )
    return parser


def _report_skill(destination: Path) -> None:
    print(f"Installed the score-generate skill to {destination}")  # noqa: T201


def _report_plugin(destination: Path) -> None:
    print(f"Installed the MuseScore plugin to {destination}")  # noqa: T201
    print("Enable it in MuseScore: Plugins > Manage plugins > MCP Score Bridge.")  # noqa: T201
    print("Requires MuseScore Studio 4.4.2 or later.")  # noqa: T201


def _install(skill: bool, plugin: bool) -> int:
    """Run the requested installs, reporting each; missing files fail the command."""
    try:
        if skill:
            _report_skill(install_skill())
        if plugin:
            _report_plugin(install_plugin())
    except FileNotFoundError as error:
        sys.stderr.write(f"Error: {error}\n")
        return EXIT_FAILURE
    return EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    """Entry point: returns the process exit code."""
    args = build_parser().parse_args(argv)
    command: str | None = args.command
    if command is None or command == "serve":
        return serve()
    if command == "run":
        return run_script(args.script, args.arguments)
    return _install(
        skill=command in ("install", "install-skill"),
        plugin=command in ("install", "install-plugin"),
    )
