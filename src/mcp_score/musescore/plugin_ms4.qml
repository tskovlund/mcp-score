// MuseScore 4.4+ QML Plugin -- WebSocket client for mcp-score bridge.
//
// Install: copy to MuseScore's Plugins directory, enable via Plugin Manager.
// Requires: mcp-score serve must be running before the plugin is started.
//
// Connects outward to the Python mcp-score WebSocket server on localhost:8765.
// The Python server acts as the WebSocket server; the plugin dials in.
//
// Protocol: each WebSocket message is a JSON object with a "command" field
// and optionally a "params" field. The response is always a JSON object with
// either a "result" field (on success) or an "error" field (on failure).
//
// Supported commands:
//   ping, getScore, getCursorInfo, goToMeasure, goToStaff, addNote,
//   addRehearsalMark, setBarline, setKeySignature, setTimeSignature,
//   setTempo, addChordSymbol, addDynamic, appendMeasures,
//   selectCurrentMeasure, selectCustomRange, transpose, undo,
//   processSequence

import QtQuick 2.9
import MuseScore 3.0
import QtWebSockets 1.0

MuseScore {
    id: root
    menuPath: "Plugins.MCP Score Bridge"
    description: "WebSocket bridge for mcp-score MCP server"
    version: "0.1.0"

    // ===================================================================
    // Constants
    // ===================================================================

    readonly property int serverPort: 8765
    readonly property string serverHost: "localhost"
    readonly property string logPrefix: "[mcp-score]"

    // MuseScore internal tick counts (from fraction.h).
    readonly property int ticksPerWholeNote: 1920
    readonly property real secondsPerMinute: 60.0

    // Key signature bounds (circle of fifths).
    readonly property int minFifths: -7
    readonly property int maxFifths: 7

    // ===================================================================
    // Lookup tables
    // ===================================================================

    // Barline type string -> MuseScore enum value.
    readonly property var barlineTypes: ({
        "normal":         1,
        "double":         2,
        "startRepeat":    4,
        "endRepeat":      8,
        "endStartRepeat": 16,
        "final":          32,
        "dashed":         64,
        "dotted":         128,
        "tick":           256,
        "short":          512
    })

    // Dynamic marking -> MIDI velocity.
    readonly property var dynamicVelocities: ({
        "pppp": 10,  "ppp": 25,  "pp": 36,  "p": 49,   "mp": 64,
        "mf": 80,    "f": 96,    "ff": 112,  "fff": 120, "ffff": 127,
        "fp": 96,    "sfz": 112, "sffz": 120, "sfp": 112, "rfz": 112,
        "fz": 112
    })

    // Semitone -> diatonic interval (within one octave).
    // Used for chromatic transposition with correct enharmonic spelling.
    readonly property var semitoneToDiatonic: [0, 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6]

    // ===================================================================
    // WebSocket client
    // ===================================================================

    WebSocket {
        id: socket
        url: "ws://" + serverHost + ":" + serverPort
        active: false

        onStatusChanged: {
            if (status === WebSocket.Open) {
                console.warn(logPrefix, "Connected to mcp-score server");
                statusText.text = "Connected";
                statusText.color = "green";
            } else if (status === WebSocket.Closed) {
                console.warn(logPrefix, "Disconnected from mcp-score server -- retrying in 3s");
                statusText.text = "Connecting...";
                statusText.color = "orange";
                socket.active = false;
                reconnectTimer.start();
            } else if (status === WebSocket.Error) {
                console.warn(logPrefix, "WebSocket error:", socket.errorString);
                socket.active = false;
                // Closed will fire immediately after Error — let it handle the retry.
            }
        }

        onTextMessageReceived: function(message) {
            var response = handleMessage(message);
            socket.sendTextMessage(JSON.stringify(response));
        }
    }

    Timer {
        id: reconnectTimer
        interval: 3000
        repeat: false
        onTriggered: {
            console.warn(logPrefix, "Attempting reconnect...");
            socket.active = true;
        }
    }

    // ===================================================================
    // Internal cursor state
    // ===================================================================

    // Logical cursor position, maintained across commands. The MuseScore
    // Cursor object is re-created from this state for each command.

    property int cursorMeasure: 1   // 1-indexed measure number
    property int cursorStaff: 0     // 0-indexed staff index
    property int cursorVoice: 0     // voice (always 0 for now)

    // ===================================================================
    // Command dispatch
    // ===================================================================

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

        try {
            switch (command) {
                case "ping":                return handlePing();
                case "getScore":            return handleGetScore();
                case "getCursorInfo":       return handleGetCursorInfo();
                case "goToMeasure":         return handleGoToMeasure(params);
                case "goToStaff":           return handleGoToStaff(params);
                case "addNote":             return handleAddNote(params);
                case "addRehearsalMark":    return handleAddRehearsalMark(params);
                case "setBarline":          return handleSetBarline(params);
                case "setKeySignature":     return handleSetKeySignature(params);
                case "setTimeSignature":    return handleSetTimeSignature(params);
                case "setTempo":            return handleSetTempo(params);
                case "addChordSymbol":      return handleAddChordSymbol(params);
                case "addDynamic":          return handleAddDynamic(params);
                case "appendMeasures":      return handleAppendMeasures(params);
                case "selectCurrentMeasure": return handleSelectCurrentMeasure();
                case "selectCustomRange":   return handleSelectCustomRange(params);
                case "transpose":           return handleTranspose(params);
                case "undo":                return handleUndo();
                case "processSequence":     return handleProcessSequence(params);
                default:
                    return { error: "Unknown command: " + command };
            }
        } catch (e) {
            console.log(logPrefix, "Error handling '" + command + "':", e.message);
            return { error: e.message || String(e) };
        }
    }

    // ===================================================================
    // Guard helpers (reduce repetition in handlers)
    // ===================================================================

    /// Returns an error object if no score is open, or null if OK.
    function requireScore() {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        return null;
    }

    /// Returns a positioned cursor, or an error object if it cannot be created.
    function requireCursor() {
        var scoreErr = requireScore();
        if (scoreErr) return { cursor: null, error: scoreErr };

        var cursor = positionedCursor();
        if (!cursor) return { cursor: null, error: { error: "Could not position cursor" } };

        return { cursor: cursor, error: null };
    }

    // ===================================================================
    // Cursor positioning
    // ===================================================================

    /// Create a MuseScore Cursor at the current logical position.
    function positionedCursor() {
        if (!curScore) return null;
        var cursor = curScore.newCursor();
        cursor.staffIdx = cursorStaff;
        cursor.voice = cursorVoice;
        cursor.rewind(Cursor.SCORE_START);

        for (var i = 1; i < cursorMeasure; i++) {
            cursor.nextMeasure();
        }
        return cursor;
    }

    /// Navigate a raw cursor to a specific 1-indexed measure number.
    function advanceCursorToMeasure(cursor, measureNumber) {
        cursor.rewind(Cursor.SCORE_START);
        for (var i = 1; i < measureNumber; i++) {
            cursor.nextMeasure();
        }
    }

    // ===================================================================
    // Utility helpers
    // ===================================================================

    /// Count the total number of measures in the score.
    function countMeasures() {
        if (!curScore) return 0;
        var cursor = curScore.newCursor();
        cursor.rewind(Cursor.SCORE_START);
        var count = 0;
        while (cursor.measure) {
            count++;
            cursor.nextMeasure();
        }
        return count;
    }

    /// Get the 1-indexed measure number for a given tick position.
    function measureNumberAtTick(tick) {
        if (!curScore) return 0;
        var cursor = curScore.newCursor();
        cursor.rewind(Cursor.SCORE_START);
        var measureNumber = 1;
        while (cursor.measure) {
            var measureStart = cursor.tick;
            cursor.nextMeasure();
            var measureEnd = cursor.measure ? cursor.tick : Infinity;
            if (tick >= measureStart && tick < measureEnd) {
                return measureNumber;
            }
            measureNumber++;
        }
        return measureNumber;
    }

    /// Map a barline type string to the MuseScore enum value, or null.
    function barlineTypeFromString(typeString) {
        var value = barlineTypes[typeString];
        return (value !== undefined) ? value : null;
    }

    /// Parse a value to integer, returning null if the result is NaN.
    function safeParseInt(value) {
        var parsed = parseInt(value);
        return isNaN(parsed) ? null : parsed;
    }

    /// Describe a score element as a plain object for JSON serialization.
    function describeElement(element) {
        if (!element) return null;

        var info = { type: element.type };

        if (element.type === Element.CHORD) {
            var notes = [];
            for (var i = 0; i < element.notes.length; i++) {
                var note = element.notes[i];
                notes.push({
                    pitch: note.pitch,
                    tpc: note.tpc,
                    name: note.noteName || null
                });
            }
            info.notes = notes;
            info.duration = {
                numerator: element.duration.numerator,
                denominator: element.duration.denominator
            };
        } else if (element.type === Element.REST) {
            info.duration = {
                numerator: element.duration.numerator,
                denominator: element.duration.denominator
            };
        } else if (element.type === Element.NOTE) {
            info.pitch = element.pitch;
            info.tpc = element.tpc;
            info.name = element.noteName || null;
        }

        return info;
    }

    // ===================================================================
    // Command handlers -- read-only / navigation
    // ===================================================================

    function handlePing() {
        return { result: "pong" };
    }

    /// Return metadata about the currently open score.
    function handleGetScore() {
        var scoreErr = requireScore();
        if (scoreErr) return scoreErr;

        var parts = [];
        for (var i = 0; i < curScore.parts.length; i++) {
            var part = curScore.parts[i];
            parts.push({
                name: part.partName,
                startStaff: part.startStaff,
                endStaff: part.endStaff
            });
        }

        var cursor = curScore.newCursor();
        cursor.rewind(Cursor.SCORE_START);

        var keySig = (cursor.keySignature !== undefined) ? cursor.keySignature : null;

        var timeSig = null;
        if (cursor.timeSignature) {
            timeSig = {
                numerator: cursor.timeSignature.numerator,
                denominator: cursor.timeSignature.denominator
            };
        }

        return {
            result: {
                title: curScore.title || "",
                partCount: parts.length,
                parts: parts,
                measureCount: countMeasures(),
                keySignature: keySig,
                timeSignature: timeSig
            }
        };
    }

    /// Return the current logical cursor position and the element there.
    function handleGetCursorInfo() {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        var elementInfo = cursor.element ? describeElement(cursor.element) : null;

        var beat = null;
        if (cursor.measure && cursor.timeSignature) {
            var measureStartTick = cursor.measure.firstSegment.tick;
            var ticksPerBeat = ticksPerWholeNote / cursor.timeSignature.denominator;
            beat = Math.floor((cursor.tick - measureStartTick) / ticksPerBeat) + 1;
        }

        return {
            result: {
                measure: cursorMeasure,
                staff: cursorStaff,
                voice: cursorVoice,
                beat: beat,
                tick: cursor.tick,
                element: elementInfo
            }
        };
    }

    /// Move the logical cursor to the specified 1-indexed measure.
    function handleGoToMeasure(params) {
        var scoreErr = requireScore();
        if (scoreErr) return scoreErr;

        if (params.measure === undefined) {
            return { error: "Missing required parameter: measure" };
        }

        var measureNumber = safeParseInt(params.measure);
        if (measureNumber === null) {
            return { error: "Invalid value for measure: " + params.measure };
        }
        var totalMeasures = countMeasures();

        if (measureNumber < 1 || measureNumber > totalMeasures) {
            return { error: "Measure " + measureNumber + " out of range (1-" + totalMeasures + ")" };
        }

        cursorMeasure = measureNumber;
        return { result: { measure: cursorMeasure, staff: cursorStaff } };
    }

    /// Move the logical cursor to the specified 0-indexed staff.
    function handleGoToStaff(params) {
        var scoreErr = requireScore();
        if (scoreErr) return scoreErr;

        if (params.staff === undefined) {
            return { error: "Missing required parameter: staff" };
        }

        var staffIndex = safeParseInt(params.staff);
        if (staffIndex === null) {
            return { error: "Invalid value for staff: " + params.staff };
        }
        if (staffIndex < 0 || staffIndex >= curScore.nstaves) {
            return { error: "Staff " + staffIndex + " out of range (0-" + (curScore.nstaves - 1) + ")" };
        }

        cursorStaff = staffIndex;
        return { result: { measure: cursorMeasure, staff: cursorStaff } };
    }

    // ===================================================================
    // Command handlers -- score modification
    // ===================================================================

    /// Add a note at the current cursor position.
    /// Params: { pitch, duration?: { numerator, denominator }, advanceCursorAfterAction?: bool }
    function handleAddNote(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.pitch === undefined) {
            return { error: "Missing required parameter: pitch" };
        }

        var pitch = safeParseInt(params.pitch);
        if (pitch === null) {
            return { error: "Invalid value for pitch: " + params.pitch };
        }
        var numerator = 1;
        var denominator = 4;
        if (params.duration) {
            if (params.duration.numerator !== undefined) {
                numerator = safeParseInt(params.duration.numerator);
                if (numerator === null) return { error: "Invalid duration numerator" };
            }
            if (params.duration.denominator !== undefined) {
                denominator = safeParseInt(params.duration.denominator);
                if (denominator === null) return { error: "Invalid duration denominator" };
            }
        }
        var advance = (params.advanceCursorAfterAction !== false);

        curScore.startCmd("addNote");
        cursor.setDuration(numerator, denominator);
        cursor.addNote(pitch);
        curScore.endCmd();

        if (advance) {
            cursorMeasure = measureNumberAtTick(cursor.tick);
        }

        return {
            result: {
                pitch: pitch,
                duration: { numerator: numerator, denominator: denominator },
                measure: cursorMeasure,
                staff: cursorStaff
            }
        };
    }

    /// Add a rehearsal mark at the current cursor position.
    /// Params: { text }
    function handleAddRehearsalMark(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.text === undefined || params.text === "") {
            return { error: "Missing required parameter: text" };
        }

        if (!cursor.segment) {
            return { error: "No valid segment at cursor position" };
        }

        curScore.startCmd("addRehearsalMark");
        var rehearsalMark = newElement(Element.REHEARSAL_MARK);
        rehearsalMark.text = params.text;
        cursor.add(rehearsalMark);
        curScore.endCmd();

        return { result: { text: params.text, measure: cursorMeasure } };
    }

    /// Set the barline type at the current cursor position.
    /// Params: { type }
    function handleSetBarline(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.type === undefined) {
            return { error: "Missing required parameter: type" };
        }

        var barlineType = barlineTypeFromString(params.type);
        if (barlineType === null) {
            return { error: "Unknown barline type: " + params.type +
                ". Valid types: " + Object.keys(barlineTypes).join(", ") };
        }

        if (!cursor.measure) {
            return { error: "No valid measure at cursor position" };
        }

        curScore.startCmd("setBarline");
        var barline = newElement(Element.BAR_LINE);
        barline.barlineType = barlineType;
        cursor.add(barline);
        curScore.endCmd();

        return { result: { type: params.type, measure: cursorMeasure } };
    }

    /// Set the key signature at the current cursor position.
    /// Params: { fifths } (-7 to 7 on the circle of fifths)
    function handleSetKeySignature(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.fifths === undefined) {
            return { error: "Missing required parameter: fifths" };
        }

        var fifths = safeParseInt(params.fifths);
        if (fifths === null) {
            return { error: "Invalid value for fifths: " + params.fifths };
        }
        if (fifths < minFifths || fifths > maxFifths) {
            return { error: "fifths must be between " + minFifths + " and " + maxFifths + ", got: " + fifths };
        }
        if (!cursor.segment) {
            return { error: "No valid segment at cursor position" };
        }

        curScore.startCmd("setKeySignature");
        var keySig = newElement(Element.KEYSIG);
        keySig.key = fifths;
        cursor.add(keySig);
        curScore.endCmd();

        return { result: { fifths: fifths, measure: cursorMeasure } };
    }

    /// Set the time signature at the current cursor position.
    /// Params: { numerator, denominator }
    function handleSetTimeSignature(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.numerator === undefined || params.denominator === undefined) {
            return { error: "Missing required parameters: numerator and denominator" };
        }

        var numerator = safeParseInt(params.numerator);
        var denominator = safeParseInt(params.denominator);
        if (numerator === null || denominator === null) {
            return { error: "Invalid time signature values" };
        }
        if (!cursor.segment) {
            return { error: "No valid segment at cursor position" };
        }

        curScore.startCmd("setTimeSignature");
        var timeSig = newElement(Element.TIMESIG);
        timeSig.timesig = fraction(numerator, denominator);
        cursor.add(timeSig);
        curScore.endCmd();

        return { result: { numerator: numerator, denominator: denominator, measure: cursorMeasure } };
    }

    /// Set a tempo marking at the current cursor position.
    /// Params: { bpm, text? }
    function handleSetTempo(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.bpm === undefined) {
            return { error: "Missing required parameter: bpm" };
        }

        var bpm = safeParseInt(params.bpm);
        if (bpm === null) {
            return { error: "Invalid value for bpm: " + params.bpm };
        }
        var displayText = params.text || ("\u2669 = " + bpm);

        if (!cursor.segment) {
            return { error: "No valid segment at cursor position" };
        }

        curScore.startCmd("setTempo");
        var tempo = newElement(Element.TEMPO_TEXT);
        tempo.text = displayText;
        tempo.tempo = bpm / secondsPerMinute;
        tempo.followText = false;
        cursor.add(tempo);
        curScore.endCmd();

        return { result: { bpm: bpm, text: displayText, measure: cursorMeasure } };
    }

    /// Add a chord symbol at the current cursor position.
    /// Params: { text }
    function handleAddChordSymbol(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.text === undefined || params.text === "") {
            return { error: "Missing required parameter: text" };
        }

        if (!cursor.segment) {
            return { error: "No valid segment at cursor position" };
        }

        curScore.startCmd("addChordSymbol");
        var harmony = newElement(Element.HARMONY);
        harmony.text = params.text;
        cursor.add(harmony);
        curScore.endCmd();

        return { result: { text: params.text, measure: cursorMeasure } };
    }

    /// Add a dynamic marking at the current cursor position.
    /// Params: { type }
    function handleAddDynamic(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.type === undefined || params.type === "") {
            return { error: "Missing required parameter: type" };
        }

        if (!cursor.segment) {
            return { error: "No valid segment at cursor position" };
        }

        curScore.startCmd("addDynamic");
        var dynamic = newElement(Element.DYNAMIC);
        dynamic.text = params.type;
        if (dynamicVelocities[params.type] !== undefined) {
            dynamic.velocity = dynamicVelocities[params.type];
        }
        cursor.add(dynamic);
        curScore.endCmd();

        return { result: { type: params.type, measure: cursorMeasure } };
    }

    /// Append empty measures to the end of the score.
    /// Params: { count }
    function handleAppendMeasures(params) {
        var scoreErr = requireScore();
        if (scoreErr) return scoreErr;

        if (params.count === undefined) {
            return { error: "Missing required parameter: count" };
        }

        var count = safeParseInt(params.count);
        if (count === null || count < 1) {
            return { error: "count must be at least 1, got: " + count };
        }

        curScore.startCmd("appendMeasures");
        curScore.appendMeasures(count);
        curScore.endCmd();

        return { result: { count: count, totalMeasures: countMeasures() } };
    }

    // ===================================================================
    // Command handlers -- selection and transposition
    // ===================================================================

    /// Select all elements in the measure at the current cursor position.
    function handleSelectCurrentMeasure() {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (!cursor.measure) {
            return { error: "No measure at current cursor position" };
        }

        var measureStart = cursor.measure.firstSegment.tick;
        var measureEnd = cursor.measure.lastSegment.tick + 1;

        curScore.startCmd("selectCurrentMeasure");
        curScore.selection.selectRange(
            measureStart, measureEnd,
            cursorStaff, cursorStaff + 1
        );
        curScore.endCmd();

        return { result: { measure: cursorMeasure, staff: cursorStaff } };
    }

    /// Select a range of measures and staves.
    /// Params: { startMeasure, endMeasure, startStaff, endStaff }
    /// Measures are 1-indexed (inclusive). Staves are 0-indexed (inclusive).
    function handleSelectCustomRange(params) {
        var scoreErr = requireScore();
        if (scoreErr) return scoreErr;

        var startMeasure = parseInt(params.startMeasure);
        var endMeasure = parseInt(params.endMeasure);
        var startStaff = parseInt(params.startStaff);
        var endStaff = parseInt(params.endStaff);

        if (isNaN(startMeasure) || isNaN(endMeasure) ||
            isNaN(startStaff) || isNaN(endStaff)) {
            return { error: "Missing required parameters: startMeasure, endMeasure, startStaff, endStaff" };
        }

        var totalMeasures = countMeasures();
        if (startMeasure < 1 || startMeasure > totalMeasures ||
            endMeasure < 1 || endMeasure > totalMeasures ||
            startMeasure > endMeasure) {
            return { error: "Invalid measure range: " + startMeasure + "-" + endMeasure +
                " (score has " + totalMeasures + " measures)" };
        }
        if (startStaff < 0 || startStaff >= curScore.nstaves ||
            endStaff < 0 || endStaff >= curScore.nstaves ||
            startStaff > endStaff) {
            return { error: "Invalid staff range: " + startStaff + "-" + endStaff +
                " (score has " + curScore.nstaves + " staves)" };
        }

        // Find tick positions for the measure range.
        var cursor = curScore.newCursor();
        advanceCursorToMeasure(cursor, startMeasure);
        var startTick = cursor.tick;

        for (var j = startMeasure; j <= endMeasure; j++) {
            cursor.nextMeasure();
        }
        var endTick = cursor.measure ? cursor.tick : curScore.lastSegment.tick + 1;

        curScore.startCmd("selectCustomRange");
        curScore.selection.selectRange(
            startTick, endTick,
            startStaff, endStaff + 1  // selectRange uses exclusive end for staves
        );
        curScore.endCmd();

        return {
            result: {
                startMeasure: startMeasure,
                endMeasure: endMeasure,
                startStaff: startStaff,
                endStaff: endStaff
            }
        };
    }

    /// Transpose the current selection by a number of semitones.
    /// Params: { semitones }
    /// Requires an active selection (use selectCurrentMeasure or selectCustomRange first).
    function handleTranspose(params) {
        var scoreErr = requireScore();
        if (scoreErr) return scoreErr;

        if (params.semitones === undefined) {
            return { error: "Missing required parameter: semitones" };
        }

        var semitones = safeParseInt(params.semitones);
        if (semitones === null) {
            return { error: "Invalid value for semitones: " + params.semitones };
        }

        if (!curScore.selection || !curScore.selection.elements ||
            curScore.selection.elements.length === 0) {
            return { error: "No active selection. Use selectCurrentMeasure or selectCustomRange first." };
        }

        var direction = semitones >= 0 ? 0 : 1;
        var absSemitones = Math.abs(semitones);

        // Map semitones to diatonic + chromatic interval pair for correct
        // enharmonic spelling in the transposition.
        var diatonicInterval = semitoneToDiatonic[absSemitones % 12]
            + Math.floor(absSemitones / 12) * 7;

        curScore.startCmd("transpose");
        // transpose(mode, direction, key, diatonicInterval, chromaticInterval,
        //           transposeKeySignatures, transposeChordNames)
        // mode 0 = by interval, direction 0 = up / 1 = down, key 0 = unused
        curScore.transpose(0, direction, 0, diatonicInterval, absSemitones, true, true);
        curScore.endCmd();

        return { result: { semitones: semitones } };
    }

    /// Undo the last action.
    function handleUndo() {
        var scoreErr = requireScore();
        if (scoreErr) return scoreErr;

        cmd("undo");

        // Clamp cursor to valid bounds -- undo may have changed the score
        // structure (removed measures, changed staves).
        var totalMeasures = countMeasures();
        if (totalMeasures > 0 && cursorMeasure > totalMeasures) {
            cursorMeasure = totalMeasures;
        }
        if (curScore.nstaves > 0 && cursorStaff >= curScore.nstaves) {
            cursorStaff = curScore.nstaves - 1;
        }

        return { result: "ok" };
    }

    // ===================================================================
    // Command handler -- processSequence (atomic batch execution)
    // ===================================================================

    /// Execute multiple actions atomically in a single undo group.
    /// If any action fails, all preceding actions are rolled back.
    ///
    /// Params: { sequence: [{ action, params }, ...] }
    function handleProcessSequence(params) {
        var scoreErr = requireScore();
        if (scoreErr) return scoreErr;

        if (!params.sequence || !Array.isArray(params.sequence)) {
            return { error: "Missing required parameter: sequence (array of {action, params})" };
        }

        var sequence = params.sequence;
        if (sequence.length === 0) {
            return { result: { results: [], count: 0 } };
        }

        var results = [];

        // Single startCmd/endCmd wraps all steps into one undo group.
        curScore.startCmd("processSequence");

        for (var i = 0; i < sequence.length; i++) {
            var step = sequence[i];
            var action = step.action;
            var actionParams = step.params || {};

            if (!action) {
                curScore.endCmd();
                cmd("undo");
                return {
                    error: "Step " + i + " is missing 'action' field",
                    failedIndex: i,
                    results: results
                };
            }

            var stepResult;
            try {
                stepResult = executeSequenceStep(action, actionParams);
            } catch (e) {
                curScore.endCmd();
                cmd("undo");
                return {
                    error: "Step " + i + " (" + action + ") failed: " + (e.message || String(e)),
                    failedAction: action,
                    failedIndex: i,
                    results: results
                };
            }

            if (stepResult.error) {
                curScore.endCmd();
                cmd("undo");
                return {
                    error: "Step " + i + " (" + action + ") failed: " + stepResult.error,
                    failedAction: action,
                    failedIndex: i,
                    results: results
                };
            }

            results.push(stepResult.result);
        }

        curScore.endCmd();

        return { result: { results: results, count: results.length } };
    }

    /// Execute a single step within processSequence WITHOUT its own
    /// startCmd/endCmd (the caller manages the undo group).
    function executeSequenceStep(action, params) {
        switch (action) {
            case "ping":
                return { result: "pong" };

            case "goToMeasure": {
                if (params.measure === undefined)
                    return { error: "Missing required parameter: measure" };
                var measureNum = safeParseInt(params.measure);
                if (measureNum === null)
                    return { error: "Invalid value for measure: " + params.measure };
                var total = countMeasures();
                if (measureNum < 1 || measureNum > total)
                    return { error: "Measure " + measureNum + " out of range (1-" + total + ")" };
                cursorMeasure = measureNum;
                return { result: { measure: cursorMeasure, staff: cursorStaff } };
            }

            case "goToStaff": {
                if (params.staff === undefined)
                    return { error: "Missing required parameter: staff" };
                var staffIdx = safeParseInt(params.staff);
                if (staffIdx === null)
                    return { error: "Invalid value for staff: " + params.staff };
                if (staffIdx < 0 || staffIdx >= curScore.nstaves)
                    return { error: "Staff " + staffIdx + " out of range (0-" + (curScore.nstaves - 1) + ")" };
                cursorStaff = staffIdx;
                return { result: { measure: cursorMeasure, staff: cursorStaff } };
            }

            case "addNote": {
                if (params.pitch === undefined)
                    return { error: "Missing required parameter: pitch" };
                var pitch = safeParseInt(params.pitch);
                if (pitch === null)
                    return { error: "Invalid value for pitch: " + params.pitch };
                var noteNum = 1;
                var noteDen = 4;
                if (params.duration) {
                    if (params.duration.numerator !== undefined) {
                        noteNum = safeParseInt(params.duration.numerator);
                        if (noteNum === null) return { error: "Invalid duration numerator" };
                    }
                    if (params.duration.denominator !== undefined) {
                        noteDen = safeParseInt(params.duration.denominator);
                        if (noteDen === null) return { error: "Invalid duration denominator" };
                    }
                }
                var advance = (params.advanceCursorAfterAction !== false);
                var noteCursor = positionedCursor();
                if (!noteCursor) return { error: "Could not position cursor" };
                noteCursor.setDuration(noteNum, noteDen);
                noteCursor.addNote(pitch);
                if (advance) {
                    cursorMeasure = measureNumberAtTick(noteCursor.tick);
                }
                return { result: { pitch: pitch, duration: { numerator: noteNum, denominator: noteDen }, measure: cursorMeasure } };
            }

            case "addRehearsalMark": {
                if (!params.text)
                    return { error: "Missing required parameter: text" };
                var rmCursor = positionedCursor();
                if (!rmCursor) return { error: "Could not position cursor" };
                if (!rmCursor.segment) return { error: "No valid segment at cursor position" };
                var rehearsalMark = newElement(Element.REHEARSAL_MARK);
                rehearsalMark.text = params.text;
                rmCursor.add(rehearsalMark);
                return { result: { text: params.text, measure: cursorMeasure } };
            }

            case "setBarline": {
                if (!params.type)
                    return { error: "Missing required parameter: type" };
                var barlineValue = barlineTypeFromString(params.type);
                if (barlineValue === null)
                    return { error: "Unknown barline type: " + params.type };
                var blCursor = positionedCursor();
                if (!blCursor) return { error: "Could not position cursor" };
                if (!blCursor.measure) return { error: "No valid measure at cursor position" };
                var barline = newElement(Element.BAR_LINE);
                barline.barlineType = barlineValue;
                blCursor.add(barline);
                return { result: { type: params.type, measure: cursorMeasure } };
            }

            case "setKeySignature": {
                if (params.fifths === undefined)
                    return { error: "Missing required parameter: fifths" };
                var fifths = safeParseInt(params.fifths);
                if (fifths === null)
                    return { error: "Invalid value for fifths: " + params.fifths };
                if (fifths < minFifths || fifths > maxFifths)
                    return { error: "fifths must be between " + minFifths + " and " + maxFifths };
                var ksCursor = positionedCursor();
                if (!ksCursor) return { error: "Could not position cursor" };
                if (!ksCursor.segment) return { error: "No valid segment at cursor position" };
                var keySig = newElement(Element.KEYSIG);
                keySig.key = fifths;
                ksCursor.add(keySig);
                return { result: { fifths: fifths, measure: cursorMeasure } };
            }

            case "setTimeSignature": {
                if (params.numerator === undefined || params.denominator === undefined)
                    return { error: "Missing required parameters: numerator and denominator" };
                var tsNum = safeParseInt(params.numerator);
                var tsDen = safeParseInt(params.denominator);
                if (tsNum === null || tsDen === null)
                    return { error: "Invalid time signature values" };
                var tsCursor = positionedCursor();
                if (!tsCursor) return { error: "Could not position cursor" };
                if (!tsCursor.segment) return { error: "No valid segment at cursor position" };
                var timeSig = newElement(Element.TIMESIG);
                timeSig.timesig = fraction(tsNum, tsDen);
                tsCursor.add(timeSig);
                return { result: { numerator: tsNum, denominator: tsDen, measure: cursorMeasure } };
            }

            case "setTempo": {
                if (params.bpm === undefined)
                    return { error: "Missing required parameter: bpm" };
                var bpm = safeParseInt(params.bpm);
                if (bpm === null)
                    return { error: "Invalid value for bpm: " + params.bpm };
                var tempoText = params.text || ("\u2669 = " + bpm);
                var tempoCursor = positionedCursor();
                if (!tempoCursor) return { error: "Could not position cursor" };
                if (!tempoCursor.segment) return { error: "No valid segment at cursor position" };
                var tempoMark = newElement(Element.TEMPO_TEXT);
                tempoMark.text = tempoText;
                tempoMark.tempo = bpm / secondsPerMinute;
                tempoMark.followText = false;
                tempoCursor.add(tempoMark);
                return { result: { bpm: bpm, text: tempoText, measure: cursorMeasure } };
            }

            case "addChordSymbol": {
                if (!params.text)
                    return { error: "Missing required parameter: text" };
                var chordCursor = positionedCursor();
                if (!chordCursor) return { error: "Could not position cursor" };
                if (!chordCursor.segment) return { error: "No valid segment at cursor position" };
                var harmony = newElement(Element.HARMONY);
                harmony.text = params.text;
                chordCursor.add(harmony);
                return { result: { text: params.text, measure: cursorMeasure } };
            }

            case "addDynamic": {
                if (!params.type)
                    return { error: "Missing required parameter: type" };
                var dynCursor = positionedCursor();
                if (!dynCursor) return { error: "Could not position cursor" };
                if (!dynCursor.segment) return { error: "No valid segment at cursor position" };
                var dynamic = newElement(Element.DYNAMIC);
                dynamic.text = params.type;
                if (dynamicVelocities[params.type] !== undefined) {
                    dynamic.velocity = dynamicVelocities[params.type];
                }
                dynCursor.add(dynamic);
                return { result: { type: params.type, measure: cursorMeasure } };
            }

            case "appendMeasures": {
                if (params.count === undefined)
                    return { error: "Missing required parameter: count" };
                var appendCount = safeParseInt(params.count);
                if (appendCount === null || appendCount < 1)
                    return { error: "count must be at least 1" };
                curScore.appendMeasures(appendCount);
                return { result: { count: appendCount, totalMeasures: countMeasures() } };
            }

            case "selectCurrentMeasure": {
                var selCursor = positionedCursor();
                if (!selCursor) return { error: "Could not position cursor" };
                if (!selCursor.measure) return { error: "No measure at current cursor position" };
                var selStart = selCursor.measure.firstSegment.tick;
                var selEnd = selCursor.measure.lastSegment.tick + 1;
                curScore.selection.selectRange(selStart, selEnd, cursorStaff, cursorStaff + 1);
                return { result: { measure: cursorMeasure, staff: cursorStaff } };
            }

            case "selectCustomRange": {
                var srStartMeasure = safeParseInt(params.startMeasure);
                var srEndMeasure = safeParseInt(params.endMeasure);
                var srStartStaff = safeParseInt(params.startStaff);
                var srEndStaff = safeParseInt(params.endStaff);
                if (srStartMeasure === null || srEndMeasure === null ||
                    srStartStaff === null || srEndStaff === null)
                    return { error: "Missing required parameters: startMeasure, endMeasure, startStaff, endStaff" };
                var srTotal = countMeasures();
                if (srStartMeasure < 1 || srStartMeasure > srTotal ||
                    srEndMeasure < 1 || srEndMeasure > srTotal ||
                    srStartMeasure > srEndMeasure)
                    return { error: "Invalid measure range: " + srStartMeasure + "-" + srEndMeasure };
                if (srStartStaff < 0 || srStartStaff >= curScore.nstaves ||
                    srEndStaff < 0 || srEndStaff >= curScore.nstaves ||
                    srStartStaff > srEndStaff)
                    return { error: "Invalid staff range: " + srStartStaff + "-" + srEndStaff };
                var srCursor = curScore.newCursor();
                advanceCursorToMeasure(srCursor, srStartMeasure);
                var srStartTick = srCursor.tick;
                for (var k = srStartMeasure; k <= srEndMeasure; k++) {
                    srCursor.nextMeasure();
                }
                var srEndTick = srCursor.measure ? srCursor.tick : curScore.lastSegment.tick + 1;
                curScore.selection.selectRange(srStartTick, srEndTick, srStartStaff, srEndStaff + 1);
                return { result: { startMeasure: srStartMeasure, endMeasure: srEndMeasure, startStaff: srStartStaff, endStaff: srEndStaff } };
            }

            case "transpose": {
                if (params.semitones === undefined)
                    return { error: "Missing required parameter: semitones" };
                var trSemitones = safeParseInt(params.semitones);
                if (trSemitones === null)
                    return { error: "Invalid value for semitones: " + params.semitones };
                if (!curScore.selection || !curScore.selection.elements ||
                    curScore.selection.elements.length === 0)
                    return { error: "No active selection. Use selectCurrentMeasure or selectCustomRange first." };
                var trDirection = trSemitones >= 0 ? 0 : 1;
                var trAbs = Math.abs(trSemitones);
                var trDiatonic = semitoneToDiatonic[trAbs % 12] + Math.floor(trAbs / 12) * 7;
                curScore.transpose(0, trDirection, 0, trDiatonic, trAbs, true, true);
                return { result: { semitones: trSemitones } };
            }

            default:
                return { error: "Unknown action in sequence: " + action };
        }
    }

    // ===================================================================
    // Plugin lifecycle
    // ===================================================================

    onRun: {
        console.warn(logPrefix, "Bridge plugin started -- connecting to mcp-score server on port", serverPort);
        statusWindow.show();
        socket.active = true;
    }

    // ===================================================================
    // Status window
    // ===================================================================

    Window {
        id: statusWindow
        title: "MCP Score Bridge"
        width: 300
        height: 80
        flags: Qt.Tool | Qt.WindowStaysOnTopHint

        Rectangle {
            anchors.fill: parent
            color: "#1e1e1e"

            Column {
                anchors.centerIn: parent
                spacing: 4

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "MCP Score Bridge"
                    color: "#cccccc"
                    font.pixelSize: 11
                }

                Text {
                    id: statusText
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Connecting..."
                    color: "orange"
                    font.pixelSize: 13
                    font.bold: true
                }
            }
        }
    }
}
