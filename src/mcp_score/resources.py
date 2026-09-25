"""Locate files bundled with the mcp_score package (skill, plugin)."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

__all__ = ["PLUGIN_FILE", "SKILL_DIRECTORY", "package_path"]

# Both paths are relative to the package root when installed from a wheel
# and to the repository root in a development checkout.
SKILL_DIRECTORY = Path(".claude") / "skills" / "score-generate"
PLUGIN_FILE = Path("musescore") / "plugin.qml"


def package_path(resource_path: str) -> Path:
    """Resolve a path relative to the installed mcp_score package.

    Falls back to the source tree layout for development installs.
    """
    # importlib.resources works for installed packages.
    anchor = importlib.resources.files("mcp_score")
    package_dir = Path(str(anchor))

    # When installed via pip, the skill files are bundled inside the wheel
    # (see [tool.hatch.build.targets.wheel.force-include] in pyproject.toml),
    # so they end up under the package directory.
    candidate = package_dir / resource_path
    if candidate.exists():
        return candidate

    # Development: resolve from source tree.
    # package_dir = <repo>/src/mcp_score -> <repo>
    project_root = package_dir.parent.parent
    candidate = project_root / resource_path
    if candidate.exists():
        return candidate

    # Last resort: try relative to this file itself.
    module_dir = Path(__file__).resolve().parent
    candidate = module_dir / resource_path
    if candidate.exists():
        return candidate

    error_message = f"Cannot find bundled resource: {resource_path}"
    raise FileNotFoundError(error_message)
