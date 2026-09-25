# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- Score generation via Claude Code skill (music21 -> MusicXML)
- `generate_score` and `score_generation_guide` MCP tools plus a `score-generate` MCP prompt, so score generation works in any MCP client
- MCP server with 16 tools for live score manipulation (MuseScore, Dorico)
- Multi-bridge architecture: MuseScore QML plugin, Dorico Remote Control
- MuseScore 4 QML plugin with WebSocket bridge (19 commands)
- CLI install commands: `mcp-score install-skill`, `mcp-score install-plugin`
- Comprehensive test suite (107 tests)
- Full documentation (architecture, reference, getting-started)
- GitHub security: CodeQL scanning, branch protection, SECURITY.md
- Score metadata: subtitle (movementName), arranger (Contributor), copyright support
- Prompt request PR workflow in CONTRIBUTING.md
- `render_score` tool: export PDF, PNG, MIDI, MP3, WAV or MusicXML from a score file through the MuseScore command line, located via `MCP_SCORE_MUSESCORE_PATH`, PATH or the platform default install
- Integration tests against real MuseScore Studio installs (headless `render_score` export and the live plugin bridge) on Linux (4.4, 4.6, 4.7), Windows and macOS, run by the `Integration` workflow and locally via `scripts/musescore_harness.py`

### Fixed

- MuseScore plugin: `addChordSymbol` and `setBarline` no longer crash MuseScore Studio 4 (chord symbols get their text after insertion; bar lines change the measure's end bar line or repeat flags instead of being inserted through the cursor)
- MuseScore plugin: `undo` now works on every supported version (4.7 renamed the action to `action://notation/undo`) and `transpose` no longer depends on the removed `Score.transpose` API
- MuseScore plugin: a failed `processSequence` rolls back the score and cursor instead of leaving the completed steps behind
- MuseScore plugin now loads on MuseScore Studio 4.4.2+ (Qt 6). It uses MuseScore's built-in `api.websocketserver` instead of the `QtWebSockets` QML module, which MuseScore stopped shipping in 4.4. Runs as a dialog plugin with a status window (dock plugins are unsupported in MuseScore 4). Fixes #78

### Changed

- Migrated from the `mcp` Python SDK v1 to v2 (`FastMCP` renamed to `MCPServer`, `mcp.server.fastmcp` import path replaced by `mcp.server.mcpserver`)
- Skill now asks user for missing metadata (title, composer, arranger, subtitle, copyright) instead of silently using defaults
- Chord repetition intervals are context-aware: divides phrase length evenly instead of fixed "every 4 bars"
- Skill documents volta brackets (1st/2nd endings) via `spanner.RepeatBracket`
- Skill documents MuseScore subtitle/arranger display limitation (known issue, data is in MusicXML)
- Dependabot: bumped setup-uv 7.3.0→7.3.1, upload-artifact 4→7, download-artifact 4→8
- Dorico support labelled experimental

### Removed

- Sibelius bridge and `connect_to_sibelius` tool (out of scope)
