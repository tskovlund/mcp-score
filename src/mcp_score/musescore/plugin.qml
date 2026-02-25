// MuseScore QML plugin — WebSocket server for mcp-score bridge.
// Install: copy to MuseScore's Plugins directory, enable in Plugins > Plugin Manager.
//
// This plugin opens a WebSocket server inside MuseScore, allowing the
// mcp-score Python server to read from and write to the active score.

import QtQuick 2.9
import MuseScore 3.0

MuseScore {
    id: root
    menuPath: "Plugins.MCP Score Bridge"
    description: "WebSocket bridge for mcp-score MCP server"
    version: "0.1.0"

    onRun: {
        console.log("mcp-score bridge plugin loaded — not yet implemented");
    }
}
