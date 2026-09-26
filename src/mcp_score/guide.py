"""The score-generate skill as one document for MCP clients.

Claude Code reads the skill from disk. Every other client gets the same
files through the ``score_generation_guide`` tool and the ``score-generate``
prompt, concatenated here behind a preamble that maps the skill's
"save and run" steps onto the ``generate_score`` tool.
"""

from __future__ import annotations

from pathlib import Path

from mcp_score.resources import SKILL_DIRECTORY, package_path

__all__ = ["load_guide"]

_GUIDE_FILES: tuple[Path, ...] = (
    Path("SKILL.md"),
    Path("references") / "instruments.md",
    Path("references") / "template.py",
)
"""Skill files concatenated into the guide, relative to the skill directory."""

_GUIDE_PREAMBLE = """\
# Score generation guide

This is the bundled `score-generate` skill that Claude Code uses, served so
any MCP client can follow the same instructions.

When you read this through MCP, replace the skill's "save to /tmp and run
`mcp-score run`" steps with the `generate_score` tool: pass the complete
music21 script as the `script` argument. The tool runs it in a working
directory of its own and returns the absolute paths of the files it created,
so end the script with `score.write("musicxml", fp="<Title>.musicxml")`
(a plain file name, relative to the working directory).
"""


def load_guide() -> str:
    """The skill files as one guide document, with the MCP preamble first.

    Raises:
        FileNotFoundError: When a bundled skill file is missing.
    """
    skill_directory = package_path(str(SKILL_DIRECTORY))
    sections: list[str] = [_GUIDE_PREAMBLE]
    for relative_path in _GUIDE_FILES:
        file_path = skill_directory / relative_path
        if not file_path.is_file():
            error_message = f"Cannot find bundled skill file: {file_path}"
            raise FileNotFoundError(error_message)
        content = file_path.read_text(encoding="utf-8")
        if file_path.suffix == ".py":
            content = f"```python\n{content}\n```"
        sections.append(f"---\n\n# {relative_path.as_posix()}\n\n{content}")
    return "\n\n".join(sections)
