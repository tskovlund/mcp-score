// MuseScore QML Plugin -- WebSocket server for mcp-score bridge.
//
// Install: copy to MuseScore's Plugins directory, enable via Plugin Manager.
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
//
// Supported commands:
//   ping, getScore, getCursorInfo, goToMeasure, goToStaff, addNote,
//   addRehearsalMark, setBarline, setKeySignature, setTimeSignature,
//   setTempo, addChordSymbol, addDynamic, appendMeasures,
//   selectCurrentMeasure, selectCustomRange, transpose, undo,
//   processSequence

import QtQuick 2.15
import MuseScore 3.0

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

    // Semitone interval (0-11, upward) -> change in tonal pitch class.
    // Gives the conventional spelling for each interval: a minor second
    // up spells C as Db (tpc -5), a major second up as D (tpc +2), and
    // so on. Downward intervals use the same table via modulo 12.
    readonly property var semitoneToTpcDelta: [0, -5, 2, -3, 4, -1, 6, 1, -4, 3, -2, 5]

    // Tonal pitch class bounds (Fbb .. B##) and the enharmonic step.
    readonly property int minTpc: -1
    readonly property int maxTpc: 33
    readonly property int tpcEnharmonicStep: 12

    // MIDI pitch bounds.
    readonly property int minMidiPitch: 0
    readonly property int maxMidiPitch: 127

    // Tracks per staff in MuseScore (four voices).
    readonly property int voicesPerStaff: 4

    // ===================================================================
    // WebSocket server
    // ===================================================================

    // Human-readable server state, shown in the plugin window.
    property string statusText: "Starting..."

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
    // Undo-step wrapper
    // ===================================================================

    /// Run `fn` inside one MuseScore undo step named `name`.
    /// The step is committed when `fn` returns a result and rolled back
    /// when it returns an error or throws, so a failed command never
    /// leaves partial changes in the score.
    function withUndoStep(name, fn) {
        var scoreErr = requireScore();
        if (scoreErr) return scoreErr;

        curScore.startCmd(name);
        var response;
        try {
            response = fn();
        } catch (e) {
            curScore.endCmd(true);
            throw e;
        }
        curScore.endCmd(response.error !== undefined);
        return response;
    }

    /// Action code that undoes the last step in the running MuseScore.
    /// MuseScore 4.7 moved notation actions to query-style codes; the
    /// plain "undo" code is what 4.4-4.6 register.
    function undoActionCode() {
        var queryStyleActions = mscoreMajorVersion > 4
            || (mscoreMajorVersion === 4 && mscoreMinorVersion >= 7);
        return queryStyleActions ? "action://notation/undo" : "undo";
    }

    // ===================================================================
    // Command handlers -- score modification
    //
    // Each command has an `apply*` function that validates its parameters
    // and mutates the score without opening an undo step. The `handle*`
    // wrapper runs it inside one undo step; processSequence runs several
    // inside a single step so the whole batch undoes together.
    // ===================================================================

    /// Add a note at the current cursor position.
    /// Params: { pitch, duration?: { numerator, denominator }, advanceCursorAfterAction?: bool }
    function applyAddNote(params) {
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
        if (pitch < minMidiPitch || pitch > maxMidiPitch) {
            return { error: "pitch must be between " + minMidiPitch + " and " + maxMidiPitch + ", got: " + pitch };
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

        cursor.setDuration(numerator, denominator);
        cursor.addNote(pitch);

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

    function handleAddNote(params) {
        return withUndoStep("addNote", function() { return applyAddNote(params); });
    }

    /// Add a rehearsal mark at the current cursor position.
    /// Params: { text }
    function applyAddRehearsalMark(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.text === undefined || params.text === "") {
            return { error: "Missing required parameter: text" };
        }
        if (!cursor.segment) {
            return { error: "No valid segment at cursor position" };
        }

        var rehearsalMark = newElement(Element.REHEARSAL_MARK);
        rehearsalMark.text = params.text;
        cursor.add(rehearsalMark);

        return { result: { text: params.text, measure: cursorMeasure } };
    }

    function handleAddRehearsalMark(params) {
        return withUndoStep("addRehearsalMark", function() { return applyAddRehearsalMark(params); });
    }

    /// Set the barline at the end of the measure at the cursor position.
    /// Params: { type }
    ///
    /// MuseScore 4 rejects bar lines inserted through Cursor.add (it
    /// crashes), so this changes the measure's existing end bar line on
    /// every staff instead. Repeats are measure flags in MuseScore, so
    /// the repeat types set those.
    function applySetBarline(params) {
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
        var measure = cursor.measure;
        if (!measure) {
            return { error: "No valid measure at cursor position" };
        }

        if (params.type === "startRepeat") {
            measure.repeatStart = true;
            return { result: { type: params.type, measure: cursorMeasure } };
        }
        if (params.type === "endStartRepeat") {
            var next = measure.nextMeasure;
            if (!next) {
                return { error: "endStartRepeat needs a following measure to start the repeat in" };
            }
            measure.repeatEnd = true;
            next.repeatStart = true;
            return { result: { type: params.type, measure: cursorMeasure } };
        }
        if (params.type === "endRepeat") {
            measure.repeatEnd = true;
            return { result: { type: params.type, measure: cursorMeasure } };
        }

        // A plain type replaces any end repeat on this measure.
        measure.repeatEnd = false;
        var endSegment = measure.lastSegment;
        var changed = 0;
        for (var staff = 0; staff < curScore.nstaves; staff++) {
            var element = endSegment ? endSegment.elementAt(staff * voicesPerStaff) : null;
            if (element && element.type === Element.BAR_LINE) {
                element.barlineType = barlineType;
                changed++;
            }
        }
        if (changed === 0) {
            return { error: "No end bar line found for measure " + cursorMeasure };
        }

        return { result: { type: params.type, measure: cursorMeasure } };
    }

    function handleSetBarline(params) {
        return withUndoStep("setBarline", function() { return applySetBarline(params); });
    }

    /// Set the key signature at the current cursor position.
    /// Params: { fifths } (-7 to 7 on the circle of fifths)
    function applySetKeySignature(params) {
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

        var keySig = newElement(Element.KEYSIG);
        keySig.key = fifths;
        cursor.add(keySig);

        return { result: { fifths: fifths, measure: cursorMeasure } };
    }

    function handleSetKeySignature(params) {
        return withUndoStep("setKeySignature", function() { return applySetKeySignature(params); });
    }

    /// Set the time signature at the current cursor position.
    /// Params: { numerator, denominator }
    function applySetTimeSignature(params) {
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

        var timeSig = newElement(Element.TIMESIG);
        timeSig.timesig = fraction(numerator, denominator);
        cursor.add(timeSig);

        return { result: { numerator: numerator, denominator: denominator, measure: cursorMeasure } };
    }

    function handleSetTimeSignature(params) {
        return withUndoStep("setTimeSignature", function() { return applySetTimeSignature(params); });
    }

    /// Set a tempo marking at the current cursor position.
    /// Params: { bpm, text? }
    function applySetTempo(params) {
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
        var displayText = params.text || ("♩ = " + bpm);
        if (!cursor.segment) {
            return { error: "No valid segment at cursor position" };
        }

        var tempo = newElement(Element.TEMPO_TEXT);
        tempo.text = displayText;
        tempo.tempo = bpm / secondsPerMinute;
        tempo.followText = false;
        cursor.add(tempo);

        return { result: { bpm: bpm, text: displayText, measure: cursorMeasure } };
    }

    function handleSetTempo(params) {
        return withUndoStep("setTempo", function() { return applySetTempo(params); });
    }

    /// Add a chord symbol at the current cursor position.
    /// Params: { text }
    ///
    /// The text is set after the element is in the score: MuseScore 4
    /// crashes when a chord symbol is parsed before it has a parent.
    function applyAddChordSymbol(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.text === undefined || params.text === "") {
            return { error: "Missing required parameter: text" };
        }
        if (!cursor.segment) {
            return { error: "No valid segment at cursor position" };
        }

        var harmony = newElement(Element.HARMONY);
        cursor.add(harmony);
        harmony.text = params.text;

        return { result: { text: params.text, measure: cursorMeasure } };
    }

    function handleAddChordSymbol(params) {
        return withUndoStep("addChordSymbol", function() { return applyAddChordSymbol(params); });
    }

    /// Add a dynamic marking at the current cursor position.
    /// Params: { type }
    function applyAddDynamic(params) {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (params.type === undefined || params.type === "") {
            return { error: "Missing required parameter: type" };
        }
        if (!cursor.segment) {
            return { error: "No valid segment at cursor position" };
        }

        var dynamic = newElement(Element.DYNAMIC);
        dynamic.text = params.type;
        if (dynamicVelocities[params.type] !== undefined) {
            dynamic.velocity = dynamicVelocities[params.type];
        }
        cursor.add(dynamic);

        return { result: { type: params.type, measure: cursorMeasure } };
    }

    function handleAddDynamic(params) {
        return withUndoStep("addDynamic", function() { return applyAddDynamic(params); });
    }

    /// Append empty measures to the end of the score.
    /// Params: { count }
    function applyAppendMeasures(params) {
        if (params.count === undefined) {
            return { error: "Missing required parameter: count" };
        }
        var count = safeParseInt(params.count);
        if (count === null || count < 1) {
            return { error: "count must be at least 1, got: " + count };
        }

        curScore.appendMeasures(count);

        return { result: { count: count, totalMeasures: countMeasures() } };
    }

    function handleAppendMeasures(params) {
        return withUndoStep("appendMeasures", function() { return applyAppendMeasures(params); });
    }

    // ===================================================================
    // Command handlers -- selection and transposition
    // ===================================================================

    /// Select all elements in the measure at the current cursor position.
    function applySelectCurrentMeasure() {
        var req = requireCursor();
        if (req.error) return req.error;
        var cursor = req.cursor;

        if (!cursor.measure) {
            return { error: "No measure at current cursor position" };
        }

        var measureStart = cursor.measure.firstSegment.tick;
        var measureEnd = cursor.measure.lastSegment.tick + 1;
        curScore.selection.selectRange(measureStart, measureEnd, cursorStaff, cursorStaff + 1);

        return { result: { measure: cursorMeasure, staff: cursorStaff } };
    }

    function handleSelectCurrentMeasure() {
        return withUndoStep("selectCurrentMeasure", function() { return applySelectCurrentMeasure(); });
    }

    /// Select a range of measures and staves.
    /// Params: { startMeasure, endMeasure, startStaff, endStaff }
    /// Measures are 1-indexed (inclusive). Staves are 0-indexed (inclusive).
    function applySelectCustomRange(params) {
        var startMeasure = safeParseInt(params.startMeasure);
        var endMeasure = safeParseInt(params.endMeasure);
        var startStaff = safeParseInt(params.startStaff);
        var endStaff = safeParseInt(params.endStaff);

        if (startMeasure === null || endMeasure === null ||
            startStaff === null || endStaff === null) {
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

        // selectRange uses an exclusive end for staves.
        curScore.selection.selectRange(startTick, endTick, startStaff, endStaff + 1);

        return {
            result: {
                startMeasure: startMeasure,
                endMeasure: endMeasure,
                startStaff: startStaff,
                endStaff: endStaff
            }
        };
    }

    function handleSelectCustomRange(params) {
        return withUndoStep("selectCustomRange", function() { return applySelectCustomRange(params); });
    }

    /// Bring a tonal pitch class back into range by respelling it
    /// enharmonically (e.g. B## becomes C#).
    function respellTpc(tpc) {
        while (tpc > maxTpc) tpc -= tpcEnharmonicStep;
        while (tpc < minTpc) tpc += tpcEnharmonicStep;
        return tpc;
    }

    /// Transpose the notes in the current selection by a number of semitones.
    /// Params: { semitones }
    /// Requires an active selection (use selectCurrentMeasure or selectCustomRange first).
    ///
    /// MuseScore 4's plugin API has no transpose call, so each selected
    /// note is shifted directly, with its spelling moved by the
    /// conventional interval. Key signatures and chord symbols are not
    /// transposed.
    function applyTranspose(params) {
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

        var elements = curScore.selection.elements;
        var notes = [];
        for (var i = 0; i < elements.length; i++) {
            if (elements[i].type === Element.NOTE) {
                notes.push(elements[i]);
            }
        }
        if (notes.length === 0) {
            return { error: "The selection contains no notes" };
        }

        // Validate every target pitch before changing anything.
        for (var v = 0; v < notes.length; v++) {
            var target = notes[v].pitch + semitones;
            if (target < minMidiPitch || target > maxMidiPitch) {
                return { error: "Transposition would move a note to MIDI pitch " + target +
                    ", outside " + minMidiPitch + "-" + maxMidiPitch };
            }
        }

        var tpcDelta = semitoneToTpcDelta[((semitones % 12) + 12) % 12];
        for (var n = 0; n < notes.length; n++) {
            var note = notes[n];
            note.pitch = note.pitch + semitones;
            note.tpc1 = respellTpc(note.tpc1 + tpcDelta);
            note.tpc2 = respellTpc(note.tpc2 + tpcDelta);
        }

        return { result: { semitones: semitones, notes: notes.length } };
    }

    function handleTranspose(params) {
        return withUndoStep("transpose", function() { return applyTranspose(params); });
    }

    /// Undo the last action.
    function handleUndo() {
        var scoreErr = requireScore();
        if (scoreErr) return scoreErr;

        cmd(undoActionCode());

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

    /// Execute multiple actions in a single undo step.
    /// If any action fails, the score and the cursor are restored to
    /// their state before the sequence.
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

        var savedMeasure = cursorMeasure;
        var savedStaff = cursorStaff;

        var response = withUndoStep("processSequence", function() {
            var results = [];
            for (var i = 0; i < sequence.length; i++) {
                var step = sequence[i];
                var action = step.action;
                if (!action) {
                    return { error: "Step " + i + " is missing 'action' field", failedIndex: i, results: results };
                }

                var stepResult;
                try {
                    stepResult = executeSequenceStep(action, step.params || {});
                } catch (e) {
                    stepResult = { error: e.message || String(e) };
                }
                if (stepResult.error) {
                    return {
                        error: "Step " + i + " (" + action + ") failed: " + stepResult.error,
                        failedAction: action,
                        failedIndex: i,
                        results: results
                    };
                }
                results.push(stepResult.result);
            }
            return { result: { results: results, count: results.length } };
        });

        if (response.error !== undefined) {
            cursorMeasure = savedMeasure;
            cursorStaff = savedStaff;
        }
        return response;
    }

    /// Execute one step of processSequence inside the caller's undo step.
    function executeSequenceStep(action, params) {
        switch (action) {
            case "ping":                 return handlePing();
            case "goToMeasure":          return handleGoToMeasure(params);
            case "goToStaff":            return handleGoToStaff(params);
            case "addNote":              return applyAddNote(params);
            case "addRehearsalMark":     return applyAddRehearsalMark(params);
            case "setBarline":           return applySetBarline(params);
            case "setKeySignature":      return applySetKeySignature(params);
            case "setTimeSignature":     return applySetTimeSignature(params);
            case "setTempo":             return applySetTempo(params);
            case "addChordSymbol":       return applyAddChordSymbol(params);
            case "addDynamic":           return applyAddDynamic(params);
            case "appendMeasures":       return applyAppendMeasures(params);
            case "selectCurrentMeasure": return applySelectCurrentMeasure();
            case "selectCustomRange":    return applySelectCustomRange(params);
            case "transpose":            return applyTranspose(params);
            default:
                return { error: "Unknown action in sequence: " + action };
        }
    }

    // ===================================================================
    // Plugin lifecycle
    // ===================================================================

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
