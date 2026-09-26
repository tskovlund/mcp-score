// MuseScore QML Plugin -- WebSocket server for mcp-score bridge.
//
// Install: copy this directory to MuseScore's Plugins directory, enable via
// Plugins > Manage plugins.
//
// Opens a WebSocket server inside MuseScore, allowing the mcp-score Python
// MCP server to read from and write to the active score by sending JSON
// commands and receiving JSON responses.
//
// Requires MuseScore Studio 4.4.2 or later. The server uses MuseScore's
// built-in plugin API (api.websocketserver), which replaced the QtWebSockets
// QML module that MuseScore stopped shipping in 4.4 (Qt 6).
//
// Protocol: each WebSocket message is a JSON object with a "command" field
// and optionally a "params" field. The response is always a JSON object with
// either a "result" field (on success) or an "error" field (on failure).
// The `commands` table below lists the commands; the modules implement them.

import QtQuick 2.15
import MuseScore 3.0

import "reading.js" as Reading
import "editing.js" as Editing
import "selection.js" as Selection
import "sequence.js" as Sequence

MuseScore {
    id: root
    title: "MCP Score Bridge"
    categoryCode: "composing-arranging-tools"
    description: "WebSocket bridge for mcp-score MCP server"
    version: "0.2.0"

    // A dialog keeps the plugin instance (and its server) alive for as long
    // as the window is open. MuseScore 4 does not support dock plugins.
    pluginType: "dialog"
    width: 360
    height: 120

    readonly property int serverPort: 8765
    readonly property string serverHost: "localhost"
    readonly property string logPrefix: "[mcp-score]"

    // Logical cursor position, maintained across commands. The MuseScore
    // Cursor object is re-created from this state for each command.
    property int cursorMeasure: 1   // 1-indexed measure number
    property int cursorStaff: 0     // 0-indexed staff index
    property int cursorVoice: 0     // voice (always 0 for now)

    // Human-readable server state, shown in the plugin window.
    property string statusText: "Starting..."

    // Command name -> implementation. Every implementation takes the
    // plugin (for the cursor state and MuseScore's API) and the params.
    readonly property var commands: ({
        "ping":                 Reading.ping,
        "getScore":             Reading.getScore,
        "getCursorInfo":        Reading.getCursorInfo,
        "goToMeasure":          Reading.goToMeasure,
        "goToStaff":            Reading.goToStaff,
        "addNote":              Editing.addNote,
        "addRehearsalMark":     Editing.addRehearsalMark,
        "setBarline":           Editing.setBarline,
        "setKeySignature":      Editing.setKeySignature,
        "setTimeSignature":     Editing.setTimeSignature,
        "setTempo":             Editing.setTempo,
        "addChordSymbol":       Editing.addChordSymbol,
        "addDynamic":           Editing.addDynamic,
        "appendMeasures":       Editing.appendMeasures,
        "selectCurrentMeasure": Selection.selectCurrentMeasure,
        "selectCustomRange":    Selection.selectCustomRange,
        "transpose":            Selection.transpose,
        "undo":                 Selection.undo,
        "processSequence":      Sequence.processSequence
    })

    // ── Command dispatch ────────────────────────────────────────────

    function handleMessage(message) {
        var request;
        try {
            request = JSON.parse(message);
        } catch (e) {
            return { error: "Invalid JSON: " + e.message };
        }

        var command = request.command;
        var params = request.params || {};

        if (!command) {
            return { error: "Missing 'command' field" };
        }

        console.log(logPrefix, "Command:", command);

        var implementation = commands[command];
        if (!implementation) {
            return { error: "Unknown command: " + command };
        }
        try {
            return implementation(root, params);
        } catch (e) {
            console.log(logPrefix, "Error handling '" + command + "':", e.message);
            return { error: e.message || String(e) };
        }
    }

    // ── WebSocket server ────────────────────────────────────────────

    /// True when this MuseScore build exposes the plugin WebSocket API.
    function hasWebSocketApi() {
        return typeof api !== "undefined"
            && api.websocketserver !== undefined
            && api.websocketserver !== null;
    }

    /// Start the WebSocket server via MuseScore's built-in plugin API.
    function startServer() {
        if (!hasWebSocketApi()) {
            statusText = "Error: this MuseScore build has no plugin WebSocket API.\n"
                + "MuseScore Studio 4.4.2 or later is required.";
            console.log(logPrefix, statusText);
            return;
        }

        api.websocketserver.listen(serverPort, function(clientId) {
            console.log(logPrefix, "Client connected:", clientId);
            api.websocketserver.onMessage(clientId, function(message) {
                var response = handleMessage(message);
                api.websocketserver.send(clientId, JSON.stringify(response));
            });
        });

        statusText = "Bridge running on ws://" + serverHost + ":" + serverPort + "\n"
            + "Keep this window open while using mcp-score.";
        console.log(logPrefix, "Bridge plugin started -- WebSocket server on port", serverPort);
    }

    // ── Plugin lifecycle ────────────────────────────────────────────

    onRun: {
        startServer();
    }

    // Status window. Closing it stops the plugin and the server with it.
    Rectangle {
        anchors.fill: parent
        color: "#ffffff"

        Text {
            anchors.fill: parent
            anchors.margins: 12
            text: root.statusText
            wrapMode: Text.WordWrap
            verticalAlignment: Text.AlignVCenter
        }
    }
}
