# MuseScore plugin setup

> How-to guide — install and configure the mcp-score MuseScore plugin for live manipulation.

## Overview

The MuseScore plugin runs inside MuseScore 4 and opens a WebSocket server on `localhost:8765`. The mcp-score Python server connects to this WebSocket to read from and write to the active score.

The plugin is only needed for **manipulation** tools (reading passages, arranging, transposing). **Generation** tools work without it — they produce MusicXML files that MuseScore can open.

## Installation

1. Locate your MuseScore plugins directory:
   - **macOS:** `~/Documents/MuseScore4/Plugins/`
   - **Linux:** `~/.local/share/MuseScore4/Plugins/`
   - **Windows:** `%APPDATA%/MuseScore4/Plugins/`

2. Copy the plugin file:
   ```bash
   cp src/mcp_score/musescore/plugin.qml ~/Documents/MuseScore4/Plugins/mcp-score-bridge.qml
   ```

3. In MuseScore, go to **Plugins > Plugin Manager** and enable "MCP Score Bridge"

4. Run the plugin: **Plugins > MCP Score Bridge**

The plugin will start a WebSocket server. The mcp-score Python server will connect automatically when you use manipulation tools.

## Troubleshooting

### Plugin doesn't appear in Plugin Manager

- Verify the `.qml` file is in the correct directory
- Restart MuseScore after adding the plugin

### WebSocket connection fails

- Ensure the plugin is running (check the MuseScore status bar)
- Verify no other application is using port 8765
- Check MuseScore's plugin console for error messages
