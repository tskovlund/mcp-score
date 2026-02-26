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
