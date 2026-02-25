// MuseScore QML plugin — WebSocket server for mcp-score bridge.
// Install: copy to MuseScore's Plugins directory, enable in Plugins > Plugin Manager.
//
// This plugin opens a WebSocket server inside MuseScore on port 8765,
// allowing the mcp-score Python MCP server to read from and write to the
// active score by sending JSON commands and receiving JSON responses.
//
// Protocol: each WebSocket message is a JSON object with a "command" field
// and optionally a "params" field. The response is always a JSON object with
// either a "result" field (on success) or an "error" field (on failure).

import QtQuick 2.9
import MuseScore 3.0
import QtWebSockets 1.0

MuseScore {
    id: root
    menuPath: "Plugins.MCP Score Bridge"
    description: "WebSocket bridge for mcp-score MCP server"
    version: "0.1.0"

    // Keep the plugin running after onRun (required for persistent server).
    pluginType: "dock"
    dockArea: "bottom"
    implicitWidth: 0
    implicitHeight: 0

    // -----------------------------------------------------------------------
    // WebSocket server
    // -----------------------------------------------------------------------

    WebSocketServer {
        id: server
        port: 8765
        listen: true
        name: "mcp-score-bridge"

        onClientConnected: function(webSocket) {
            console.log("[mcp-score] Client connected");
            webSocket.onTextMessageReceived.connect(function(message) {
                var response = handleMessage(message);
                webSocket.sendTextMessage(JSON.stringify(response));
            });
            webSocket.onStatusChanged.connect(function(status) {
                if (status === WebSocket.Closed) {
                    console.log("[mcp-score] Client disconnected");
                }
            });
        }

        onErrorStringChanged: {
            console.log("[mcp-score] Server error: " + errorString);
        }
    }

    // -----------------------------------------------------------------------
    // Command dispatch
    // -----------------------------------------------------------------------

    /**
     * Parse an incoming JSON message and dispatch to the appropriate handler.
     * Returns a response object with either "result" or "error".
     */
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

        console.log("[mcp-score] Command: " + command);

        try {
            switch (command) {
                case "ping":               return handlePing();
                case "getScore":           return handleGetScore();
                case "getCursorInfo":      return handleGetCursorInfo();
                case "goToMeasure":        return handleGoToMeasure(params);
                case "goToStaff":          return handleGoToStaff(params);
                case "addNote":            return handleAddNote(params);
                case "addRehearsalMark":   return handleAddRehearsalMark(params);
                case "setBarline":         return handleSetBarline(params);
                case "setKeySignature":    return handleSetKeySignature(params);
                case "setTimeSignature":   return handleSetTimeSignature(params);
                case "setTempo":           return handleSetTempo(params);
                case "addChordSymbol":     return handleAddChordSymbol(params);
                case "addDynamic":         return handleAddDynamic(params);
                case "appendMeasures":     return handleAppendMeasures(params);
                case "selectCurrentMeasure": return handleSelectCurrentMeasure();
                case "selectCustomRange":  return handleSelectCustomRange(params);
                case "transpose":          return handleTranspose(params);
                case "undo":               return handleUndo();
                case "processSequence":    return handleProcessSequence(params);
                default:
                    return { error: "Unknown command: " + command };
            }
        } catch (e) {
            console.log("[mcp-score] Error handling '" + command + "': " + e.message);
            return { error: e.message || String(e) };
        }
    }

    // -----------------------------------------------------------------------
    // Internal cursor state
    // -----------------------------------------------------------------------

    // We maintain a logical cursor position (measure number and staff index)
    // so that sequential operations work predictably. The MuseScore Cursor
    // object is re-created from this state for each command.

    property int cursorMeasure: 1   // 1-indexed measure number
    property int cursorStaff: 0     // 0-indexed staff index
    property int cursorVoice: 0     // voice (always 0 for now)

    /**
     * Create a fresh MuseScore Cursor positioned at the current logical
     * cursor location (cursorMeasure, cursorStaff, cursorVoice).
     * Returns null if there is no active score.
     */
    function positionedCursor() {
        if (!curScore) return null;
        var cursor = curScore.newCursor();
        cursor.staffIdx = cursorStaff;
        cursor.voice = cursorVoice;
        cursor.rewind(Cursor.SCORE_START);

        // Advance to the target measure (1-indexed, so advance measure-1 times).
        for (var i = 1; i < cursorMeasure; i++) {
            cursor.nextMeasure();
        }
        return cursor;
    }

    // -----------------------------------------------------------------------
    // Utility helpers
    // -----------------------------------------------------------------------

    /**
     * Count the total number of measures in the score.
     */
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

    /**
     * Get the measure number (1-indexed) for a given tick position.
     */
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

    /**
     * Map a duration fraction (numerator/denominator) to a MuseScore duration
     * constant. Common durations:
     *   1/1 = whole, 1/2 = half, 1/4 = quarter, 1/8 = eighth,
     *   1/16 = sixteenth, 1/32 = thirty-second, 1/64 = sixty-fourth
     * Dotted durations: 3/8 = dotted quarter, 3/4 = dotted half, etc.
     */
    function fractionToDuration(numerator, denominator) {
        // MuseScore internal duration values (from fraction.h):
        //   whole = 1920, half = 960, quarter = 480, eighth = 240,
        //   16th = 120, 32nd = 60, 64th = 30
        var baseDurations = {
            1:  1920,   // whole
            2:  960,    // half
            4:  480,    // quarter
            8:  240,    // eighth
            16: 120,    // 16th
            32: 60,     // 32nd
            64: 30      // 64th
        };

        // For simple durations like 1/4, 1/8, etc.
        if (numerator === 1 && baseDurations[denominator] !== undefined) {
            return { ticks: baseDurations[denominator], dots: 0 };
        }

        // For dotted durations: 3/8 = dotted quarter (480 + 240 = 720)
        // A dotted note of base duration D has total duration D * 3/2.
        // So if numerator is 3, the base note has denominator * 2 as its
        // undotted denominator. E.g., 3/8 -> base is 1/4, dotted.
        if (numerator === 3) {
            var baseDenom = denominator * 2 / 3;
            // Actually: a dotted 1/D note = 3/(2*D). So 3/8 = dotted 1/4.
            // Base denominator for a dotted note: denominator / 2 if we think
            // of 3/8 = 1/4 + 1/8 = dotted quarter.
            // The base duration denominator is denominator / 2:
            //   3/8 -> base 4 (quarter), 3/4 -> base 2 (half), 3/16 -> base 8 (eighth)
            var undottedDenom = Math.floor(denominator / 2);
            if (denominator % 2 === 0 && baseDurations[undottedDenom] !== undefined) {
                return { ticks: baseDurations[undottedDenom], dots: 1 };
            }
        }

        // For double-dotted durations: 7/16 = double-dotted quarter
        if (numerator === 7) {
            var ddDenom = Math.floor(denominator / 4);
            if (denominator % 4 === 0 && baseDurations[ddDenom] !== undefined) {
                return { ticks: baseDurations[ddDenom], dots: 2 };
            }
        }

        // Fallback: compute tick duration directly from the fraction.
        // A whole note = 1920 ticks, so duration = 1920 * numerator / denominator.
        var totalTicks = Math.round(1920 * numerator / denominator);
        return { ticks: totalTicks, dots: 0 };
    }

    /**
     * Map a barline type string to the MuseScore Barline enum value.
     */
    function barlineTypeFromString(typeString) {
        var types = {
            "normal":      1,    // Barline.NORMAL
            "double":      2,    // Barline.DOUBLE
            "startRepeat":  4,   // Barline.START_REPEAT
            "endRepeat":    8,   // Barline.END_REPEAT
            "endStartRepeat": 16, // Barline.END_START_REPEAT
            "final":       32,   // Barline.FINAL
            "dashed":      64,   // Barline.DASHED
            "dotted":      128,  // Barline.DOTTED
            "tick":        256,  // Barline.TICK
            "short":       512   // Barline.SHORT
        };
        if (types[typeString] !== undefined) {
            return types[typeString];
        }
        return null;
    }

    // -----------------------------------------------------------------------
    // Command handlers
    // -----------------------------------------------------------------------

    /**
     * ping — simple health check.
     * Returns: { result: "pong" }
     */
    function handlePing() {
        return { result: "pong" };
    }

    /**
     * getScore — return metadata about the currently open score.
     * Returns: { result: { title, parts, measureCount, keySignature, timeSignature } }
     */
    function handleGetScore() {
        if (!curScore) {
            return { error: "No score is currently open" };
        }

        var parts = [];
        for (var i = 0; i < curScore.parts.length; i++) {
            var part = curScore.parts[i];
            parts.push({
                name: part.partName,
                startStaff: part.startStaff,
                endStaff: part.endStaff
            });
        }

        // Get key signature from first measure.
        var keySig = null;
        var cursor = curScore.newCursor();
        cursor.rewind(Cursor.SCORE_START);
        if (cursor.keySignature !== undefined) {
            keySig = cursor.keySignature;
        }

        // Get time signature from first measure.
        var timeSig = null;
        if (cursor.timeSignature) {
            timeSig = {
                numerator: cursor.timeSignature.numerator,
                denominator: cursor.timeSignature.denominator
            };
        }

        var measureCount = countMeasures();

        return {
            result: {
                title: curScore.title || "",
                partCount: parts.length,
                parts: parts,
                measureCount: measureCount,
                keySignature: keySig,
                timeSignature: timeSig
            }
        };
    }

    /**
     * getCursorInfo — return the current logical cursor position and the
     * element at that position.
     * Returns: { result: { measure, staff, voice, beat, element } }
     */
    function handleGetCursorInfo() {
        if (!curScore) {
            return { error: "No score is currently open" };
        }

        var cursor = positionedCursor();
        if (!cursor) {
            return { error: "Could not create cursor" };
        }

        var elementInfo = null;
        if (cursor.element) {
            elementInfo = describeElement(cursor.element);
        }

        // Compute beat position within the measure.
        var beat = null;
        if (cursor.measure && cursor.timeSignature) {
            var measureStartTick = cursor.measure.firstSegment.tick;
            var ticksPerBeat = 1920 / cursor.timeSignature.denominator;
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

    /**
     * Describe a score element as a plain object.
     */
    function describeElement(element) {
        if (!element) return null;

        var info = {
            type: element.type
        };

        // Element.NOTE = 24, Element.REST = 25, Element.CHORD = 91
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

    /**
     * goToMeasure — move the logical cursor to the specified measure.
     * Params: { measure: int } (1-indexed)
     * Returns: { result: { measure, staff } }
     */
    function handleGoToMeasure(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.measure === undefined) {
            return { error: "Missing required parameter: measure" };
        }

        var measureNumber = parseInt(params.measure);
        var totalMeasures = countMeasures();

        if (measureNumber < 1 || measureNumber > totalMeasures) {
            return { error: "Measure " + measureNumber + " out of range (1-" + totalMeasures + ")" };
        }

        cursorMeasure = measureNumber;
        return {
            result: {
                measure: cursorMeasure,
                staff: cursorStaff
            }
        };
    }

    /**
     * goToStaff — move the logical cursor to the specified staff.
     * Params: { staff: int } (0-indexed)
     * Returns: { result: { measure, staff } }
     */
    function handleGoToStaff(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.staff === undefined) {
            return { error: "Missing required parameter: staff" };
        }

        var staffIndex = parseInt(params.staff);
        if (staffIndex < 0 || staffIndex >= curScore.nstaves) {
            return { error: "Staff " + staffIndex + " out of range (0-" + (curScore.nstaves - 1) + ")" };
        }

        cursorStaff = staffIndex;
        return {
            result: {
                measure: cursorMeasure,
                staff: cursorStaff
            }
        };
    }

    /**
     * addNote — add a note at the current cursor position.
     * Params: { pitch: int, duration: { numerator, denominator }, advanceCursorAfterAction: bool }
     * - pitch: MIDI pitch number (60 = middle C)
     * - duration: fraction (e.g. {1, 4} = quarter note)
     * - advanceCursorAfterAction: if true, advance cursor past the written note
     * Returns: { result: { pitch, measure, staff } }
     */
    function handleAddNote(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.pitch === undefined) {
            return { error: "Missing required parameter: pitch" };
        }

        var pitch = parseInt(params.pitch);
        var numerator = 1;
        var denominator = 4;
        if (params.duration) {
            numerator = parseInt(params.duration.numerator) || 1;
            denominator = parseInt(params.duration.denominator) || 4;
        }
        var advance = (params.advanceCursorAfterAction !== false);

        var cursor = positionedCursor();
        if (!cursor) {
            return { error: "Could not position cursor" };
        }

        var durInfo = fractionToDuration(numerator, denominator);

        curScore.startCmd("addNote");
        cursor.setDuration(numerator, denominator);
        cursor.addNote(pitch);
        curScore.endCmd();

        if (advance) {
            // After addNote the cursor has advanced; update our logical measure.
            // Re-read the cursor position to see where we landed.
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

    /**
     * addRehearsalMark — add a rehearsal mark at the current cursor position.
     * Params: { text: string }
     * Returns: { result: { text, measure } }
     */
    function handleAddRehearsalMark(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.text === undefined || params.text === "") {
            return { error: "Missing required parameter: text" };
        }

        var cursor = positionedCursor();
        if (!cursor) {
            return { error: "Could not position cursor" };
        }

        curScore.startCmd("addRehearsalMark");

        var rehearsalMark = newElement(Element.REHEARSAL_MARK);
        rehearsalMark.text = params.text;
        cursor.add(rehearsalMark);

        curScore.endCmd();

        return {
            result: {
                text: params.text,
                measure: cursorMeasure
            }
        };
    }

    /**
     * setBarline — set the barline type at the current cursor position.
     * Params: { type: string }
     * Valid types: "normal", "double", "startRepeat", "endRepeat",
     *             "endStartRepeat", "final", "dashed", "dotted", "tick", "short"
     * Returns: { result: { type, measure } }
     */
    function handleSetBarline(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.type === undefined) {
            return { error: "Missing required parameter: type" };
        }

        var barlineType = barlineTypeFromString(params.type);
        if (barlineType === null) {
            return { error: "Unknown barline type: " + params.type +
                ". Valid types: normal, double, startRepeat, endRepeat, " +
                "endStartRepeat, final, dashed, dotted, tick, short" };
        }

        var cursor = positionedCursor();
        if (!cursor) {
            return { error: "Could not position cursor" };
        }

        curScore.startCmd("setBarline");

        // Find the measure at the cursor and set the end barline.
        if (cursor.measure) {
            var barline = newElement(Element.BAR_LINE);
            barline.barlineType = barlineType;
            cursor.add(barline);
        }

        curScore.endCmd();

        return {
            result: {
                type: params.type,
                measure: cursorMeasure
            }
        };
    }

    /**
     * setKeySignature — set the key signature at the current cursor position.
     * Params: { fifths: int }
     * - fifths: position on the circle of fifths (-7 to 7)
     *   -7 = Cb major, -1 = F major, 0 = C major, 1 = G major, 7 = C# major
     * Returns: { result: { fifths, measure } }
     */
    function handleSetKeySignature(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.fifths === undefined) {
            return { error: "Missing required parameter: fifths" };
        }

        var fifths = parseInt(params.fifths);
        if (fifths < -7 || fifths > 7) {
            return { error: "fifths must be between -7 and 7, got: " + fifths };
        }

        var cursor = positionedCursor();
        if (!cursor) {
            return { error: "Could not position cursor" };
        }

        curScore.startCmd("setKeySignature");

        var keySig = newElement(Element.KEYSIG);
        keySig.key = fifths;
        cursor.add(keySig);

        curScore.endCmd();

        return {
            result: {
                fifths: fifths,
                measure: cursorMeasure
            }
        };
    }

    /**
     * setTimeSignature — set the time signature at the current cursor position.
     * Params: { numerator: int, denominator: int }
     * Returns: { result: { numerator, denominator, measure } }
     */
    function handleSetTimeSignature(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.numerator === undefined || params.denominator === undefined) {
            return { error: "Missing required parameters: numerator and denominator" };
        }

        var numerator = parseInt(params.numerator);
        var denominator = parseInt(params.denominator);

        var cursor = positionedCursor();
        if (!cursor) {
            return { error: "Could not position cursor" };
        }

        curScore.startCmd("setTimeSignature");

        var timeSig = newElement(Element.TIMESIG);
        timeSig.timesig = fraction(numerator, denominator);
        cursor.add(timeSig);

        curScore.endCmd();

        return {
            result: {
                numerator: numerator,
                denominator: denominator,
                measure: cursorMeasure
            }
        };
    }

    /**
     * setTempo — set a tempo marking at the current cursor position.
     * Params: { bpm: int, text?: string }
     * - bpm: beats per minute
     * - text: optional display text (e.g. "Allegro"). If omitted, uses "♩ = <bpm>".
     * Returns: { result: { bpm, text, measure } }
     */
    function handleSetTempo(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.bpm === undefined) {
            return { error: "Missing required parameter: bpm" };
        }

        var bpm = parseInt(params.bpm);
        var displayText = params.text || ("\u2669 = " + bpm);

        var cursor = positionedCursor();
        if (!cursor) {
            return { error: "Could not position cursor" };
        }

        curScore.startCmd("setTempo");

        var tempo = newElement(Element.TEMPO_TEXT);
        tempo.text = displayText;
        // Tempo is stored as beats per second internally.
        tempo.tempo = bpm / 60.0;
        tempo.followText = false;
        cursor.add(tempo);

        curScore.endCmd();

        return {
            result: {
                bpm: bpm,
                text: displayText,
                measure: cursorMeasure
            }
        };
    }

    /**
     * addChordSymbol — add a chord symbol at the current cursor position.
     * Params: { text: string }
     * Returns: { result: { text, measure } }
     */
    function handleAddChordSymbol(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.text === undefined || params.text === "") {
            return { error: "Missing required parameter: text" };
        }

        var cursor = positionedCursor();
        if (!cursor) {
            return { error: "Could not position cursor" };
        }

        curScore.startCmd("addChordSymbol");

        var harmony = newElement(Element.HARMONY);
        harmony.text = params.text;

        // Place on the segment at the cursor's current position.
        if (cursor.segment) {
            cursor.add(harmony);
        }

        curScore.endCmd();

        return {
            result: {
                text: params.text,
                measure: cursorMeasure
            }
        };
    }

    /**
     * addDynamic — add a dynamic marking at the current cursor position.
     * Params: { type: string }
     * Valid types: "pppp", "ppp", "pp", "p", "mp", "mf", "f", "ff", "fff",
     *             "ffff", "fp", "sfz", "sffz", "sfp", "rfz", "fz"
     * Returns: { result: { type, measure } }
     */
    function handleAddDynamic(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.type === undefined || params.type === "") {
            return { error: "Missing required parameter: type" };
        }

        var cursor = positionedCursor();
        if (!cursor) {
            return { error: "Could not position cursor" };
        }

        curScore.startCmd("addDynamic");

        var dynamic = newElement(Element.DYNAMIC);
        dynamic.text = params.type;
        // MuseScore uses subtype for dynamics. Map common dynamics to
        // standard velocity values.
        var velocityMap = {
            "pppp": 10, "ppp": 25, "pp": 36, "p": 49, "mp": 64,
            "mf": 80, "f": 96, "ff": 112, "fff": 120, "ffff": 127,
            "fp": 96, "sfz": 112, "sffz": 120, "sfp": 112, "rfz": 112, "fz": 112
        };
        if (velocityMap[params.type] !== undefined) {
            dynamic.velocity = velocityMap[params.type];
        }
        cursor.add(dynamic);

        curScore.endCmd();

        return {
            result: {
                type: params.type,
                measure: cursorMeasure
            }
        };
    }

    /**
     * appendMeasures — append empty measures to the end of the score.
     * Params: { count: int }
     * Returns: { result: { count, totalMeasures } }
     */
    function handleAppendMeasures(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.count === undefined) {
            return { error: "Missing required parameter: count" };
        }

        var count = parseInt(params.count);
        if (count < 1) {
            return { error: "count must be at least 1, got: " + count };
        }

        curScore.startCmd("appendMeasures");
        curScore.appendMeasures(count);
        curScore.endCmd();

        return {
            result: {
                count: count,
                totalMeasures: countMeasures()
            }
        };
    }

    /**
     * selectCurrentMeasure — select all elements in the measure at the
     * current cursor position.
     * Returns: { result: { measure, staff } }
     */
    function handleSelectCurrentMeasure() {
        if (!curScore) {
            return { error: "No score is currently open" };
        }

        var cursor = positionedCursor();
        if (!cursor) {
            return { error: "Could not position cursor" };
        }

        if (!cursor.measure) {
            return { error: "No measure at current cursor position" };
        }

        // Select from the start of this measure to the start of the next.
        var measureStart = cursor.measure.firstSegment.tick;
        var measureEnd = cursor.measure.lastSegment.tick + 1;

        // Use cmd("select-all") won't work here — we need a range selection.
        // Set selection via the score's selection object.
        curScore.startCmd("selectCurrentMeasure");
        curScore.selection.selectRange(
            measureStart,
            measureEnd,
            cursorStaff,
            cursorStaff + 1
        );
        curScore.endCmd();

        return {
            result: {
                measure: cursorMeasure,
                staff: cursorStaff
            }
        };
    }

    /**
     * selectCustomRange — select a range of measures and staves.
     * Params: { startMeasure: int, endMeasure: int, startStaff: int, endStaff: int }
     * - Measures are 1-indexed, endMeasure is inclusive.
     * - Staves are 0-indexed, endStaff is inclusive.
     * Returns: { result: { startMeasure, endMeasure, startStaff, endStaff } }
     */
    function handleSelectCustomRange(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }

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
        cursor.rewind(Cursor.SCORE_START);

        // Navigate to startMeasure.
        for (var i = 1; i < startMeasure; i++) {
            cursor.nextMeasure();
        }
        var startTick = cursor.tick;

        // Navigate to the measure AFTER endMeasure (for the end boundary).
        for (var j = startMeasure; j <= endMeasure; j++) {
            cursor.nextMeasure();
        }
        // If we've gone past the end of the score, use the score's last tick.
        var endTick = cursor.measure ? cursor.tick : curScore.lastSegment.tick + 1;

        curScore.startCmd("selectCustomRange");
        curScore.selection.selectRange(
            startTick,
            endTick,
            startStaff,
            endStaff + 1   // selectRange uses exclusive end for staves
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

    /**
     * transpose — transpose the current selection by a given number of semitones.
     * Params: { semitones: int }
     * Requires an active selection (use selectCurrentMeasure or selectCustomRange first).
     * Returns: { result: { semitones } }
     */
    function handleTranspose(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (params.semitones === undefined) {
            return { error: "Missing required parameter: semitones" };
        }

        var semitones = parseInt(params.semitones);

        // Check that there is an active selection.
        if (!curScore.selection || !curScore.selection.elements ||
            curScore.selection.elements.length === 0) {
            return { error: "No active selection. Use selectCurrentMeasure or selectCustomRange first." };
        }

        curScore.startCmd("transpose");

        // cmd("transpose") with parameters:
        // direction: true = up, false = down
        // mode: 0 = chromatic by semitone
        // The MuseScore QML API provides a transpose method on the selection
        // or we can use the built-in cmd approach.
        //
        // Use the score-level transpose command. The API uses:
        //   curScore.transpose(mode, direction, key, diatonicInterval, chromaticInterval,
        //                      transposeKeySignatures, transposeChordNames)
        // mode: 0 = by interval, 1 = by key
        // direction: 0 = up, 1 = down

        var direction = semitones >= 0 ? 0 : 1;
        var absSemitones = Math.abs(semitones);

        // Map semitones to diatonic + chromatic interval pair.
        // Chromatic interval is abs(semitones).
        // Diatonic interval approximation: map semitones to the nearest
        // standard interval (used for correct enharmonic spelling).
        var diatonicMap = [0, 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6];
        var diatonicInterval = diatonicMap[absSemitones % 12] + Math.floor(absSemitones / 12) * 7;
        var chromaticInterval = absSemitones;

        // transpose(mode, direction, key, diatonicInterval, chromaticInterval,
        //           transposeKeySignatures, transposeChordNames)
        // key = 0 (unused in interval mode)
        curScore.transpose(0, direction, 0, diatonicInterval, chromaticInterval, true, true);

        curScore.endCmd();

        return {
            result: {
                semitones: semitones
            }
        };
    }

    /**
     * undo — undo the last action.
     * Returns: { result: "ok" }
     */
    function handleUndo() {
        if (!curScore) {
            return { error: "No score is currently open" };
        }

        cmd("undo");

        return { result: "ok" };
    }

    /**
     * processSequence — execute multiple commands atomically.
     * All commands share a single undo group. If any command fails,
     * all preceding commands in the sequence are undone.
     *
     * Params: { sequence: [{ action: string, params: object }, ...] }
     * Returns: { result: { results: [...], count: int } }
     *          or { error: string, failedAction: string, failedIndex: int, results: [...] }
     */
    function handleProcessSequence(params) {
        if (!curScore) {
            return { error: "No score is currently open" };
        }
        if (!params.sequence || !Array.isArray(params.sequence)) {
            return { error: "Missing required parameter: sequence (array of {action, params})" };
        }

        var sequence = params.sequence;
        if (sequence.length === 0) {
            return { result: { results: [], count: 0 } };
        }

        var results = [];

        // We wrap the entire sequence in a single startCmd/endCmd so that
        // all operations form one undo group.
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

            // Dispatch to the handler, but we need to handle the fact that
            // individual handlers call startCmd/endCmd themselves.
            // For processSequence, we call the internal logic directly
            // without nested startCmd/endCmd.
            var stepResult;
            try {
                stepResult = executeStepInSequence(action, actionParams);
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

        return {
            result: {
                results: results,
                count: results.length
            }
        };
    }

    /**
     * Execute a single step within a processSequence call.
     * This performs the action's logic WITHOUT wrapping in startCmd/endCmd
     * (since the caller already has an active command group).
     */
    function executeStepInSequence(action, params) {
        switch (action) {
            case "ping":
                return { result: "pong" };

            case "goToMeasure": {
                if (params.measure === undefined) {
                    return { error: "Missing required parameter: measure" };
                }
                var measureNum = parseInt(params.measure);
                var total = countMeasures();
                if (measureNum < 1 || measureNum > total) {
                    return { error: "Measure " + measureNum + " out of range (1-" + total + ")" };
                }
                cursorMeasure = measureNum;
                return { result: { measure: cursorMeasure, staff: cursorStaff } };
            }

            case "goToStaff": {
                if (params.staff === undefined) {
                    return { error: "Missing required parameter: staff" };
                }
                var staffIdx = parseInt(params.staff);
                if (staffIdx < 0 || staffIdx >= curScore.nstaves) {
                    return { error: "Staff " + staffIdx + " out of range" };
                }
                cursorStaff = staffIdx;
                return { result: { measure: cursorMeasure, staff: cursorStaff } };
            }

            case "addNote": {
                if (params.pitch === undefined) {
                    return { error: "Missing required parameter: pitch" };
                }
                var pitch = parseInt(params.pitch);
                var num = (params.duration && params.duration.numerator) ? parseInt(params.duration.numerator) : 1;
                var den = (params.duration && params.duration.denominator) ? parseInt(params.duration.denominator) : 4;
                var advance = (params.advanceCursorAfterAction !== false);

                var cursor = positionedCursor();
                if (!cursor) return { error: "Could not position cursor" };
                cursor.setDuration(num, den);
                cursor.addNote(pitch);
                if (advance) {
                    cursorMeasure = measureNumberAtTick(cursor.tick);
                }
                return { result: { pitch: pitch, measure: cursorMeasure } };
            }

            case "addRehearsalMark": {
                if (!params.text) return { error: "Missing required parameter: text" };
                var cursor = positionedCursor();
                if (!cursor) return { error: "Could not position cursor" };
                var rm = newElement(Element.REHEARSAL_MARK);
                rm.text = params.text;
                cursor.add(rm);
                return { result: { text: params.text, measure: cursorMeasure } };
            }

            case "setBarline": {
                if (!params.type) return { error: "Missing required parameter: type" };
                var bt = barlineTypeFromString(params.type);
                if (bt === null) return { error: "Unknown barline type: " + params.type };
                var cursor = positionedCursor();
                if (!cursor) return { error: "Could not position cursor" };
                var bl = newElement(Element.BAR_LINE);
                bl.barlineType = bt;
                cursor.add(bl);
                return { result: { type: params.type, measure: cursorMeasure } };
            }

            case "setKeySignature": {
                if (params.fifths === undefined) return { error: "Missing required parameter: fifths" };
                var fifths = parseInt(params.fifths);
                if (fifths < -7 || fifths > 7) return { error: "fifths must be between -7 and 7" };
                var cursor = positionedCursor();
                if (!cursor) return { error: "Could not position cursor" };
                var ks = newElement(Element.KEYSIG);
                ks.key = fifths;
                cursor.add(ks);
                return { result: { fifths: fifths, measure: cursorMeasure } };
            }

            case "setTimeSignature": {
                if (params.numerator === undefined || params.denominator === undefined) {
                    return { error: "Missing required parameters: numerator and denominator" };
                }
                var cursor = positionedCursor();
                if (!cursor) return { error: "Could not position cursor" };
                var ts = newElement(Element.TIMESIG);
                ts.timesig = fraction(parseInt(params.numerator), parseInt(params.denominator));
                cursor.add(ts);
                return { result: { numerator: parseInt(params.numerator), denominator: parseInt(params.denominator), measure: cursorMeasure } };
            }

            case "setTempo": {
                if (params.bpm === undefined) return { error: "Missing required parameter: bpm" };
                var bpm = parseInt(params.bpm);
                var text = params.text || ("\u2669 = " + bpm);
                var cursor = positionedCursor();
                if (!cursor) return { error: "Could not position cursor" };
                var tt = newElement(Element.TEMPO_TEXT);
                tt.text = text;
                tt.tempo = bpm / 60.0;
                tt.followText = false;
                cursor.add(tt);
                return { result: { bpm: bpm, text: text, measure: cursorMeasure } };
            }

            case "addChordSymbol": {
                if (!params.text) return { error: "Missing required parameter: text" };
                var cursor = positionedCursor();
                if (!cursor) return { error: "Could not position cursor" };
                var h = newElement(Element.HARMONY);
                h.text = params.text;
                cursor.add(h);
                return { result: { text: params.text, measure: cursorMeasure } };
            }

            case "addDynamic": {
                if (!params.type) return { error: "Missing required parameter: type" };
                var cursor = positionedCursor();
                if (!cursor) return { error: "Could not position cursor" };
                var dyn = newElement(Element.DYNAMIC);
                dyn.text = params.type;
                cursor.add(dyn);
                return { result: { type: params.type, measure: cursorMeasure } };
            }

            case "appendMeasures": {
                if (params.count === undefined) return { error: "Missing required parameter: count" };
                var count = parseInt(params.count);
                if (count < 1) return { error: "count must be at least 1" };
                curScore.appendMeasures(count);
                return { result: { count: count, totalMeasures: countMeasures() } };
            }

            default:
                return { error: "Unknown action in sequence: " + action };
        }
    }

    // -----------------------------------------------------------------------
    // Plugin lifecycle
    // -----------------------------------------------------------------------

    onRun: {
        console.log("[mcp-score] Bridge plugin started — WebSocket server on port 8765");
    }

    // Minimal invisible UI (required for dock plugin type to keep running).
    Rectangle {
        visible: false
        width: 0
        height: 0
    }
}
