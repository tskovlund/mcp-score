# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Score generation via Claude Code skill (music21 -> MusicXML)
- MCP server with 18 tools for live score manipulation (MuseScore, Dorico, Sibelius)
- Multi-bridge architecture: MuseScore QML plugin, Dorico Remote Control, Sibelius Connect
- MuseScore 4 QML plugin with WebSocket bridge (19 commands)
- CLI install commands: `mcp-score install-skill`, `mcp-score install-plugin`
- Comprehensive test suite (145 tests)
- Full documentation (architecture, reference, getting-started)
- GitHub security: CodeQL scanning, branch protection, SECURITY.md
- Score metadata: subtitle (movementName), arranger (Contributor), copyright support
- Prompt request PR workflow in CONTRIBUTING.md

### Changed
- Skill now asks user for missing metadata (title, composer, arranger, subtitle, copyright) instead of silently using defaults
- Chord repetition intervals are context-aware: divides phrase length evenly instead of fixed "every 4 bars"
- Skill documents volta brackets (1st/2nd endings) via `spanner.RepeatBracket`
- Skill documents MuseScore subtitle/arranger display limitation (known issue, data is in MusicXML)
- Dependabot: bumped setup-uv 7.3.0→7.3.1, upload-artifact 4→7, download-artifact 4→8
